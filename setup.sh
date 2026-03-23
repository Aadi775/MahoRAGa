#!/bin/bash
set -e

echo "=========================================="
echo " MahoRAGa Knowledge Graph - Setup Script  "
echo "=========================================="

echo "[1/4] Creating Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "[2/4] Activating virtual environment..."
source .venv/bin/activate

echo "[3/4] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

echo "[4/4] Setting up MCP Server..."
# FastMCP CLI installs the MCP server config into Claude Desktop/Cursor
python -m fastmcp install src.main:mcp --name "MahoRAGa Knowledge Graph"

echo "=========================================="
echo " Setup complete! The MCP server is ready."
echo " Claude Desktop or Cursor will automatically"
echo " connect to the knowledge graph."
echo "=========================================="
