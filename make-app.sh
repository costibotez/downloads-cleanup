#!/bin/bash
# Builds "Downloads Sorter.app" (in this folder) that starts the sorter and opens it in your browser.
# Usage: ./make-app.sh            then drag the app to /Applications or your Dock if you like.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/Downloads Sorter.app"

swiftc -O -o "$ROOT/build/sorter-vision" "$ROOT/native/SorterVision.swift" 2>/dev/null
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Downloads Sorter</string>
  <key>CFBundleDisplayName</key><string>Downloads Sorter</string>
  <key>CFBundleIdentifier</key><string>local.downloads-sorter</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSUIElement</key><true/>
  <key>NSDownloadsFolderUsageDescription</key><string>Downloads Sorter files the contents of your Downloads folder.</string>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/launcher" <<LAUNCH
#!/bin/bash
ROOT="$ROOT"
URL_FILE="\$HOME/Library/Application Support/Downloads Sorter/server.url"
if [ -f "\$URL_FILE" ] && curl -fs -o /dev/null "\$(cat "\$URL_FILE")"; then
  open "\$(cat "\$URL_FILE")"
  exit 0
fi
export PATH="/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:\$PATH"
mkdir -p "\$HOME/Library/Logs"
exec python3 "\$ROOT/app/server.py" >> "\$HOME/Library/Logs/Downloads Sorter.log" 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/launcher"

# Icon: a cobalt folder, drawn with the system's own tools.
ICON_TMP="$(mktemp -d)"
cat > "$ICON_TMP/icon.swift" <<'SWIFT'
import AppKit
let size = 1024.0
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
NSColor(red: 0.055, green: 0.09, blue: 0.15, alpha: 1).setFill()
NSBezierPath(roundedRect: NSRect(x: 80, y: 80, width: 864, height: 864), xRadius: 190, yRadius: 190).fill()
NSColor(red: 0.14, green: 0.34, blue: 0.88, alpha: 1).setFill()
let tab = NSBezierPath(roundedRect: NSRect(x: 230, y: 560, width: 250, height: 110), xRadius: 34, yRadius: 34)
tab.fill()
NSBezierPath(roundedRect: NSRect(x: 230, y: 300, width: 564, height: 330), xRadius: 44, yRadius: 44).fill()
NSColor(red: 0.80, green: 0.85, blue: 0.98, alpha: 1).setFill()
for (i, w) in [300.0, 220.0, 260.0].enumerated() {
  NSBezierPath(roundedRect: NSRect(x: 300, y: 540 - Double(i) * 70, width: w, height: 34), xRadius: 17, yRadius: 17).fill()
}
img.unlockFocus()
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
SWIFT
if swift "$ICON_TMP/icon.swift" "$ICON_TMP/icon.png" 2>/dev/null; then
  mkdir -p "$ICON_TMP/AppIcon.iconset"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$ICON_TMP/icon.png" --out "$ICON_TMP/AppIcon.iconset/icon_${s}x${s}.png" >/dev/null
    sips -z $((s*2)) $((s*2)) "$ICON_TMP/icon.png" --out "$ICON_TMP/AppIcon.iconset/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICON_TMP/AppIcon.iconset" -o "$APP/Contents/Resources/AppIcon.icns" || true
fi
rm -rf "$ICON_TMP"
echo "Built: $APP"
