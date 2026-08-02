#!/bin/bash
# Run the test suite. Creates/activates the venv and ensures pytest is installed.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# Ensure pytest is available
python -c "import pytest" 2>/dev/null || {
    echo "Installing test dependencies..."
    pip install -r requirements.txt -q
}

# Run tests (pass any extra args through, e.g. ./run-tests.sh tests/test_db.py -v)
pytest "$@"
