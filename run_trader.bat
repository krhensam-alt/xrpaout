@echo off
TITLE XRP AI TRADER SERVER
cd /d "%~dp0"

echo ===================================================
echo   XRP AI TRADER SYSTEM IS STARTING...
echo ===================================================
echo.
echo Dashboard: http://localhost:13151
echo External:  http://112.220.123.154:13151
echo AI Brain:  LM Studio (localhost:1234)
echo.

:: Execute uvicorn using the python in venv
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 13151

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Server failed to start.
    pause
)
