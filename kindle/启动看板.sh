#!/bin/sh
# Kindle scriptlet: 从图书馆点开即可启动看板

lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null
touch /mnt/us/TESTD_PREVENT_SCREENSAVER 2>/dev/null

# 先停掉旧循环，再启动新脚本（避免卡在 20 分钟刷新的旧版本）
if pgrep -f '/mnt/us/dashboard/run.sh' >/dev/null 2>&1; then
  kill $(pgrep -f '/mnt/us/dashboard/run.sh') 2>/dev/null || true
  sleep 1
fi

if [ ! -x /mnt/us/dashboard/run.sh ]; then
  eips 10 10 "Missing dashboard/run.sh" 2>/dev/null || true
  sleep 3
  exit 1
fi

nohup sh /mnt/us/dashboard/run.sh >>/mnt/us/dashboard/dashboard.log 2>&1 &

eips 10 10 "Dashboard starting..." 2>/dev/null || true
sleep 2
