#!/bin/sh
# Kindle Paperwhite 10 出门看板：整点拉图并全屏显示
#
# 点「启动看板」后系统会回到主页盖住画面，所以启动后只补绘几次；
# 之后每个整点拉一次新图并显示，不再几秒刷一次。

IMAGE_URL="${IMAGE_URL:-https://hou-boyu.github.io/kindle-dashboard/dashboard.png}"
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

# 距下一个整点还有多少秒（busybox 友好）
seconds_to_next_hour() {
  MIN=$(date +%M)
  SEC=$(date +%S)
  case "$MIN" in 0*) MIN=${MIN#0} ;; esac
  case "$SEC" in 0*) SEC=${SEC#0} ;; esac
  [ -z "$MIN" ] && MIN=0
  [ -z "$SEC" ] && SEC=0
  LEFT=$((3600 - MIN * 60 - SEC))
  if [ "$LEFT" -le 0 ]; then
    LEFT=3600
  fi
  echo "$LEFT"
}

log "dashboard started url=$IMAGE_URL mode=hourly"
prevent_sleep
refresh_wifi

if fetch_image; then
  log "initial fetch ok"
else
  log "initial fetch skipped/failed; using local image if any"
fi

display_image || log "display failed: no png yet"
# 启动后补绘几次，盖过主页重绘；之后不再高频刷新
sleep 5
prevent_sleep
display_image || true
sleep 10
prevent_sleep
display_image || true

while true; do
  WAIT="$(seconds_to_next_hour)"
  log "sleep ${WAIT}s until next hour"
  sleep "$WAIT"
  prevent_sleep
  refresh_wifi
  if fetch_image; then
    log "hourly fetch ok"
  else
    log "hourly fetch failed; keep current frame"
  fi
  display_image || true
  # 整点后再补绘一次，防止刚刷新就被系统盖掉
  sleep 8
  prevent_sleep
  display_image || true
done
