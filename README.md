# job-scraper

Fetches job listings from LinkedIn, Jobicy, Himalayas, and Greenhouse, scores them by fit, and generates tailored ATS-optimized resumes and cover letters with one click using Claude or Gemini.

## Requirements

- Python 3.11+
- Node.js (for AI CLI)
- One of:
  - [Claude Code CLI](https://claude.ai/code) — `npm install -g @anthropic-ai/claude-code`
  - [Gemini CLI](https://github.com/google-gemini/gemini-cli) — `npm install -g @google/gemini-cli`

## Setup

### 1. Clone and install

```bash
git clone https://github.com/anis2040/job-scraper.git
cd job-scraper
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> If you get a "running scripts is disabled" error on Windows, run once as Administrator:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 2. Set up your profile

Copy the example profile and fill in your details:

```bash
cp resume-skill/references/profile.md.example resume-skill/references/profile.md
```

Edit `resume-skill/references/profile.md` with your experience, education, and certifications. This is the only source of truth the AI uses — it will never invent anything not listed here.

### 3. Set up your AI CLI

**Option A — Claude:**
```bash
npm install -g @anthropic-ai/claude-code
claude login
```

**Option B — Gemini:**
```bash
npm install -g @google/gemini-cli
```
Then set your API key (get one free at [aistudio.google.com](https://aistudio.google.com/apikey)):
```bash
# macOS / Linux
export GEMINI_API_KEY="your_key_here"

# Windows (PowerShell)
$env:GEMINI_API_KEY="your_key_here"
```
To make it permanent on Windows, add it via System Properties → Environment Variables.

The app auto-detects which CLI is installed. Claude is tried first; Gemini is used if Claude is not found.

### 4. Install BasicTeX (for PDF compilation)

Resumes and cover letters are compiled from LaTeX to PDF.

**macOS:**
```bash
brew install --cask basictex
sudo /usr/local/texlive/2026basic/bin/universal-darwin/tlmgr install titlesec enumitem hyperref geometry parskip microtype
```

**Windows:** Download and install [MiKTeX](https://miktex.org/download). It installs missing packages automatically on first use.

**Linux:**
```bash
sudo apt install texlive-latex-extra
```

---

## Run

Activate the virtualenv first (every new terminal session):

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Start the web UI:

```bash
python web.py
```

Open **http://localhost:5050** in your browser.

---

## Usage

**Fetch new jobs** — click ⟳ Fetch new jobs in the header. Jobs are scored and deduplicated automatically.

**Build CV** — click ▶ Build CV on any row. The AI generates a tailored resume for that job in the background. Once done, click 📄 Open CV to view the PDF.

**Write Letter** — appears once a CV is built. Generates a matching cover letter that reads the resume first for consistency.

**Applied / Skip** — mark jobs to move them to the Applied or Skipped tabs.

---

## Configuration

Edit `config.yaml` to change what roles you're searching for:

```yaml
searches:
  - name: "LinkedIn - Product Owner USA"
    source: linkedin          # linkedin | jobicy | himalayas | greenhouse
    query: "Product Owner"
    location: "United States"
    remote: true
    max_pages: 3

title_filter:                 # only keep jobs matching at least one of these
  - product owner
  - product manager
  - business analyst

blacklist:                    # drop jobs containing these words
  - internship
  - junior

company_blacklist:            # ignore these companies entirely
  - Accentuate Staffing
```

---

## Output

Generated files are saved per company:

```
resumes/<CompanyName>/
├── Yassine_Helaoui_Resume.pdf
├── Yassine_Helaoui_Resume.tex
├── Yassine_Helaoui_Cover_Letter.pdf   (if generated)
└── job_description.txt
```

---

## Reset

Clear all saved listings and start fresh:

```bash
# macOS / Linux
sqlite3 state.db "DELETE FROM jobs; DELETE FROM filter_log; DELETE FROM fetch_log;"

# Windows (PowerShell)
python -c "import sqlite3; c=sqlite3.connect('state.db'); c.execute('DELETE FROM jobs'); c.execute('DELETE FROM filter_log'); c.execute('DELETE FROM fetch_log'); c.commit()"
```
