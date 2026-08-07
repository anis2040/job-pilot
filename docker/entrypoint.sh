#!/bin/sh
set -eu

# One-time migrations / .env load (idempotent)
python -c "from startup import run_startup; run_startup()"

# Ensure profiles dir exists (bind mounts may start empty)
mkdir -p /app/profiles

PORT="${PORT:-5050}"
WORKERS="${GUNICORN_WORKERS:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-180}"

exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WORKERS}" \
  --threads 2 \
  --timeout "${TIMEOUT}" \
  --access-logfile - \
  --error-logfile - \
  web:app
