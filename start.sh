#!/bin/bash
# Launch job-scraper — auto-installs Python if missing, then starts the app.

cd "$(dirname "$0")"
OS="$(uname -s)"

RED='\033[0;31m'; NC='\033[0m'
err()  { echo -e "${RED}  [ERROR]${NC} $*"; }
info() { echo "  $*"; }

echo ""
echo "  ============================================="
echo "   job-scraper"
echo "  ============================================="
echo ""

# ── 1. Refresh PATH with known Python / Homebrew locations ────────────────────
# Covers the case where Python or brew was just installed in this session.
refresh_path() {
    for p in /opt/homebrew/bin \
              /opt/homebrew/opt/python@3.11/bin \
              /usr/local/bin \
              /usr/local/opt/python@3.11/bin \
              "$HOME/.pyenv/bin"; do
        [[ -d "$p" ]] && export PATH="$p:$PATH"
    done
    hash -r 2>/dev/null || true
}
refresh_path

# ── 2. Find a usable Python 3.9+ ──────────────────────────────────────────────
find_python() {
    PYTHON=""
    PY_VER=""
    for cmd in python3.13 python3.12 python3.11 python3.10 python3.9 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            ver="$($cmd --version 2>&1 | awk '{print $2}')"
            maj="${ver%%.*}"
            min="${ver#*.}"; min="${min%%.*}"
            if [[ "$maj" -gt 3 ]] || [[ "$maj" -eq 3 && "$min" -ge 9 ]]; then
                PYTHON="$cmd"
                PY_VER="$ver"
                return 0
            fi
        fi
    done
    return 1
}
find_python

# ── 3. Auto-install Python if not found ───────────────────────────────────────
if [[ -z "$PYTHON" ]]; then
    info "Python 3.9+ not found. Installing automatically..."
    info "(One-time step — takes about a minute)"
    echo ""

    if [[ "$OS" == "Darwin" ]]; then
        if ! command -v brew &>/dev/null; then
            info "Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            refresh_path
            if ! command -v brew &>/dev/null; then
                err "Homebrew install failed."
                err "Install Python manually from https://www.python.org/downloads/ then run ./start.sh again."
                exit 1
            fi
        fi
        info "Installing Python 3.11 via Homebrew..."
        brew install python@3.11
        refresh_path

    elif command -v apt-get &>/dev/null; then
        info "Installing Python 3 via apt..."
        sudo apt-get update -qq && sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v dnf &>/dev/null; then
        info "Installing Python 3 via dnf..."
        sudo dnf install -y python3 python3-pip
    elif command -v yum &>/dev/null; then
        info "Installing Python 3 via yum..."
        sudo yum install -y python3 python3-pip
    elif command -v pacman &>/dev/null; then
        info "Installing Python 3 via pacman..."
        sudo pacman -Sy --noconfirm python python-pip
    else
        err "No supported package manager found (tried apt, dnf, yum, pacman)."
        err "Install Python 3.9+ manually from https://www.python.org/downloads/ then run ./start.sh again."
        exit 1
    fi

    refresh_path
    find_python

    if [[ -z "$PYTHON" ]]; then
        err "Could not find Python 3.9+ after install."
        err "Install it manually from https://www.python.org/downloads/ then run ./start.sh again."
        exit 1
    fi
fi

info "Python: $PYTHON ($PY_VER)"

# ── 4. Create virtual environment ─────────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv || {
        err "Could not create virtual environment."
        err "Try running: $PYTHON -m pip install --user virtualenv"
        exit 1
    }
fi

# ── 5. Activate ────────────────────────────────────────────────────────────────
# shellcheck disable=SC1091
source .venv/bin/activate || {
    err "Could not activate virtual environment. Try deleting the .venv folder and running ./start.sh again."
    exit 1
}

# ── 6. Install dependencies ────────────────────────────────────────────────────
if ! python -c "import flask" &>/dev/null; then
    info "Installing dependencies (first run — takes about a minute)..."
    pip install -r requirements.txt -q || {
        err "pip install failed. Check your internet connection and try again."
        exit 1
    }
    info "Dependencies installed."
fi

# ── 7. Open browser after Flask starts ────────────────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
    (sleep 3 && open "http://localhost:5050") &
else
    (sleep 3 && (xdg-open "http://localhost:5050" 2>/dev/null || \
                 sensible-browser "http://localhost:5050" 2>/dev/null || \
                 x-www-browser "http://localhost:5050" 2>/dev/null || true)) &
fi

# ── 8. Launch ──────────────────────────────────────────────────────────────────
echo ""
info "Starting job-scraper at http://localhost:5050"
info "Browser will open automatically. Press Ctrl+C to stop the app."
echo ""
python web.py
