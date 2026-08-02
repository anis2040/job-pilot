@echo off
setlocal
title job-scraper
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo  First-time setup needed. Running setup.bat...
    echo.
    call "%~dp0setup.bat"
    exit /b
)

call .venv\Scripts\activate.bat

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 3; Start-Process 'http://localhost:5050'"

echo.
echo  Starting job-scraper at http://localhost:5050
echo  Browser will open automatically. Press Ctrl+C here to stop the app.
echo.

python web.py

echo.
echo  App stopped. Press any key to close this window.
pause >nul
endlocal
