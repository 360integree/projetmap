#!/bin/bash
# Codemap — installer
set -e

echo "🗺️  Installing Codemap..."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install
source .venv/bin/activate
pip install -e ".[full]"

echo ""
echo "✅ Codemap installed!"
echo ""
echo "Usage:"
echo "  python -m codemap <path>              # Scan a project"
echo "  python -m codemap <path> --behavioral  # With behavioral analysis"
echo "  python -m codemap mcp                  # Start MCP server for IDEs"
echo ""
echo "Or add to PATH:"
echo "  export PATH=\"\$(pwd)/.venv/bin:\$PATH\""
echo "  codemap <path>"
