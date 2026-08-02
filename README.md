# JobPilot AI

Your AI copilot for the job hunt — from discovery to offer. JobPilot AI fetches
listings from LinkedIn, StepStone, Greenhouse, GermanTechJobs, Berlin Startup
Jobs, Jobicy, and Himalayas, then generates tailored, ATS-optimized resumes and
cover letters with one click using Claude or Gemini. Supports multiple profiles
so different people (or different job tracks) can share one installation.

---

## Install & Run

```bash
git clone https://github.com/anis2040/job-scraper.git
cd job-scraper
```

**First time only** — installs Python if missing, sets up the environment, then launches the app:

| macOS / Linux | Windows |
|---|---|
| `./setup.sh` | `setup.bat` |

> **macOS/Linux:** if you get a permission error run `chmod +x setup.sh start.sh` first.

**Every time after that** — skips all setup, starts instantly:

| macOS / Linux | Windows |
|---|---|
| `./start.sh` | `start.bat` |

---

## Setup Wizard

Runs automatically on first launch. 3 steps:

**Step 1 — Prerequisites:** Checks Node.js, AI CLI (Claude or Gemini), and pdflatex. Shows install instructions for anything missing.

> **Windows — pdflatex:** Install [MiKTeX](https://miktex.org/download). During its setup wizard, set *"Install missing packages on-the-fly"* to **Yes** — this prevents the first PDF build from failing or hanging while waiting for missing LaTeX packages.

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
