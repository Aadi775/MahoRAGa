@echo off
setlocal

echo ==========================================
echo  MahoRAGa Knowledge Graph - Setup Script  
echo ==========================================

echo [1/4] Creating Python virtual environment...
if not exist ".venv" (
    python -m venv .venv
)

echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/4] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

echo [4/4] Setting up MCP Server...
python -m fastmcp install src.main:mcp --name "MahoRAGa Knowledge Graph"

echo ==========================================
echo  Setup complete! The MCP server is ready.
echo  Claude Desktop or Cursor will automatically
echo  connect to the knowledge graph.
echo ==========================================

endlocal
