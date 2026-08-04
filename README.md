# JobPilot AI

JobPilot AI helps you search jobs, score them against your profile, and generate tailored resumes and cover letters.

## React Dev Mode

Use the root dev launcher when you want the React app and Flask backend together.

```bash
npm run dev
```

What it does automatically:

- Creates `.venv` if it does not exist yet
- Installs Python packages from `requirements.txt`
- Installs frontend packages in `frontend/`
- Starts Flask on `http://localhost:5050`
- Starts Vite on `http://localhost:5173`

This works on both macOS and Windows as long as `python`/`python3` and `node`/`npm` are installed.

If you prefer OS-specific launchers:

| macOS | Windows |
|---|---|
| `./dev.sh` | `dev.bat` |

> If `dev.sh` is not executable, run `chmod +x dev.sh` once.

## Legacy Flask Launcher

The old server-rendered UI is still available and uses the original setup/start scripts.

| First run | Later runs |
|---|---|
| `./setup.sh` / `setup.bat` | `./start.sh` / `start.bat` |

That flow opens the Flask app directly at `http://localhost:5050`.

## Common Commands

```bash
# React app + backend
npm run dev

# Backend only
npm run backend

# Frontend only
npm run frontend

# Frontend production build
npm --prefix frontend run build

# Frontend tests
npm --prefix frontend run test
```

After building the frontend, Flask serves the compiled SPA at `http://localhost:5050/app`.

## Setup Wizard

On first launch, the app guides you through:

1. Checking prerequisites such as Node.js, an AI provider, and `pdflatex`
2. Creating or importing your profile
3. Generating search settings from your profile and starting the first fetch

For Windows PDF generation, install [MiKTeX](https://miktex.org/download) and enable on-the-fly package installation.

## Features

- Fetches jobs from multiple sources including LinkedIn, StepStone, Greenhouse, Jobicy, and Himalayas
- Supports multiple profiles with separate jobs, configs, and generated documents
- Scores jobs with keyword matching and optional semantic matching
- Builds ATS-oriented resumes and matching cover letters per job
- Lets you manage AI providers, models, and token usage from the UI

## AI Providers

JobPilot can use Groq, Anthropic Claude, and Gemini. API keys are entered in the app and saved to `.env`.

| Provider | Env var |
|---|---|
| Groq | `GROQ_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Gemini | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |

## Output

Generated files are stored under the active profile, for example:

```text
profiles/<name>/<CompanyName>/resumes/
profiles/<name>/<CompanyName>/cover-letters/
```
