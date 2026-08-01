# job-scraper — Job Hunt Automator

Fetches job listings from LinkedIn, Jobicy, and Himalayas, filters out irrelevant roles, scores them by fit, and lets you generate tailored ATS-optimized resumes with one click. Includes both a web UI and a CLI.

## Sources

| Source | Coverage |
|---|---|
| `linkedin` | Large US job market, scrapes public search results |
| `jobicy` | Remote-first US jobs, public JSON API |
| `himalayas` | Remote US jobs, public JSON API |

All sources return only US-based or US-remote jobs.

## Requirements

- Python 3.11+
- [Claude Code CLI](https://claude.ai/code) (`claude` command) — required for resume generation

## Setup (macOS/Linux)

Run once:

```bash
cd ~/Downloads/job-scraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Every new terminal session:

```bash
cd ~/Downloads/job-scraper
source .venv/bin/activate
```

## Windows Setup

**One-time setup:**

```powershell
cd $HOME\Downloads\job-scraper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Every new terminal session:**

```powershell
cd $HOME\Downloads\job-scraper
.venv\Scripts\activate
```

> If you get a "running scripts is disabled" error, run this once in PowerShell as Administrator:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

---

## Web UI (recommended)

Start the server:

```bash
python web.py
```

Then open **http://localhost:5050** in your browser.

> Port 5050 is used because macOS reserves port 5000 for AirPlay Receiver.

### Web UI features

**Jobs table** — shows all pending listings sorted by fit score, with columns for Score, Title, Company, Remote, Location, Salary, Experience, Age, and CV status.

**Tabs** — switch between Pending, Applied, and Skipped listings.

**▶ Build CV button** — click on any row to generate a tailored resume for that job:
1. Fetches the full job description if not already available
2. Runs the resume skill in the background using `claude -p`
3. Button shows a spinner while building
4. Once done, shows a **📄 Open CV** link — click to open the PDF in the browser

**✓ Applied / ✗ Skip buttons** — mark a job as applied or skipped; it moves to the relevant tab instantly.

**↩ Restore** — undo an applied/skipped action from the Applied or Skipped tabs.

**⟳ Fetch new jobs** button — triggers a fresh fetch from all sources with a live progress message. New rows appear automatically when done.

**Auto-refresh** — the table refreshes every 30 seconds in the background.

---

## Configuration

Edit `config.yaml`:

```yaml
searches:
  - name: "LinkedIn - Product Owner USA"
    source: linkedin          # linkedin | jobicy | himalayas
    query: "Product Owner"
    location: "United States"
    remote: true
    max_pages: 3

title_filter:                 # only keep jobs whose title matches at least one keyword
  - product owner
  - product manager
  - business analyst

blacklist:                    # filter by keyword in title or description
  - internship
  - junior

company_blacklist:            # filter out specific companies entirely
  - Accentuate Staffing
```

**To change the role:** update `query` in each search entry and add/update `title_filter` accordingly.

---

## CLI Commands

All commands require the virtualenv to be activated first.

### `fetch` — Pull new listings

```bash
python -m job.cli fetch
```

Scrapes all sources, applies filters, deduplicates across sources, scores each job, and saves new listings. Fires a macOS notification if new jobs are found. Warns if last fetch was more than 24h ago.

### `list` — Show listings by status

```bash
python -m job.cli list                   # pending (default)
python -m job.cli list --status applied
python -m job.cli list --status skipped
```

### `unique` — Deduplicated view

```bash
python -m job.cli unique
```

Shows one listing per company+title, sorted by fit score. Useful when the same job appears on multiple sources.

### `resume` — Generate tailored resumes

```bash
python -m job.cli resume              # top 5 pending jobs
python -m job.cli resume --limit 10
```

For each job: fetches the description if missing, runs the resume skill, opens the job URL in your browser. Resumes are saved to `resumes/<CompanyName>/`.

### `open` — Open a job in the browser

```bash
python -m job.cli open li_4432695491
```

### `done` / `skip` — Update status

```bash
python -m job.cli done li_4432695491   # mark as applied
python -m job.cli skip li_4432695491   # dismiss
```

Job ID prefixes: `li_` = LinkedIn, `jc_` = Jobicy, `hi_` = Himalayas.

### `stats` — View counts and fetch history

```bash
python -m job.cli stats
```

Shows counts per status and when each source was last fetched (warns if stale).

---

## Fit Score

Each job gets a score from 0–100 when fetched:

| Signal | Points |
|---|---|
| Remote | +10 |
| Hybrid | +5 |
| PO/Agile keywords in description | up to +20 |
| Senior/Lead title signals | +10 |
| Salary ≥ $120k | +10 |
| Salary ≥ $90k | +5 |
| Has a description | +5 |
| Exec/clearance signals | −20 |

Jobs are displayed sorted by score (highest first) in both the web UI and `unique` command.

---

## Resume output

Resumes are saved inside the project:

```
resumes/<CompanyName>/
├── Yassine_Helaoui_Resume.pdf
├── Yassine_Helaoui_Resume.tex
└── job_description.txt
```

The resume skill used is the local copy at `resume-skill/` — edit `resume-skill/SKILL.md` and `resume-skill/references/profile.md` to update your profile or instructions.

---

## Reset

Clear all saved listings and start fresh:

```bash
sqlite3 state.db "DELETE FROM jobs; DELETE FROM filter_log; DELETE FROM fetch_log;"
```

---

## Automation (optional)

**macOS/Linux** — auto-fetch every 30 minutes via cron:

```bash
crontab -e
# Add:
*/30 * * * * cd ~/Downloads/job-scraper && .venv/bin/python -m job.cli fetch >> logs/fetch.log 2>&1
```

**Windows** — use Task Scheduler:
1. Open Task Scheduler → Create Basic Task
2. Trigger: repeat every 30 minutes
3. Action: Start a program
   - Program: `C:\Users\<you>\Downloads\job-scraper\.venv\Scripts\python.exe`
   - Arguments: `-m job.cli fetch`
   - Start in: `C:\Users\<you>\Downloads\job-scraper`
