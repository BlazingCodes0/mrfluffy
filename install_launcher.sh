#!/bin/bash
set -e
APP_DIR="$HOME/mrfluffy"
SHARE="$HOME/.local/share/applications"
DESK="$HOME/Desktop"

mkdir -p "$SHARE" "$DESK"

cat > "$SHARE/mrfluffy.desktop" << EOD
[Desktop Entry]
Version=1.0
Type=Application
Name=Mr.Fluffy
Comment=News + readout reader
Exec=python3 $APP_DIR/app.py
Icon=$APP_DIR/icon.svg
Terminal=false
Categories=Utility;
EOD

cp -f "$SHARE/mrfluffy.desktop" "$DESK/Mr.Fluffy.desktop"

chmod +x "$SHARE/mrfluffy.desktop" "$DESK/Mr.Fluffy.desktop" 2>/dev/null || true
chmod +x "$APP_DIR/app.py" 2>/dev/null || true

echo "Mr.Fluffy launchers created."
