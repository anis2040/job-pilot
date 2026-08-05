@echo off
setlocal
title JobPilot AI
cd /d "%~dp0"

echo.
echo  =============================================
echo   JobPilot AI — starting
echo  =============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo  [ERROR] Setup not complete. Run setup-react.bat first.
    pause
    exit /b 1
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 6; Start-Process 'http://localhost:5173'"

echo   Backend:  http://localhost:5050
echo   Frontend: http://localhost:5173
echo.
echo   Browser will open automatically. Press Ctrl+C to stop.
echo.
node scripts\dev.mjs

echo.
echo  App stopped. Press any key to close this window.
pause >nul
endlocal
