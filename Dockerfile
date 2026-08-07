# syntax=docker/dockerfile:1

# ── Stage 1: build React SPA ─────────────────────────────────────────────────
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
# Platform optional bindings (rolldown/oxlint) resolve for the build OS — do not
# pin host-specific packages like @rolldown/binding-darwin-arm64 in package.json.
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: runtime (Flask + Gunicorn + pdflatex) ───────────────────────────
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_DEBUG=false \
    AUTH_DISABLED=0 \
    PORT=5050 \
    # Avoid interactive TeX prompts
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System deps: pdflatex for resume/cover-letter PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-fonts-recommended \
        texlive-latex-extra \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# App source (profiles/ is mounted at runtime — do not bake user data into the image)
COPY web.py startup.py ./
COPY job/ ./job/
COPY templates/ ./templates/
COPY static/ ./static/
COPY resume-skill/ ./resume-skill/
COPY cover-letter-skill/ ./cover-letter-skill/
COPY --from=frontend-build /src/frontend/dist ./frontend/dist

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /app/profiles

# Run as non-root. docker-compose.yml sets user to your host UID/GID so the
# bind-mounted ./data/profiles directory stays writable and owned by you.
ARG APP_UID=1000
ARG APP_GID=1000
# Host GIDs (e.g. macOS staff=20) may already exist in the base image — reuse them.
RUN set -eux; \
    if getent group "${APP_GID}" >/dev/null; then \
      GROUP_NAME="$(getent group "${APP_GID}" | cut -d: -f1)"; \
    else \
      groupadd --gid "${APP_GID}" appgroup; \
      GROUP_NAME=appgroup; \
    fi; \
    if ! id -u "${APP_UID}" >/dev/null 2>&1; then \
      useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /usr/sbin/nologin appuser; \
    fi; \
    chown -R "${APP_UID}:${APP_GID}" /app

USER ${APP_UID}:${APP_GID}

EXPOSE 5050

# Persist this path via a volume / bind mount (see docker-compose.yml)
VOLUME ["/app/profiles"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/auth/status" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
