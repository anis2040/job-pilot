# job-scraper

Fetches job listings from LinkedIn, Jobicy, Himalayas, and Greenhouse, and generates tailored ATS-optimized resumes and cover letters with one click using Claude or Gemini. Supports multiple profiles so different people (or different job tracks) can share one installation.

---

## What you need to install manually

Only two things are required before you can run the app. Everything else (AI CLI, pdflatex, your profile) is handled by the in-browser setup wizard.

### 1. Python 3.9+

**macOS:**
```bash
brew install python@3.11
```
Or download from [python.org/downloads](https://www.python.org/downloads/)

After installing with Homebrew, Python is added to PATH automatically. Verify with `python3 --version`. If it says "command not found", add it manually:
```bash
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Windows:**

1. Download the installer from [python.org/downloads](https://www.python.org/downloads/)
2. Run the installer — on the **first screen**, check **"Add Python to PATH"** before clicking Install Now

   > ⚠️ If you miss this checkbox, Python won't be found in the terminal. You'd need to reinstall or add it manually.

3. Open a new PowerShell window and verify:
   ```powershell
   python --version
   ```
   Should show `Python 3.11.x` or higher.

If Python is installed but not in PATH (you get "not recognized as a command"), add it manually:
- Open **System Properties** → **Environment Variables**
- Under **User variables**, find `Path`, click **Edit**
- Add: `C:\Users\<YourName>\AppData\Local\Programs\Python\Python311\` and `C:\Users\<YourName>\AppData\Local\Programs\Python\Python311\Scripts\`
- Open a new terminal and try again

**Linux:**
```bash
sudo apt install python3.11 python3.11-venv
```

Verify: `python3 --version` (should show 3.11 or higher)

---

### 2. Git

**macOS:** pre-installed, or `brew install git`

**Windows:** download from [git-scm.com/download/win](https://git-scm.com/download/win)

**Linux:** `sudo apt install git`

---

### 3. Node.js 18+ *(required for CV/cover letter generation only)*

Not needed to run the app or fetch jobs. Only needed if you want the AI to build resumes — the setup wizard will prompt you if it's missing.

**macOS:**
```bash
brew install node
```

**Windows:** download from [nodejs.org/en/download](https://nodejs.org/en/download) (LTS), or:
```powershell
winget install OpenJS.NodeJS.LTS
```

**Linux:**
```bash
sudo apt install nodejs npm
```

Verify: `node --version`

---

## Install & Run

**1. Clone the repo:**

```bash
git clone https://github.com/anis2040/job-scraper.git
cd job-scraper
```

**2. Run the start script:**

**macOS / Linux:**
```bash
./start.sh
```

**Windows:**
```powershell
start.bat
```

That's it. The script automatically:
- Creates a Python virtual environment if one doesn't exist
- Installs all dependencies (`pip install -r requirements.txt`)
- Starts the app at **http://localhost:5050**

Run the same script every time you want to start the app.

> **If you get a permission error on macOS/Linux**, make the script executable first:
> ```bash
> chmod +x start.sh
> ```

---

<details>
<summary>Manual setup (if the script doesn't work)</summary>

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python web.py
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python web.py
```

> If you get `ModuleNotFoundError`, make sure you activated the virtualenv before running `python web.py`.

</details>

Open **http://localhost:5050** — the setup wizard launches automatically and guides you through the AI CLI, pdflatex, and your profile.

> There is no `package.json` or `npm install` — this is a Python app. All dependencies are Python packages managed by `pip` via `requirements.txt`.

---

## Setup Wizard

Runs on first launch. 3 steps:

**Step 1 — Prerequisites:** Checks Node.js, AI CLI (Claude or Gemini), and pdflatex.
- One-click install buttons for AI CLI and pdflatex (macOS/Linux). Windows shows step-by-step instructions.
- If Node.js is missing, install it manually (see above) — the wizard can't install it automatically on all platforms.

**Step 2 — Profile:** Fill in your experience, education, and certifications using a structured form, or upload an existing PDF/DOCX resume to autofill. The AI uses this exclusively to build resumes — it never invents anything not in your profile.

**Step 3 — Done:** Auto-configure searches from your profile with one click, or skip with a quick title + location form to start fetching jobs immediately.

> The AI CLI, pdflatex, Gemini API key, and your profile are all configured inside the wizard — no extra terminal commands needed after `pip install`.


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
