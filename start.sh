#!/bin/bash
# Start job-scraper. Run setup.sh first if you haven't already.

cd "$(dirname "$0")"
OS="$(uname -s)"

if [[ ! -f ".venv/bin/activate" ]]; then
    echo "  [ERROR] Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ "$OS" == "Darwin" ]]; then
    (sleep 3 && open "http://localhost:5050") &
else
    (sleep 3 && (xdg-open "http://localhost:5050" 2>/dev/null || \
                 sensible-browser "http://localhost:5050" 2>/dev/null || \
                 x-www-browser "http://localhost:5050" 2>/dev/null || true)) &
fi

echo ""
echo "  Starting job-scraper at http://localhost:5050"
echo "  Browser will open automatically. Press Ctrl+C to stop the app."
echo ""
python web.py
