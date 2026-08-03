# JobPilot AI

Your AI copilot for the job hunt — from discovery to offer. JobPilot AI fetches
listings from eight sources, scores them against your profile, then generates
tailored, ATS-optimized resumes and cover letters with one click.

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

**Step 1 — Prerequisites:** Checks Node.js, an AI provider (see [AI Providers](#ai-providers)), and pdflatex. Shows install instructions for anything missing.

> **Windows — pdflatex:** Install [MiKTeX](https://miktex.org/download). During setup, set *"Install missing packages on-the-fly"* to **Yes** to prevent the first PDF build from hanging on missing LaTeX packages.

**Step 2 — Profile:** Fill in your experience, education, and certifications using a structured form, or upload an existing PDF/DOCX resume to autofill.

**Step 3 — Done:** Auto-configure searches from your profile with one click, or enter a job title and location to start fetching immediately.

---

## Features

**Multi-profile** — avatar in the top-right switches between profiles, each with its own jobs, search config, and generated documents.

**Job list** — sortable and searchable. Filter by title, company, location, source, remote type, and posting date.

**Match scoring** — every job is scored against your profile automatically:
- *Skill match* — keyword overlap between the job description and your skills (always available, no API key needed).
- *Smart match* — semantic similarity scored with embeddings for an "overall fit %" signal. Requires a Gemini API key; toggle in **AI Settings → Smart job matching**.

**Build CV** — click ▶ Build CV on any job to generate a tailored ATS-optimized resume PDF.

**Write Letter** — appears after a CV is built. Generates a matching cover letter.

**AI Settings** — dedicated page to configure providers, API keys, models, and smart matching. Shows per-provider token usage for the last 24 hours.

**Search Settings** — edit queries, sources, locations, and filters from the UI without touching files.

**Profile Settings** — avatar → Manage Profiles → click a profile row. Edit profile, search config, or clear data.

---

## AI Providers

JobPilot picks a provider automatically (first available wins), or you can pin one in **AI Settings**.

| Provider | How to use | Cost |
|---|---|---|
| **Groq** | Add `GROQ_API_KEY` — get one free at [console.groq.com](https://console.groq.com) | Free tier |
| **Claude (API)** | Add `ANTHROPIC_API_KEY` | Paid |
| **Claude (CLI)** | Install `@anthropic-ai/claude-code` and log in with a Pro subscription | Subscription |
| **Gemini (API)** | Add `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Free tier / paid |
| **Gemini (CLI)** | Install `@google/gemini-cli` and log in with a personal Google account | Free |

Keys are entered in the UI (**AI Settings**) and saved to `.env` — no manual file editing required. The preferred provider and model are configurable per-provider, and the page shows a live connection test and 24-hour token usage.

> **Recommendation:** Start with a free Groq key (`llama-3.3-70b-versatile` is the default). Add a Gemini key too to unlock smart semantic job matching.

---

## Sources

| Source | Coverage |
|---|---|
| LinkedIn | Large job market, public search |
| StepStone | European job market |
| Greenhouse | Per-company boards, no key required |
| GermanTechJobs | German tech job market |
| Berlin Startup Jobs | Berlin startup ecosystem |
| Jobicy | Remote-first jobs, public API |
| Himalayas | Remote jobs, public API |
| HeyJobs | Registered but inactive (requires auth) |

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
