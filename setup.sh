#!/bin/bash
set -e

echo "=========================================="
echo " MahoRAGa Knowledge Graph - Setup Script  "
echo "=========================================="

echo "[1/3] Creating Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "[2/3] Activating virtual environment..."
source .venv/bin/activate

echo "[3/3] Installing dependencies..."
pip install --upgrade pip
pip install -e .

echo "=========================================="
echo " Setup complete! The MCP server is ready."
echo ""
echo " Add this to your MCP client config:"
echo "   {\"mcpServers\": {\"mahoraga\": {\"command\": \"$(pwd)/.venv/bin/mahoraga-kg\"}}}"
echo "=========================================="
