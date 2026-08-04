# JobPilot Frontend

React + TypeScript + Vite frontend for JobPilot AI.

## Recommended Dev Flow

From the repo root, run:

```bash
npm run dev
```

That command installs missing backend/frontend dependencies and starts both services together:

- Flask backend on `http://localhost:5050`
- Vite frontend on `http://localhost:5173`

## Frontend-Only Commands

```bash
npm install
npm run dev
npm run build
npm run test
```

Vite proxies `/api` and `/pdf` requests to the Flask backend on port `5050` during development.
