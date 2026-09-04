#!/bin/bash
set -euo pipefail
IDX="/Volumes/Kindle/.active_content_sandbox/store/resource/cachedResources/index.html"
if [[ ! -f "$IDX" ]]; then
  echo "ERROR: Kindle payload not found at $IDX"
  exit 1
fi
cp "$IDX" "$IDX.bak"
python3 - <<'PY'
from pathlib import Path
p = Path("/Volumes/Kindle/.active_content_sandbox/store/resource/cachedResources/index.html")
t = p.read_text()
t2 = t.replace("sb.penguins184.xyz", "bookfere.com/jb/sb")
if t == t2:
    raise SystemExit("replace failed - pattern not found")
p.write_text(t2)
print("patched ok")
PY
grep -n "bookfere\|penguins184\|kindlemodding" "$IDX" || true
sync
diskutil eject /Volumes/Kindle
echo "EJECTED"
ls /Volumes
