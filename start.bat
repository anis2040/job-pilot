@echo off
:: Launch job-scraper — creates venv and installs deps if needed, then starts the app.

cd /d "%~dp0"

:: Create venv if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

:: Activate
call .venv\Scripts\activate.bat

:: Install dependencies if flask is missing
python -c "import flask" 2>nul || (
    echo Installing dependencies...
    pip install -r requirements.txt -q
)

:: Start
echo Starting job-scraper at http://localhost:5050
python web.py
