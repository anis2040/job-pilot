#!/bin/bash
# First-time setup: installs all deps (Python, Node.js, pdflatex, pip, npm) then starts the app.

cd "$(dirname "$0")"
OS="$(uname -s)"

RED='\033[0;31m'; YELLOW='\033[0;33m'; NC='\033[0m'
err()  { echo -e "${RED}  [ERROR]${NC} $*"; }
warn() { echo -e "${YELLOW}  [WARN]${NC} $*"; }
info() { echo "  $*"; }

echo ""
echo "  ============================================="
echo "   JobPilot AI — setup"
echo "  ============================================="
echo ""

# ── 1. Refresh PATH with known Python / Homebrew locations ────────────────────
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
    if [[ "$OS" == "Darwin" ]]; then
        if ! command -v brew &>/dev/null; then
            info "Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            refresh_path
        fi
        brew install python@3.11
        refresh_path
    elif command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3 python3-pip
    elif command -v yum &>/dev/null; then
        sudo yum install -y python3 python3-pip
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm python python-pip
    else
        err "No supported package manager found."
        err "Install Python 3.9+ manually from https://www.python.org/downloads/ then run ./setup-react.sh again."
        exit 1
    fi
    refresh_path
    find_python
    if [[ -z "$PYTHON" ]]; then
        err "Could not find Python 3.9+ after install."
        err "Install it manually from https://www.python.org/downloads/ then run ./setup-react.sh again."
        exit 1
    fi
fi
info "Python: $PYTHON ($PY_VER)"

# ── 4. Install Node.js if missing ─────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    info "Node.js not found. Installing automatically..."
    if [[ "$OS" == "Darwin" ]]; then
        brew install node
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y nodejs npm
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y nodejs npm
    elif command -v yum &>/dev/null; then
        sudo yum install -y nodejs npm
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm nodejs npm
    else
        err "No supported package manager found — cannot install Node.js automatically."
        err "Install Node.js manually from https://nodejs.org/ then run ./setup-react.sh again."
        exit 1
    fi
    hash -r 2>/dev/null || true
fi
if ! command -v node &>/dev/null; then
    err "Node.js not found after install."
    err "Open a new terminal and run ./setup-react.sh again, or install manually from https://nodejs.org/"
    exit 1
fi
info "Node.js: $(node --version)"

# ── 5. Install pdflatex if missing ────────────────────────────────────────────
if ! command -v pdflatex &>/dev/null; then
    info "pdflatex not found. Installing automatically..."
    info "(Required for PDF resume/cover letter generation)"
    if [[ "$OS" == "Darwin" ]]; then
        brew install --cask basictex
        eval "$(/usr/libexec/path_helper)"
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y texlive-latex-extra
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y texlive-latex texlive-collection-latexextra
    elif command -v yum &>/dev/null; then
        sudo yum install -y texlive-latex texlive-collection-latexextra
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm texlive-latexextra
    else
        warn "No supported package manager — skipping pdflatex install."
        warn "PDF generation will not work until pdflatex is installed."
    fi
    hash -r 2>/dev/null || true
fi
if command -v pdflatex &>/dev/null; then
    info "pdflatex: $(pdflatex --version | head -1)"
else
    warn "pdflatex still not found. PDF generation will not work."
fi

# ── 6. Create virtual environment ─────────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv || { err "Could not create virtual environment."; exit 1; }
fi

# ── 7. Activate ────────────────────────────────────────────────────────────────
# shellcheck disable=SC1091
source .venv/bin/activate || {
    err "Could not activate virtual environment. Try deleting .venv and running ./setup-react.sh again."
    exit 1
}

# ── 8. Install Python dependencies ────────────────────────────────────────────
info "Installing Python dependencies..."
pip install -r requirements.txt -q || { err "pip install failed. Check your internet connection and try again."; exit 1; }

# ── 9. Install frontend dependencies ──────────────────────────────────────────
info "Installing frontend dependencies..."
if [[ -f "frontend/package-lock.json" ]]; then
    npm ci --prefix frontend --include=optional || { err "npm ci failed. Check your internet connection and try again."; exit 1; }
else
    npm install --prefix frontend --include=optional || { err "npm install failed. Check your internet connection and try again."; exit 1; }
fi

# ── 10. Open browser after servers start ──────────────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
    (sleep 6 && open "http://localhost:5173") &
else
    (sleep 6 && (xdg-open "http://localhost:5173" 2>/dev/null || \
                 sensible-browser "http://localhost:5173" 2>/dev/null || \
                 x-www-browser "http://localhost:5173" 2>/dev/null || true)) &
fi

# ── 11. Launch both servers ────────────────────────────────────────────────────
echo ""
info "Setup complete. Starting JobPilot AI..."
info "  Backend:  http://localhost:5050"
info "  Frontend: http://localhost:5173"
info "Browser will open automatically. Press Ctrl+C to stop."
echo ""
node scripts/dev.mjs
