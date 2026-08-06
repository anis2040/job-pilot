#!/bin/bash
# Start JobPilot AI. Run setup-react.sh first if you haven't already.

cd "$(dirname "$0")"
OS="$(uname -s)"

if [[ ! -f ".venv/bin/activate" ]]; then
    echo "  [ERROR] Setup not complete. Run ./setup-react.sh first."
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ "$OS" == "Darwin" ]]; then
    (until curl -s http://localhost:5173 >/dev/null 2>&1; do sleep 1; done; open "http://localhost:5173") &
else
    (until curl -s http://localhost:5173 >/dev/null 2>&1; do sleep 1; done
     xdg-open "http://localhost:5173" 2>/dev/null || \
     sensible-browser "http://localhost:5173" 2>/dev/null || \
     x-www-browser "http://localhost:5173" 2>/dev/null || true) &
fi

echo ""
echo "  Starting JobPilot AI..."
echo "    Backend:  http://localhost:5050"
echo "    Frontend: http://localhost:5173"
echo "  Browser will open automatically. Press Ctrl+C to stop."
echo ""
node scripts/dev.mjs
