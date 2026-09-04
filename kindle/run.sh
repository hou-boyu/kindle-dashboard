#!/bin/sh
# Kindle Paperwhite 10 出门看板：定时拉图并全屏显示
#
# 点「启动看板」后 Kindle 会回到主页并重绘界面，把刚画的图盖掉。
# 所以这里每隔几秒重绘一次；联网拉新图仍按 FETCH_INTERVAL。

IMAGE_URL="${IMAGE_URL:-https://YOUR_USER.github.io/YOUR_REPO/dashboard.png}"
FETCH_INTERVAL_SEC="${FETCH_INTERVAL_SEC:-1200}"
REDRAW_INTERVAL_SEC="${REDRAW_INTERVAL_SEC:-8}"
LOCAL_FILE="/mnt/us/dashboard/dashboard.png"
BUNDLED_FILE="/mnt/us/dashboard/preview.png"
LOG_FILE="/mnt/us/dashboard/dashboard.log"

mkdir -p /mnt/us/dashboard

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"
}

prevent_sleep() {
  lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null
  touch /mnt/us/TESTD_PREVENT_SCREENSAVER 2>/dev/null
}

refresh_wifi() {
  lipc-set-prop com.lab126.cmd wirelessEnable 1 2>/dev/null
}

pick_image() {
  if [ -s "$LOCAL_FILE" ]; then
    echo "$LOCAL_FILE"
    return 0
  fi
  if [ -s "$BUNDLED_FILE" ]; then
    echo "$BUNDLED_FILE"
    return 0
  fi
  return 1
}

display_image() {
  IMG="$(pick_image)" || return 1
  if [ -x /mnt/us/libkh/bin/fbink ]; then
    /mnt/us/libkh/bin/fbink -q -c -f -g file="$IMG" >/dev/null 2>&1 || {
      /mnt/us/libkh/bin/fbink -q -c >/dev/null 2>&1
      /mnt/us/libkh/bin/fbink -q -f -g file="$IMG" >/dev/null 2>&1
    }
  else
    eips -g "$IMG" >/dev/null 2>&1 || {
      eips -c >/dev/null 2>&1
      eips -g "$IMG" >/dev/null 2>&1
    }
  fi
}

fetch_image() {
  case "$IMAGE_URL" in
    *YOUR_USER*|*YOUR_REPO*)
      return 1
      ;;
  esac
  TMP="${LOCAL_FILE}.tmp"
  rm -f "$TMP"
  if wget -q --timeout=30 --tries=2 \
    --header="Cache-Control: no-cache" \
    -O "$TMP" "$IMAGE_URL"; then
    if [ -s "$TMP" ]; then
      mv "$TMP" "$LOCAL_FILE"
      return 0
    fi
  fi
  rm -f "$TMP"
  return 1
}

log "dashboard started url=$IMAGE_URL fetch=${FETCH_INTERVAL_SEC}s redraw=${REDRAW_INTERVAL_SEC}s"
prevent_sleep
refresh_wifi

if fetch_image; then
  log "initial fetch ok"
else
  log "initial fetch skipped/failed; using local image if any"
fi

LAST_FETCH="$(date +%s)"
display_image || log "display failed: no png yet"

while true; do
  prevent_sleep
  sleep "$REDRAW_INTERVAL_SEC"
  NOW="$(date +%s)"
  ELAPSED=$((NOW - LAST_FETCH))
  if [ "$ELAPSED" -ge "$FETCH_INTERVAL_SEC" ]; then
    refresh_wifi
    if fetch_image; then
      log "refresh ok"
    fi
    LAST_FETCH="$NOW"
  fi
  display_image || true
done
