#!/bin/bash
# Projetmap Installer
# Installs projetmap to ~/.agents/skills/projetmap

set -e

INSTALL_DIR="${1:-$HOME/.agents/skills/projetmap}"
REPO_URL="https://github.com/360integree/projetmap.git"

echo "🗺️  Installing Projetmap..."

# Check if already installed
if [ -d "$INSTALL_DIR" ]; then
    echo "⚠️  Projetmap already exists at $INSTALL_DIR"
    read -p "Update? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$INSTALL_DIR"
        git pull
        echo "✅ Updated!"
    fi
    exit 0
fi

# Clone
echo "📥 Cloning to $INSTALL_DIR..."
git clone "$REPO_URL" "$INSTALL_DIR"

# Make bin executable
chmod +x "$INSTALL_DIR/bin/projetmap"

# Add to PATH (if not already)
if [[ ":$PATH:" != *":$INSTALL_DIR/bin:"* ]]; then
    echo ""
    echo "Add to your shell profile:"
    echo "  export PATH=\"\$PATH:$INSTALL_DIR/bin\""
fi

echo ""
echo "✅ Installed! Usage:"
echo "  projetmap .                    # Scan current directory"
echo "  projetmap . --journeys         # Scan with user journeys"
echo "  projetmap . --behavioral       # Scan with behavioral analysis"
