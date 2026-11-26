@echo off
cd /d "%~dp0"
if not exist .venv (py -m venv .venv)
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 (echo Could not install dependencies & pause & exit /b 1)
echo.
echo Open http://localhost:8000 in Chrome/Edge after server starts.
echo.
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
pause
