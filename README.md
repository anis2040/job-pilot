# job-scraper

Fetches job listings from LinkedIn, Jobicy, Himalayas, and Greenhouse, and generates tailored ATS-optimized resumes and cover letters with one click using Claude or Gemini. Supports multiple profiles so different people (or different job tracks) can share one installation.

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

### 2. Run

Activate the virtualenv (every new terminal session):

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Start the app:

```bash
python web.py
```

Open **http://localhost:5050** — the setup wizard launches automatically on first run and guides you through the rest.

---

## Setup Wizard

The wizard runs on first launch and covers 3 steps:

**Step 1 — Prerequisites:** Checks Python, Node.js, AI CLI, and pdflatex. Installs missing tools with one click (macOS/Linux). Shows platform-specific instructions for Windows.

**Step 2 — Profile:** Fill in your experience, education, and certifications using a structured form. Upload an existing PDF or DOCX resume to autofill. The AI uses this exclusively to build resumes — it never invents anything not listed here.

**Step 3 — Done:** If you filled in a profile, one click auto-configures search queries from your profile data. Or skip straight to the job list with a quick title + location form.

---

## Features

**Multi-profile support** — click the avatar in the top-right to switch between profiles, add a new one, or manage existing ones. Each profile has its own jobs database, search config, and resumes folder.

**Job list** — sortable and searchable table of all fetched listings. Filter by title, company, location, source, or remote type.

**Build CV** — click ▶ Build CV on any job. The AI generates a tailored ATS-optimized resume as a PDF. Once done, click 📄 Open CV to view it.

**Write Letter** — appears after a CV is built. Generates a matching cover letter that reads the resume for consistency.

**⚙ Search Settings** — edit search queries, sources, locations, and filters directly from the job list without touching any files.

**Profile Settings** — click your avatar → Manage Profiles → click a profile row. GitHub-settings-style page with sections for profile editing, search configuration, and danger zone actions.

---

## Sources

| Source | Type |
|---|---|
| LinkedIn | Scrapes public job search results |
| Jobicy | Remote-first jobs, public JSON API |
| Himalayas | Remote jobs, public JSON API |
| Greenhouse | Per-company job board API (no key required) |

---

## AI CLI

The app auto-detects which CLI is installed. Claude is tried first; Gemini is used if Claude is not found.

**Claude** — free tier available, login with your Anthropic account:
```bash
npm install -g @anthropic-ai/claude-code
claude login
```

**Gemini** — free API key from [Google AI Studio](https://aistudio.google.com/apikey):
```bash
npm install -g @google/gemini-cli
export GEMINI_API_KEY="your_key_here"   # macOS/Linux
$env:GEMINI_API_KEY="your_key_here"     # Windows
```

---

## PDF Compiler

Resumes and cover letters are compiled from LaTeX to PDF.

**macOS:**
```bash
brew install --cask basictex
sudo /usr/local/texlive/2026basic/bin/universal-darwin/tlmgr install titlesec enumitem hyperref geometry parskip microtype
```

**Windows:** Download [MiKTeX](https://miktex.org/download) — installs missing packages automatically on first use.

**Linux:**
```bash
sudo apt install texlive-latex-extra
```

---

## Output

Generated files are saved under each profile's folder:

```
profiles/<name>/
  resumes/
    <CompanyName>/
      <Name>_Resume.pdf
      <Name>_Resume.tex
      <Name>_Cover_Letter.pdf   (if generated)
      job_description.txt
  profile.md
  config.yaml
  state.db
```

---

## Reset

Clear all jobs for the current profile from the UI: **avatar → Manage Profiles → profile row → Danger Zone → Clear jobs**.

Or from the terminal (macOS/Linux):
```bash
source .venv/bin/activate
python -c "from job.db import clear_all_jobs; clear_all_jobs(); print('cleared')"
```
