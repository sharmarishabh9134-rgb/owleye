@echo off
REM One-click start for Windows. Needs Python 3.10 or newer (python.org).
REM Optional AI chat: set ANTHROPIC_API_KEY=your-key  (before running this file)
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add to PATH".
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
echo.
echo Open http://localhost:8000 in your browser. Press Ctrl+C to stop.
python -m uvicorn backend.app.main:app --port 8000
pause
