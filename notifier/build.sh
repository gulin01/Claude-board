#!/bin/sh
# Builds "Agent Board.app" (the notifier) next to this script. Needs only the Xcode command line tools.
set -e
cd "$(dirname "$0")"
APP="Agent Board.app"
rm -rf "$APP" build
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" build/AppIcon.iconset

swiftc -O main.swift -o "$APP/Contents/MacOS/agent-board-notify"
swiftc icon.swift -o build/icon && build/icon build/AppIcon.iconset
iconutil -c icns build/AppIcon.iconset -o "$APP/Contents/Resources/AppIcon.icns"
for s in Glass Ping Hero Pop Tink Submarine; do cp "/System/Library/Sounds/$s.aiff" "$APP/Contents/Resources/"; done

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>com.agent-board.notifier</string>
  <key>CFBundleName</key><string>Agent Board</string>
  <key>CFBundleDisplayName</key><string>Agent Board</string>
  <key>CFBundleExecutable</key><string>agent-board-notify</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSUserNotificationAlertStyle</key><string>alert</string>
</dict>
</plist>
EOF
codesign --force --deep --sign - "$APP"
rm -rf build
# Register with Launch Services so clicks on notifications relaunch this app.
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
echo "Built $(pwd)/$APP"
