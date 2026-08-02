#!/bin/bash
# First-time setup: installs Python if needed, creates venv, installs deps, then starts the app.

cd "$(dirname "$0")"
OS="$(uname -s)"

RED='\033[0;31m'; NC='\033[0m'
err()  { echo -e "${RED}  [ERROR]${NC} $*"; }
info() { echo "  $*"; }

echo ""
echo "  ============================================="
echo "   job-scraper — setup"
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
    info "(One-time step — takes about a minute)"
    echo ""

    if [[ "$OS" == "Darwin" ]]; then
        if ! command -v brew &>/dev/null; then
            info "Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            refresh_path
            if ! command -v brew &>/dev/null; then
                err "Homebrew install failed."
                err "Install Python manually from https://www.python.org/downloads/ then run ./setup.sh again."
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
        err "Install Python 3.9+ manually from https://www.python.org/downloads/ then run ./setup.sh again."
        exit 1
    fi

    refresh_path
    find_python

    if [[ -z "$PYTHON" ]]; then
        err "Could not find Python 3.9+ after install."
        err "Install it manually from https://www.python.org/downloads/ then run ./setup.sh again."
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
        info "[WARN] No supported package manager — skipping Node.js install."
        info "       Install manually from https://nodejs.org/ if you want Gemini/Claude CLI support."
    fi
    hash -r 2>/dev/null || true
fi
if command -v node &>/dev/null; then
    info "Node.js: $(node --version)"
fi

# ── 5. Install pdflatex if missing ────────────────────────────────────────────
if ! command -v pdflatex &>/dev/null; then
    info "pdflatex not found. Installing automatically..."
    info "(Required to compile resumes and cover letters to PDF)"
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
        info "[WARN] No supported package manager — skipping pdflatex install."
        info "       Install manually from https://tug.org/texlive/ if you need PDF generation."
    fi
    hash -r 2>/dev/null || true
fi
if command -v pdflatex &>/dev/null; then
    info "pdflatex: $(pdflatex --version | head -1)"
else
    info "[WARN] pdflatex still not found. PDF generation will not work."
fi

# ── 6. Create virtual environment ─────────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv || {
        err "Could not create virtual environment."
        exit 1
    }
fi

# ── 7. Activate ────────────────────────────────────────────────────────────────
# shellcheck disable=SC1091
source .venv/bin/activate || {
    err "Could not activate virtual environment. Try deleting the .venv folder and running ./setup.sh again."
    exit 1
}

# ── 8. Install dependencies ────────────────────────────────────────────────────
info "Installing dependencies..."
pip install -r requirements.txt -q || {
    err "pip install failed. Check your internet connection and try again."
    exit 1
}
info "Dependencies installed."

# ── 9. Open browser after Flask starts ────────────────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
    (sleep 3 && open "http://localhost:5050") &
else
    (sleep 3 && (xdg-open "http://localhost:5050" 2>/dev/null || \
                 sensible-browser "http://localhost:5050" 2>/dev/null || \
                 x-www-browser "http://localhost:5050" 2>/dev/null || true)) &
fi

# ── 10. Launch ──────────────────────────────────────────────────────────────────
echo ""
info "Setup complete. Starting job-scraper at http://localhost:5050"
info "Browser will open automatically. Press Ctrl+C to stop the app."
echo ""
python web.py
