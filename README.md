# job-scraper

Fetches job listings from LinkedIn, Jobicy, Himalayas, and Greenhouse, and generates tailored ATS-optimized resumes and cover letters with one click using Claude or Gemini. Supports multiple profiles so different people (or different job tracks) can share one installation.

## Prerequisites

Before you start, install the following:

### Python 3.11+

**macOS:**
```bash
brew install python@3.11
```
Or download from [python.org/downloads](https://www.python.org/downloads/)

**Windows:**
Download and run the installer from [python.org/downloads](https://www.python.org/downloads/).
Check **"Add Python to PATH"** during install.

**Linux:**
```bash
sudo apt install python3.11 python3.11-venv
```

Verify: `python --version` or `python3 --version`

---

### Node.js 18+

Required to install the AI CLI (Claude or Gemini).

**macOS:**
```bash
brew install node
```

**Windows:**
Download and run the installer from [nodejs.org/en/download](https://nodejs.org/en/download) (LTS version recommended).
Or via winget:
```powershell
winget install OpenJS.NodeJS.LTS
```

**Linux:**
```bash
sudo apt install nodejs npm
```

Verify: `node --version`

---

### Git

**macOS:** comes pre-installed, or `brew install git`

**Windows:** download from [git-scm.com/download/win](https://git-scm.com/download/win)

**Linux:** `sudo apt install git`

---

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

Open **http://localhost:5050** — the setup wizard launches automatically and walks you through everything else (AI CLI, pdflatex, and your profile).

---

## Setup Wizard

The wizard runs on first launch and covers 3 steps:

**Step 1 — Prerequisites:** Checks Python, Node.js, AI CLI, and pdflatex.
- If the AI CLI (Claude or Gemini) is not installed, there is a one-click install button — no terminal needed.
- If pdflatex is not installed, there is a one-click install on macOS/Linux, and step-by-step instructions for Windows (MiKTeX).
- Node.js is required before you can install the AI CLI. Install it from the Prerequisites section above if it's missing.

**Step 2 — Profile:** Fill in your experience, education, and certifications using a structured form. Upload an existing PDF or DOCX resume to autofill. The AI uses this exclusively to build resumes — it never invents anything not listed here.

**Step 3 — Done:** If you filled in a profile, one click auto-configures search queries from your profile data. Or skip straight to the job list with a quick title + location form.

> **Everything after cloning — the AI CLI, pdflatex, and your profile — is set up through the wizard in the browser. You do not need to run any additional commands manually.**

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
