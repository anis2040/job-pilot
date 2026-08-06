@echo off
setlocal EnableDelayedExpansion
title JobPilot AI
cd /d "%~dp0"

echo.
echo  =============================================
echo   JobPilot AI — one-click launcher
echo  =============================================
echo.

:: ── 1. Inject known Python install dirs into PATH ────────────────────────────
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
        echo  Check "Add Python to PATH" on the first installer screen, then run setup-react.bat again.
        pause
        exit /b 1
    )
    winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    echo.
    echo   Refreshing PATH after Python install...
    call :refresh_python_path
    call :find_python
)

if not defined PYTHON (
    echo.
    echo  [ERROR] Could not find Python 3.9+ after install.
    echo  Please install it manually from https://www.python.org/downloads/
    echo  Check "Add Python to PATH" on the first installer screen, then run setup-react.bat again.
    pause
    exit /b 1
)
echo   Python: !PYTHON! ^(!PY_VER!^)

:: ── 4. Install Node.js if missing ────────────────────────────────────────────
call :refresh_node_path
where node >nul 2>&1
if errorlevel 1 (
    echo   Node.js not found. Installing automatically...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] winget not available — cannot install Node.js automatically.
        echo  Please install Node.js from https://nodejs.org/ then run setup-react.bat again.
        pause
        exit /b 1
    )
    winget install --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
    echo   Refreshing PATH after Node.js install...
    call :refresh_node_path
)
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Node.js not found after install.
    echo  Close this window, open a new one, and run setup-react.bat again.
    pause
    exit /b 1
)
for /f "tokens=*" %%V in ('node --version 2^>^&1') do echo   Node.js: %%V
where npm >nul 2>&1
if errorlevel 1 (
    echo   npm not found after Node.js check. Refreshing PATH again...
    call :refresh_node_path
)
where npm >nul 2>&1
if errorlevel 1 (
    echo   npm still not found. Installing or repairing Node.js LTS with winget...
    where winget >nul 2>&1
    if not errorlevel 1 (
        winget install --id OpenJS.NodeJS.LTS --exact --silent --accept-package-agreements --accept-source-agreements
        call :refresh_node_path
    )
)
where npm >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [WARN] npm is not visible on PATH yet.
    echo         The app launcher will try Node.js's bundled npm directly.
) else (
    for /f "tokens=*" %%V in ('npm --version 2^>^&1') do echo   npm: %%V
)

:: ── 5. Install MiKTeX (pdflatex) if missing ──────────────────────────────────
where pdflatex >nul 2>&1
if errorlevel 1 (
    echo   pdflatex not found. Installing MiKTeX automatically...
    echo   ^(Required for PDF resume/cover letter generation^)
    where winget >nul 2>&1
    if not errorlevel 1 (
        winget install --id MiKTeX.MiKTeX --silent --accept-package-agreements --accept-source-agreements
        for %%D in (
            "%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64"
            "%PROGRAMFILES%\MiKTeX\miktex\bin\x64"
            "%PROGRAMFILES(X86)%\MiKTeX\miktex\bin\x64"
        ) do (
            if exist "%%~D\pdflatex.exe" set "PATH=%%~D;!PATH!"
        )
    ) else (
        echo  [WARN] winget not available — skipping MiKTeX install.
        echo         PDF generation will not work until pdflatex is installed.
    )
)
where pdflatex >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%V in ('pdflatex --version 2^>^&1 ^| findstr /i "MiKTeX pdfTeX"') do echo   pdflatex: %%V
) else (
    echo  [WARN] pdflatex not found. PDF generation will not work.
)

:: ── 6. Open browser once the frontend server is actually ready ─────────────
start "" powershell -NoProfile -WindowStyle Hidden -Command "while (-not (Test-NetConnection -ComputerName localhost -Port 5173 -InformationLevel Quiet -WarningAction SilentlyContinue)) { Start-Sleep 1 }; Start-Process 'http://localhost:5173'"

:: ── 7. Start everything via dev.mjs (venv + pip + npm + both servers) ────────
echo.
echo   Installing dependencies and starting servers...
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
goto :eof


:: ════════════════════════════════════════════════════════════════════════════
:: Subroutines
:: ════════════════════════════════════════════════════════════════════════════

:refresh_python_path
for %%V in (313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python%%V;%LOCALAPPDATA%\Programs\Python\Python%%V\Scripts;!PATH!"
    )
    if exist "%PROGRAMFILES%\Python%%V\python.exe" (
        set "PATH=%PROGRAMFILES%\Python%%V;%PROGRAMFILES%\Python%%V\Scripts;!PATH!"
    )
)
goto :eof


:refresh_node_path
:: winget writes the updated PATH to the registry, but this already-running
:: shell won't see it — so re-read PATH from both registry hives (machine + user)
:: and merge it in. This catches Node wherever winget put it, not just the known
:: dirs below.
for /f "skip=2 tokens=2,*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "PATH=!PATH!;%%B"
for /f "skip=2 tokens=2,*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "PATH=!PATH!;%%B"
:: Fast path / fallback: prepend well-known Node install dirs if present.
for %%D in (
    "%PROGRAMFILES%\nodejs"
    "%PROGRAMFILES(X86)%\nodejs"
    "%LOCALAPPDATA%\Programs\nodejs"
    "%APPDATA%\nvm\current"
) do (
    if exist "%%~D\node.exe" set "PATH=%%~D;!PATH!"
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
