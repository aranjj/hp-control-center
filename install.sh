#!/usr/bin/env bash
# HP Performance Control Center Installation Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing HP Performance Control Center ==="

# 1. Make scripts executable
chmod +x "$SCRIPT_DIR/app.py"
chmod +x "$SCRIPT_DIR/cli.py"
chmod +x "$SCRIPT_DIR/daemon/service.py"

# 2. Install desktop launcher & icons to user applications
mkdir -p "$HOME/.local/share/applications"
cp "$SCRIPT_DIR/hp-control-center.desktop" "$HOME/.local/share/applications/"
sed -i "s|/home/aran/Projects/Github/hp-control-center|$SCRIPT_DIR|g" "$HOME/.local/share/applications/hp-control-center.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# Install application icons
mkdir -p "$HOME/.local/share/icons"
cp -r "$SCRIPT_DIR/hicolor" "$HOME/.local/share/icons/"
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "[+] Desktop application launcher and icons installed."

# 3. Prompt or install systemd daemon
echo ""
if command -v pacman >/dev/null 2>&1; then
    echo "Tip: On Arch Linux, you can install as a native package with systemd service included:"
    echo "  makepkg -si"
    echo ""
fi
echo "To enable the background power-sync daemon (runs as root to defeat EC decay):"
echo "  sudo cp $SCRIPT_DIR/daemon/hp-control-daemon.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now hp-control-daemon"
echo ""
echo "[✓] Installation complete! You can run the app with:"
echo "    python3 $SCRIPT_DIR/app.py"
