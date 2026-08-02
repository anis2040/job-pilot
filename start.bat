@echo off
setlocal EnableDelayedExpansion
title job-scraper
cd /d "%~dp0"

echo.
echo  =============================================
echo   job-scraper
echo  =============================================
echo.

:: ── 1. Inject known Python install dirs into PATH ────────────────────────────
:: Covers the case where Python was just installed but the terminal wasn't
:: reopened — no need to tell the user to open a new window.
call :refresh_python_path

:: ── 2. Find a usable Python ──────────────────────────────────────────────────
call :find_python

:: ── 3. Auto-install Python if still not found ────────────────────────────────
if not defined PYTHON (
    echo   Python 3.9+ not found. Installing automatically...
    echo   ^(One-time step — takes about a minute^)
    echo.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] winget is not available on this machine.
        echo  Please install Python manually from https://www.python.org/downloads/
        echo  Check "Add Python to PATH" on the first installer screen, then run start.bat again.
        pause
        exit /b 1
    )
    winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    echo.
    echo   Refreshing PATH after install...
    call :refresh_python_path
    call :find_python
)

if not defined PYTHON (
    echo.
    echo  [ERROR] Could not find Python 3.9+ after install.
    echo  Please install it manually from https://www.python.org/downloads/
    echo  Check "Add Python to PATH" on the first installer screen, then run start.bat again.
    pause
    exit /b 1
)

echo   Python: !PYTHON! ^(!PY_VER!^)

:: ── 4. Create virtual environment ────────────────────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo   Creating virtual environment...
    !PYTHON! -m venv .venv
    if errorlevel 1 (
        echo.
        echo  [ERROR] Could not create virtual environment.
        echo  Try deleting the .venv folder and running start.bat again.
        pause
        exit /b 1
    )
)

:: ── 5. Activate ───────────────────────────────────────────────────────────────
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo  [ERROR] Could not activate the virtual environment.
    echo  Try deleting the .venv folder and running start.bat again.
    pause
    exit /b 1
)

:: ── 6. Install dependencies ───────────────────────────────────────────────────
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo   Installing dependencies ^(first run — takes about a minute^)...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo.
        echo  [ERROR] pip install failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
    echo   Dependencies installed.
)

:: ── 7. Launch app and open browser ───────────────────────────────────────────
echo.
echo   Starting job-scraper...
echo   Browser will open automatically. Press Ctrl+C here to stop the app.
echo.

:: Open the browser after 3 s — gives Flask time to start
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 3; Start-Process 'http://localhost:5050'"

python web.py

echo.
echo  App stopped. Press any key to close this window.
pause >nul
endlocal
goto :eof


:: ════════════════════════════════════════════════════════════════════════════
:: Subroutines
:: ════════════════════════════════════════════════════════════════════════════

:refresh_python_path
:: Add all well-known Python install directories to the current session PATH.
:: Handles both per-user (%LOCALAPPDATA%) and system-wide (%PROGRAMFILES%) installs.
for %%V in (313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python%%V;%LOCALAPPDATA%\Programs\Python\Python%%V\Scripts;!PATH!"
    )
    if exist "%PROGRAMFILES%\Python%%V\python.exe" (
        set "PATH=%PROGRAMFILES%\Python%%V;%PROGRAMFILES%\Python%%V\Scripts;!PATH!"
    )
)
goto :eof


:find_python
set "PYTHON="
set "PY_VER="
set "PY_MAJ=0"
set "PY_MIN=0"
for %%C in (py python3 python) do (
    if not defined PYTHON (
        where %%C >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=2 delims= " %%V in ('%%C --version 2^>^&1') do set "PY_VER=%%V"
            for /f "tokens=1,2 delims=." %%A in ("!PY_VER!") do (
                set /a "PY_MAJ=%%A" 2>nul
                set /a "PY_MIN=%%B" 2>nul
            )
            if !PY_MAJ! gtr 3 set "PYTHON=%%C"
            if !PY_MAJ! equ 3 if !PY_MIN! geq 9 set "PYTHON=%%C"
        )
    )
)
goto :eof
