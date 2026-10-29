#!/bin/bash
# Renders the README banner with headless Chrome and copies the app icon.
#   bash docs/src/render.sh            (run ./make-app.sh first for the icon)
# The screenshots are taken from the running app pointed at a folder made by demo-files.sh.
set -euo pipefail
DOCS="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1544,500 \
  --screenshot="$DOCS/banner.png" "file://$DOCS/src/banner.html" 2>/dev/null
ICNS="$DOCS/../Downloads Sorter.app/Contents/Resources/AppIcon.icns"
if [ -f "$ICNS" ]; then
  sips -s format png "$ICNS" --out "$DOCS/icon.png" -Z 256 >/dev/null
fi
echo "Rendered $DOCS/banner.png and $DOCS/icon.png"
