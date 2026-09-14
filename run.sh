#!/usr/bin/env bash
# Launch the CleanMac app detached so the terminal returns immediately.
# Wraps the binary in a minimal .app bundle (macOS grants windows and
# menu-bar slots only to bundled apps, not raw executables).
# Usage: ./run.sh  (from the swift/ directory)
set -u
cd "$(dirname "$0")"
swift build 2>&1 | grep -E "^error" && exit 1
if [ ! -f Resources/AppIcon.icns ]; then
  swift scripts/render-icon.swift build/AppIcon.iconset >/dev/null
  iconutil -c icns build/AppIcon.iconset -o Resources/AppIcon.icns
fi
BIN="$(swift build --show-bin-path)/CleanMac"
APP="$PWD/.app/CleanMac.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/CleanMac"
cp Resources/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
cat > "$APP/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>CleanMac</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.cleanmac.app</string>
    <key>CFBundleName</key>
    <string>CleanMac</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>15.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
EOF
if pkill -x CleanMac 2>/dev/null; then
    echo "Stopped previous instance."
fi
open "$APP"
echo "CleanMac launched. Quit with Cmd+Q."
