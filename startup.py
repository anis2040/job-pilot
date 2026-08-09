"""One-time startup tasks: load .env, migrate legacy folder layouts, clean up
orphaned profiles, and pre-warm the AI cache.

Extracted from web.py's __main__ block so the logic is importable and testable.
Each migration is idempotent (guarded by existence checks), so running this on
every launch is safe.
"""
from __future__ import annotations
import os
import shutil
import threading

from job.paths import BASE
from job.db import init_db
from job.profiles import (
    get_active_slug, PROFILES_DIR, _update_symlinks, migrate_legacy_profiles_layout,
    safe_profile_dir, user_profiles_dir,
)
from job.user_context import LOCAL_USER_ID, user_context


def _ensure_dependencies() -> None:
    """Install any missing packages from requirements.txt at startup."""
    import subprocess, sys
    req = BASE / "requirements.txt"
    if not req.exists():
        return
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
            check=False,
        )
    except Exception:
        pass


def _load_env_file() -> None:
    """Load server config from root .env (not per-user AI keys)."""
    env_path = BASE / ".env"
    if not env_path.exists():
        return
    ai_keys = {
        "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
        "ANTHROPIC_AUTH_TOKEN", "PREFERRED_PROVIDER", "GROQ_MODEL",
        "ANTHROPIC_MODEL", "GEMINI_MODEL", "SEMANTIC_MATCH",
        "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
    }
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in ai_keys:
                continue  # AI keys live under profiles/<user>/.env
            os.environ.setdefault(k, v)


def _migrate_active_profile(active_slug: str) -> None:
    profile_dir = safe_profile_dir(active_slug)
    if not profile_dir:
        return
    _update_symlinks(profile_dir)
    init_db()

    # Migration 1: legacy project-root resumes/<company>/ → profiles/<user>/<slug>/<company>/resumes/
    legacy_root = BASE / "resumes"
    if legacy_root.exists():
        for company_dir in legacy_root.iterdir():
            if not company_dir.is_dir():
                continue
            dest = profile_dir / company_dir.name / "resumes"
            if not dest.exists():
                dest.mkdir(parents=True, exist_ok=True)
            for f in company_dir.iterdir():
                if f.is_file() and not (dest / f.name).exists():
                    shutil.copy2(f, dest / f.name)

    # Migration 2: .../resumes/<company>/<files> → .../<company>/resumes/ or cover-letters/
    old_resumes = profile_dir / "resumes"
    if old_resumes.is_dir():
        for company_dir in old_resumes.iterdir():
            if not company_dir.is_dir():
                continue
            for f in company_dir.iterdir():
                if not f.is_file():
                    continue
                subdir = "cover-letters" if "Cover_Letter" in f.name else "resumes"
                dest_dir = profile_dir / company_dir.name / subdir
                dest_dir.mkdir(parents=True, exist_ok=True)
                if not (dest_dir / f.name).exists():
                    shutil.copy2(f, dest_dir / f.name)
        shutil.rmtree(old_resumes, ignore_errors=True)


def _cleanup_orphan_profiles() -> None:
    if not PROFILES_DIR.exists():
        return
    from job.profiles import validate_user_id

    for user_dir in PROFILES_DIR.iterdir():
        if not user_dir.is_dir() or not validate_user_id(user_dir.name):
            continue
        try:
            children = list(user_dir.iterdir())
        except OSError:
            continue
        for d in children:
            try:
                orphan = (
                    d.is_dir()
                    and d.name.startswith("new-profile-")
                    and not (d / "profile.md").exists()
                )
            except OSError:
                continue
            if orphan:
                shutil.rmtree(d, ignore_errors=True)


def run_startup() -> None:
    """Run all startup tasks in order. Safe to call once at launch."""
    _ensure_dependencies()
    _load_env_file()
    migrate_legacy_profiles_layout()

    # Startup migrations run in local-user context (CLI / single-process boot).
    with user_context(LOCAL_USER_ID):
        active_slug = get_active_slug()
        if active_slug:
            _migrate_active_profile(active_slug)
        _cleanup_orphan_profiles()

    # Pre-warm the Anthropic prompt cache in background (1h TTL)
    from job.web_api import _prewarm_cache
    threading.Thread(target=_prewarm_cache, daemon=True).start()
