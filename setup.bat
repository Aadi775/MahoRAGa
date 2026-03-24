@echo off
setlocal

echo ==========================================
echo  MahoRAGa Knowledge Graph - Setup Script  
echo ==========================================

echo [1/3] Creating Python virtual environment...
if not exist ".venv" (
    python -m venv .venv
)

echo [2/3] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/3] Installing dependencies...
python -m pip install --upgrade pip
pip install -e .

echo ==========================================
echo  Setup complete! The MCP server is ready.
echo  Add to your MCP client config:
echo    {"mcpServers": {"mahoraga": {"command": ".venv\Scripts\mahoraga-kg.exe"}}}
echo ==========================================

endlocal
