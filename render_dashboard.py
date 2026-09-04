#!/usr/bin/env python3
"""Render Apple Calendar + weather + lunar date into a PW4 dashboard PNG."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import requests
from dateutil.rrule import rrulestr
from icalendar import Calendar
from icalendar.prop import vDDDTypes
from PIL import Image, ImageDraw, ImageFont
from zhdate import ZhDate

try:
    import chinese_calendar as cn_calendar
except ImportError:  # pragma: no cover
    cn_calendar = None

# Kindle Paperwhite 10th gen (PW4)
WIDTH = 1072
HEIGHT = 1448

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
LUNAR_FESTIVALS = {
    (1, 1): "春节",
    (1, 15): "元宵节",
    (2, 2): "龙抬头",
    (5, 5): "端午节",
    (7, 7): "七夕",
    (8, 15): "中秋节",
    (9, 9): "重阳节",
    (12, 8): "腊八",
    (12, 23): "北方小年",
    (12, 24): "南方小年",
}
HOLIDAY_CN = {
    "New Year's Day": "元旦",
    "Spring Festival": "春节",
    "Tomb-sweeping Day": "清明节",
    "Labour Day": "劳动节",
    "Dragon Boat Festival": "端午节",
    "National Day": "国庆节",
    "Mid-autumn Festival": "中秋节",
}
    0: "晴",
    1: "晴间多云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    56: "冻毛毛雨",
    57: "冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "阵雪",
    95: "雷阵雨",
    96: "雷阵雨",
    99: "雷阵雨",
}
TIP_GROUPS = [
    ("出门前", ["关火", "关水", "关窗"]),
    ("随身", ["带钥匙", "戴戒指", "戴手表"]),
    ("家里", ["喂猫", "浇花", "扔垃圾"]),
]


@dataclass
class EventItem:
    start: datetime
    end: datetime
    summary: str
    all_day: bool

    @property
    def day(self) -> date:
        return self.start.date()


@dataclass
class DayWeather:
    label: str
    text: str
    temp: str


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or default


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Medium.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
            ]
        )
    candidates.extend(
        [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]
    )
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=0)
            except OSError:
                continue
    return ImageFont.load_default()


def normalize_ics_url(url: str) -> str:
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://") :]
    return url


def parse_ics_urls(raw: str) -> list[str]:
    return [normalize_ics_url(part) for part in raw.split(",") if part.strip()]


def as_datetime(value, tz: ZoneInfo, all_day: bool) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=tz)
        return value.astimezone(tz)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=tz)
    if isinstance(value, vDDDTypes):
        return as_datetime(value.dt, tz, all_day)
    raise TypeError(f"Unsupported date value: {type(value)!r}")


def fetch_calendar(url: str) -> Calendar:
    response = requests.get(
        url,
        timeout=45,
        headers={"User-Agent": "kindle-dashboard/1.0"},
    )
    response.raise_for_status()
    return Calendar.from_ical(response.content)


def expand_events(
    cal: Calendar,
    window_start: datetime,
    window_end: datetime,
    tz: ZoneInfo,
) -> list[EventItem]:
    items: list[EventItem] = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        summary = str(component.get("summary") or "（无标题）").strip()
        dtstart = component.get("dtstart")
        dtend = component.get("dtend")
        if dtstart is None:
            continue

        raw_start = dtstart.dt
        all_day = not isinstance(raw_start, datetime)
        start = as_datetime(raw_start, tz, all_day)

        if dtend is not None:
            end = as_datetime(dtend.dt, tz, all_day)
        elif all_day:
            end = start + timedelta(days=1)
        else:
            end = start + timedelta(hours=1)

        status = str(component.get("status") or "").upper()
        if status == "CANCELLED":
            continue

        rrule = component.get("rrule")
        if rrule:
            duration = end - start
            rule_text = component.get("rrule").to_ical().decode()
            rule = rrulestr(rule_text, dtstart=start)
            for occurrence in rule.between(window_start - duration, window_end, inc=True):
                if isinstance(occurrence, datetime):
                    if occurrence.tzinfo is None:
                        occurrence = occurrence.replace(tzinfo=tz)
                    else:
                        occurrence = occurrence.astimezone(tz)
                else:
                    occurrence = datetime.combine(occurrence, time.min, tzinfo=tz)
                occ_end = occurrence + duration
                if occ_end <= window_start or occurrence >= window_end:
                    continue
                items.append(
                    EventItem(
                        start=occurrence,
                        end=occ_end,
                        summary=summary,
                        all_day=all_day,
                    )
                )
            continue

        if end <= window_start or start >= window_end:
            continue
        items.append(EventItem(start=start, end=end, summary=summary, all_day=all_day))

    items.sort(key=lambda e: (e.start, e.end, e.summary))
    return items


def collect_events(urls: Iterable[str], days_ahead: int, tz: ZoneInfo) -> list[EventItem]:
    now = datetime.now(tz)
    today = now.date()
    window_start = datetime.combine(today, time.min, tzinfo=tz)
    window_end = datetime.combine(today + timedelta(days=days_ahead), time.min, tzinfo=tz)

    all_items: list[EventItem] = []
    errors: list[str] = []
    for url in urls:
        try:
            cal = fetch_calendar(url)
            all_items.extend(expand_events(cal, window_start, window_end, tz))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url[:48]}… → {exc}" if len(url) > 48 else f"{url} → {exc}")

    dedup: dict[tuple, EventItem] = {}
    for item in all_items:
        key = (item.start, item.end, item.summary, item.all_day)
        dedup[key] = item
    items = sorted(dedup.values(), key=lambda e: (e.start, e.end, e.summary))
    if errors:
        print("calendar warnings:\n" + "\n".join(errors), file=sys.stderr)
    return items


def lunar_text(d: date) -> str:
    lunar = ZhDate.from_datetime(datetime(d.year, d.month, d.day))
    chinese = lunar.chinese().split("年", 1)[-1]
    # "七月二十三 丙午年 (马年)" → 农历七月二十三
    main = chinese.split()[0] if chinese else chinese
    return f"农历{main}"


def festival_text(d: date) -> str:
    names: list[str] = []
    if cn_calendar is not None:
        on_holiday, holiday_name = cn_calendar.get_holiday_detail(d)
        if holiday_name:
            names.append(HOLIDAY_CN.get(str(holiday_name), str(holiday_name)))
        elif on_holiday:
            names.append("节日")
    lunar = ZhDate.from_datetime(datetime(d.year, d.month, d.day))
    fest = LUNAR_FESTIVALS.get((lunar.lunar_month, lunar.lunar_day))
    if fest and fest not in names:
        names.append(fest)
    next_day = ZhDate.from_datetime(datetime(d.year, d.month, d.day) + timedelta(days=1))
    if next_day.lunar_month == 1 and next_day.lunar_day == 1 and "除夕" not in names:
        names.append("除夕")
    return " · ".join(names) if names else "今日无节日"


def weather_label(code: int) -> str:
    if code in WMO_WEATHER:
        return WMO_WEATHER[code]
    if code <= 3:
        return "多云"
    if code < 70:
        return "雨"
    if code < 80:
        return "雪"
    return "天气变化"


def fetch_weather(lat: float, lon: float, tz_name: str, city: str) -> list[DayWeather]:
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": tz_name,
                "forecast_days": 2,
            },
            timeout=30,
            headers={"User-Agent": "kindle-dashboard/1.0"},
        )
        response.raise_for_status()
        daily = response.json()["daily"]
        labels = ["今天", "明天"]
        out: list[DayWeather] = []
        for i, label in enumerate(labels):
            code = int(daily["weather_code"][i])
            tmax = round(float(daily["temperature_2m_max"][i]))
            tmin = round(float(daily["temperature_2m_min"][i]))
            out.append(
                DayWeather(
                    label=f"{label} · {city}",
                    text=weather_label(code),
                    temp=f"{tmin}–{tmax}°C",
                )
            )
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"weather warning: {exc}", file=sys.stderr)
        return [
            DayWeather("今天", "暂不可用", "—"),
            DayWeather("明天", "暂不可用", "—"),
        ]


def format_day_header(d: date, today: date) -> str:
    label = f"{d.month}/{d.day} 周{WEEKDAYS[d.weekday()]}"
    if d == today:
        return f"今天 · {label}"
    if d == today + timedelta(days=1):
        return f"明天 · {label}"
    return label


def format_time_range(event: EventItem) -> str:
    if event.all_day:
        return "全天"
    return f"{event.start.strftime('%H:%M')}–{event.end.strftime('%H:%M')}"


def truncate(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    low, high = 0, len(text)
    while low < high:
        mid = (low + high) // 2
        candidate = text[:mid] + ellipsis
        if draw.textlength(candidate, font=font) <= max_width:
            low = mid + 1
        else:
            high = mid
    return text[: max(0, low - 1)] + ellipsis


def render(
    events: list[EventItem],
    title: str,
    tz: ZoneInfo,
    output: Path,
    weather: list[DayWeather],
) -> None:
    now = datetime.now(tz)
    today = now.date()

    img = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    font_kicker = load_font(22)
    font_title = load_font(48, bold=True)
    font_date = load_font(36, bold=True)
    font_sub = load_font(26)
    font_sec = load_font(28, bold=True)
    font_body = load_font(28)
    font_small = load_font(24)
    font_tip = load_font(30, bold=True)

    margin_x = 40
    inner_right = WIDTH - margin_x
    y = 28

    draw.text((margin_x, y), title, font=font_kicker, fill=80)
    y += 32
    draw.text((margin_x, y), f"{today.year}年{today.month}月{today.day}日  星期{WEEKDAYS[today.weekday()]}", font=font_title, fill=0)
    y += 58
    draw.text((margin_x, y), lunar_text(today), font=font_date, fill=0)
    y += 44
    draw.text((margin_x, y), festival_text(today), font=font_sub, fill=40)
    y += 36
    draw.text((margin_x, y), f"更新 {now.strftime('%H:%M')}", font=font_kicker, fill=110)
    y += 32
    draw.line((margin_x, y, inner_right, y), fill=0, width=3)
    y += 18

    draw.text((margin_x, y), "天气", font=font_sec, fill=0)
    y += 40
    col_w = (inner_right - margin_x) // 2
    for i, day in enumerate(weather[:2]):
        x = margin_x + i * col_w
        draw.text((x, y), day.label, font=font_small, fill=80)
        draw.text((x, y + 32), day.text, font=font_date, fill=0)
        draw.text((x, y + 78), day.temp, font=font_body, fill=40)
    y += 122
    draw.line((margin_x, y, inner_right, y), fill=180, width=1)
    y += 16

    draw.text((margin_x, y), "最近一周", font=font_sec, fill=0)
    y += 40

    tips_top = HEIGHT - 268
    content_bottom = tips_top - 12

    if not events:
        draw.text((margin_x, y), "近几天没有日程", font=font_body, fill=0)
        y += 40
    else:
        current_day: date | None = None
        for event in events:
            extra = 92 if event.day != current_day else 48
            if y + extra > content_bottom:
                draw.text((margin_x, y), "……更多请看日历 App", font=font_small, fill=80)
                break
            if event.day != current_day:
                if current_day is not None:
                    y += 8
                    draw.line((margin_x, y, inner_right, y), fill=210, width=1)
                    y += 12
                current_day = event.day
                draw.text((margin_x, y), format_day_header(current_day, today), font=font_sec, fill=0)
                y += 40
            time_label = format_time_range(event)
            draw.text((margin_x, y + 2), time_label, font=font_small, fill=70)
            text_x = margin_x + 148
            summary = truncate(event.summary, font_body, inner_right - text_x, draw)
            draw.text((text_x, y), summary, font=font_body, fill=0)
            y += 44

    draw.line((margin_x, tips_top, inner_right, tips_top), fill=0, width=3)
    ty = tips_top + 16
    draw.text((margin_x, ty), "出门提示", font=font_sec, fill=0)
    ty += 42
    for group_name, items in TIP_GROUPS:
        draw.text((margin_x, ty + 4), group_name, font=font_small, fill=80)
        x = margin_x + 92
        for item in items:
            box = 22
            draw.rectangle((x, ty + 6, x + box, ty + 6 + box), outline=0, width=2)
            draw.text((x + box + 8, ty), item, font=font_tip, fill=0)
            x += 220
        ty += 52

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG", optimize=True)
    print(f"Wrote {output} ({WIDTH}x{HEIGHT})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Kindle calendar dashboard PNG")
    parser.add_argument("--ics-url", default=env("CALENDAR_ICS_URL"), help="ICS URL(s), comma-separated")
    parser.add_argument("--timezone", default=env("TIMEZONE", "Asia/Shanghai"))
    parser.add_argument("--days", type=int, default=int(env("DAYS_AHEAD", "7") or "7"))
    parser.add_argument("--title", default=env("DASHBOARD_TITLE", "出门看板"))
    parser.add_argument("--output", default=env("OUTPUT_PATH", "output/dashboard.png"))
    parser.add_argument("--lat", type=float, default=float(env("WEATHER_LAT", "31.2304") or "31.2304"))
    parser.add_argument("--lon", type=float, default=float(env("WEATHER_LON", "121.4737") or "121.4737"))
    parser.add_argument("--city", default=env("WEATHER_CITY", "上海"))
    parser.add_argument("--allow-empty-calendar", action="store_true")
    args = parser.parse_args()

    tz = ZoneInfo(args.timezone)
    events: list[EventItem] = []
    if args.ics_url:
        events = collect_events(parse_ics_urls(args.ics_url), args.days, tz)
    elif not args.allow_empty_calendar:
        print("缺少 CALENDAR_ICS_URL / --ics-url", file=sys.stderr)
        return 2

    weather = fetch_weather(args.lat, args.lon, args.timezone, args.city or "上海")
    render(events, args.title, tz, Path(args.output), weather)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
