#!/bin/sh
# Builds "Agent Board Menu.app" (the menu-bar buddy). Needs only the Xcode command line tools.
set -e
cd "$(dirname "$0")"
APP="Agent Board Menu.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O main.swift -o "$APP/Contents/MacOS/agent-board-menu"
[ -f "../notifier/Agent Board.app/Contents/Resources/AppIcon.icns" ] && cp "../notifier/Agent Board.app/Contents/Resources/AppIcon.icns" "$APP/Contents/Resources/"
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>com.agent-board.menubar</string>
  <key>CFBundleName</key><string>Agent Board Menu</string>
  <key>CFBundleExecutable</key><string>agent-board-menu</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
EOF
codesign --force --deep --sign - "$APP"
echo "Built $(pwd)/$APP"
