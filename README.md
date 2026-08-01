# job-scraper

Fetches job listings from LinkedIn, Jobicy, Himalayas, and Greenhouse, and generates tailored ATS-optimized resumes and cover letters with one click using Claude or Gemini. Supports multiple profiles so different people (or different job tracks) can share one installation.

---

## Before you start

Install these three things manually. Everything else (AI CLI, pdflatex, your profile) is handled by the in-browser setup wizard.

### Python 3.9+

**macOS:** `brew install python@3.11` or download from [python.org/downloads](https://www.python.org/downloads/)

**Windows:** Download from [python.org/downloads](https://www.python.org/downloads/) — check **"Add Python to PATH"** on the first installer screen.

If Python isn't found after install, add it to PATH manually:
- **macOS:** `echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc`
- **Windows:** System Properties → Environment Variables → add `C:\Users\<You>\AppData\Local\Programs\Python\Python311\` to Path

**Linux:** `sudo apt install python3.11 python3.11-venv`

### Git

**macOS:** pre-installed, or `brew install git` · **Windows:** [git-scm.com/download/win](https://git-scm.com/download/win) · **Linux:** `sudo apt install git`

### Node.js 18+ *(only needed for CV/cover letter generation)*

Not required to run the app or fetch jobs. The setup wizard will prompt you if it's missing when you try to build a resume.

**macOS:** `brew install node` · **Windows:** [nodejs.org/en/download](https://nodejs.org/en/download) or `winget install OpenJS.NodeJS.LTS` · **Linux:** `sudo apt install nodejs npm`

---

## Install & Run

```bash
git clone https://github.com/anis2040/job-scraper.git
cd job-scraper
```

Then run the start script — it handles the rest automatically (creates venv, installs dependencies, starts the app):

**macOS / Linux:**
```bash
./start.sh
```

**Windows:**
```powershell
start.bat
```

Open **http://localhost:5050** — the setup wizard launches on first run.

> Run the same script every time you want to start the app.
> If you get a permission error: `chmod +x start.sh`

---

## Setup Wizard

Runs automatically on first launch. 3 steps:

**Step 1 — Prerequisites:** Checks Node.js, AI CLI (Claude or Gemini), and pdflatex. Shows install instructions for anything missing.

**Step 2 — Profile:** Fill in your experience, education, and certifications using a structured form, or upload an existing PDF/DOCX resume to autofill.

**Step 3 — Done:** Auto-configure searches from your profile with one click, or enter a job title and location to start fetching immediately.

---

## Features

**Multi-profile** — avatar in the top-right switches between profiles, each with its own jobs, search config, and resumes.

**Job list** — sortable and searchable. Filter by title, company, location, source, or remote type.

**Build CV** — click ▶ Build CV on any job to generate a tailored ATS-optimized resume PDF.

**Write Letter** — appears after a CV is built. Generates a matching cover letter.

**Search Settings** — edit queries, sources, locations, and filters from the UI without touching files.

**Profile Settings** — avatar → Manage Profiles → click a profile row. Edit profile, search config, or clear data.

---

## Sources

| Source | Coverage |
|---|---|
| LinkedIn | Large job market, public search |
| Jobicy | Remote-first jobs, public API |
| Himalayas | Remote jobs, public API |
| Greenhouse | Per-company boards, no key required |

---

## Output

Resumes and cover letters are saved per profile:

```
profiles/<name>/resumes/<CompanyName>/
  <Name>_Resume.pdf
  <Name>_Cover_Letter.pdf
  <Name>_Resume.tex
  job_description.txt
```

---

## Reset

Clear jobs from the UI: **avatar → Manage Profiles → profile row → Danger Zone → Clear jobs**
