#!/bin/bash
# Launch job-scraper — creates venv and installs deps if needed, then starts the app.

set -e
cd "$(dirname "$0")"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install / update dependencies silently if anything is missing
python -c "import flask" 2>/dev/null || {
    echo "Installing dependencies..."
    pip install -r requirements.txt -q
}

# Start
echo "Starting job-scraper at http://localhost:5050"
python web.py
