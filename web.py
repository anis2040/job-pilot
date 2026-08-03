from __future__ import annotations
import os
import sys
import json as _json
import yaml
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request, send_file, abort, redirect, url_for, make_response

from job.db import init_db, get_pending_deduped, get_jobs_by_status, update_status, get_job, get_similar_jobs, stats, last_fetch_at, clear_all_jobs
from job.web_api import trigger_resume, get_task_status, trigger_cover_letter, get_cl_task_status, trigger_fetch, get_fetch_status, clear_task_state, call_ai
from job.web_api import (
    _get_groq_client, _get_anthropic_client, _get_gemini_client,
    _get_model, _list_models, _clear_model_cache, _build_with_groq, _build_with_sdk, _build_with_gemini,
    _GROQ_MODELS, _ANTHROPIC_MODELS, _GEMINI_MODELS, _MODEL_DEFAULTS,
)
from job.profiles import (
    list_profiles, get_active_slug, get_active_profile, set_active,
    create_profile, delete_profile, has_any_profiles, slugify,
    get_profile_path, get_config_path, get_resumes_path, active_profile_dir,
    get_profile_json,
    PROFILES_DIR,
)

from job.paths import BASE
from job.fetcher import SOURCES
from job.models import RemoteType, DEFAULT_BLACKLIST, JOB_STATUSES
from job.match import compute_match

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.secret_key = os.environ.get("SECRET_KEY", "job-scraper-dev-key-change-in-prod")


@app.errorhandler(404)
def _handle_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return e


@app.errorhandler(Exception)
def _handle_exception(e):
    # Let Flask handle its own HTTP exceptions (404, 405, etc.) normally.
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    if request.path.startswith("/api/"):
        return jsonify({"error": str(e)}), 500
    raise e


def _config_path() -> Path:
    p = get_config_path()
    if not p:
        raise RuntimeError("No active profile")
    return p


def _profile_path() -> Path:
    p = get_profile_path()
    if not p:
        raise RuntimeError("No active profile")
    return p


def _resumes_path() -> Path:
    p = get_resumes_path()
    if not p:
        raise RuntimeError("No active profile")
    return p


def _source_label(search_name: str) -> str:
    n = search_name.lower()
    if "linkedin" in n:  return "LinkedIn"
    if "jobicy" in n:    return "Jobicy"
    if "himalayas" in n: return "Himalayas"
    if "greenhouse" in n: return "Greenhouse"
    return search_name.split("-")[0].strip() if search_name else ""


def _write_env_var(env_path: Path, key: str, value: str) -> None:
    """Upsert a KEY=value line in the .env file, removing any prior occurrence."""
    lines = [l for l in env_path.read_text(encoding="utf-8").splitlines() if not l.startswith(f"{key}=")] if env_path.exists() else []
    lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_install(cmd: list, timeout: int) -> dict:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "output": (r.stdout or r.stderr)[-1000:]}
    except Exception as e:
        return {"ok": False, "output": str(e)}


def _read_config_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_config_yaml(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _save_api_key(env_key: str, provider: str):
    data = request.get_json() or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "No key provided"}), 400
    _write_env_var(BASE / ".env", env_key, key)
    os.environ[env_key] = key
    _clear_model_cache(provider)
    return jsonify({"ok": True})


def _pdf_url(path: str | None) -> str | None:
    if not path:
        return None
    try:
        rel = Path(path).relative_to(_resumes_path())
        return f"/pdf/{rel.as_posix()}"
    except (ValueError, RuntimeError):
        return None


def _require_profile_dir(slug: str):
    if not (PROFILES_DIR / slug).is_dir():
        return jsonify({"error": "Profile not found"}), 404
    return None


def _format_relative_age(dt_str: str | None, *, days_only: bool = False) -> str:
    """Return a human age string ('5m', '3h', '2d ago') from an ISO datetime string."""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        if days_only:
            days = int(delta.total_seconds() // 86400)
            if days == 0:   return "today"
            if days == 1:   return "1d ago"
            return f"{days}d ago"
        mins = int(delta.total_seconds() // 60)
        if mins < 60:       return f"{mins}m"
        if mins < 1440:     return f"{mins//60}h"
        return f"{mins//1440}d"
    except Exception:
        return ""


def _format_posted(dt_str: str | None) -> str:
    """Human posting date: 'Today' / 'Yesterday' / 'Nd ago' for the last week,
    then an absolute date ('15 Jan') for anything older. '' if unknown."""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days = int((now - dt).total_seconds() // 86400)
        if days <= 0:   return "Today"
        if days == 1:   return "Yesterday"
        if days < 7:    return f"{days}d ago"
        # Older: absolute date, with year only if not the current year
        return dt.strftime("%-d %b") if dt.year == now.year else dt.strftime("%-d %b %Y")
    except Exception:
        return ""


def _find_pdf_path(profile_dir: Path, company: str, subdir: str, suffix: str) -> str | None:
    """Find a built PDF for `company`, matching by filename `suffix`
    (e.g. "_Resume.pdf" / "_Cover_Letter.pdf") regardless of the name prefix.

    PDFs may have been built under a different candidate name than the one
    currently in profile.md (profile renamed, or resume vs cover-letter using
    different names), so we match on the document-type suffix, not the exact
    filename. Searches the given subdir, then the sibling docs subdir, then the
    legacy flat layout (resumes/<Company>/<file>).
    """
    company_variants = [company, company.replace(" ", ""), company.replace(" ", "").replace("/", "")]
    # Directories to scan, in priority order.
    search_dirs: list[Path] = []
    for co in company_variants:
        search_dirs.append(profile_dir / co / subdir)          # current layout
        search_dirs.append(profile_dir / co / "resumes")       # cover letters sometimes land here
        search_dirs.append(profile_dir / "resumes" / co)       # legacy flat layout

    seen: set[Path] = set()
    for d in search_dirs:
        if d in seen or not d.is_dir():
            continue
        seen.add(d)
        matches = sorted(d.glob(f"*{suffix}"))
        if matches:
            return str(matches[0])
    return None


def _serialize_job(row, task_status: dict, cl_task_status: dict, profile: dict | None = None) -> dict:
    r = dict(row)
    job_id = r["job_id"]
    company = r.get("company") or ""

    ts = task_status.get(job_id, {})
    resume_status = ts.get("status", "idle")
    pdf_path = ts.get("pdf_path")

    cl_ts = cl_task_status.get(job_id, {})
    cl_status = cl_ts.get("status", "idle")
    cl_pdf_path = cl_ts.get("pdf_path")

    try:
        profile_dir = _resumes_path()
        if resume_status == "idle" and not pdf_path:
            pdf_path = _find_pdf_path(profile_dir, company, "resumes", "_Resume.pdf")
            if pdf_path:
                resume_status = "done"
        if cl_status == "idle" and not cl_pdf_path:
            cl_pdf_path = _find_pdf_path(profile_dir, company, "cover-letters", "_Cover_Letter.pdf")
            if cl_pdf_path:
                cl_status = "done"
    except RuntimeError:
        pass

    return {
        "job_id": job_id,
        "url": r.get("url") or "",
        "title": r.get("title") or "",
        "company": company,
        "location": r.get("location") or "",
        "remote": r.get("remote") or "",
        "experience": r.get("experience") or "",
        "age": _format_relative_age(r.get("first_seen_at")),
        "posted": _format_posted(r.get("posted_at")),
        "posted_at": r.get("posted_at") or "",
        "first_seen_at": r.get("first_seen_at") or "",
        "status": r.get("status") or "pending",
        "source": _source_label(r.get("search_name") or ""),
        "match": compute_match(r.get("description") or "", profile),
        "resume_status": resume_status,
        "resume_stage": ts.get("stage", ""),
        "pdf_url": _pdf_url(pdf_path),
        "resume_error": ts.get("error"),
        "cl_status": cl_status,
        "cl_stage": cl_ts.get("stage", ""),
        "cl_pdf_url": _pdf_url(cl_pdf_path),
        "cl_error": cl_ts.get("error"),
    }


# ── Main routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if not has_any_profiles():
        return redirect(url_for("setup"))
    if not get_active_slug():
        return redirect(url_for("profile_picker"))
    # Allow access even without a profile.md — user can browse/fetch without CV features
    try:
        init_db()
        counts = stats()
        last = last_fetch_at()
    except Exception:
        counts = {"pending": 0, "applied": 0, "skipped": 0}
        last = None
    last_str = ""
    stale = False
    if last:
        dt = datetime.fromisoformat(last)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        last_str = f"{int(hours)}h ago" if hours >= 1 else "just now"
        stale = hours > 24
    active = get_active_profile()
    has_pdflatex = bool(shutil.which("pdflatex"))
    return render_template("index.html", counts=counts, last_fetch=last_str, stale=stale, active_profile=active, has_pdflatex=has_pdflatex)


@app.route("/profiles")
def profile_picker():
    profiles = list_profiles()
    if not profiles:
        return redirect(url_for("setup"))
    return render_template("profiles.html", profiles=profiles)


@app.route("/api/profiles/<slug>/clear-jobs", methods=["POST"])
def api_profile_clear_jobs(slug):
    if err := _require_profile_dir(slug): return err
    import sqlite3
    profile_dir = PROFILES_DIR / slug
    db_path = str(profile_dir / "state.db")
    try:
        con = sqlite3.connect(db_path)
        con.execute("DELETE FROM jobs")
        con.execute("DELETE FROM filter_log")
        con.execute("DELETE FROM fetch_log")
        con.commit()
        con.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    if slug == get_active_slug():
        clear_task_state()
    return jsonify({"ok": True})


@app.route("/profile-settings/<slug>")
def profile_settings(slug):
    from job.profiles import _profile_info
    profile_dir = PROFILES_DIR / slug
    if not profile_dir.is_dir():
        return redirect(url_for("manage_profiles"))
    profile = _profile_info(profile_dir)
    active_slug = get_active_slug()
    return render_template("profile_settings.html", profile=profile, active_slug=active_slug)


@app.route("/manage-profiles")
def manage_profiles():
    return render_template("manage_profiles.html")


@app.route("/ai-settings")
def ai_settings_page():
    providers = [
        {"id": "groq",      "label": "Groq",             "sub": "Fast free inference — llama, mixtral, gemma",  "badge_class": "badge-free",  "badge_text": "Free ⚡",  "placeholder": "gsk_…",    "hint": 'Get a free key at <a href="https://console.groq.com/keys" target="_blank">console.groq.com/keys ↗</a>. Saved locally in <code>.env</code>.'},
        {"id": "anthropic", "label": "Claude (Anthropic)","sub": "High quality — Haiku, Sonnet, Opus",          "badge_class": "badge-paid",  "badge_text": "API key",  "placeholder": "sk-ant-…", "hint": 'Get a key at <a href="https://console.anthropic.com/settings/keys" target="_blank">console.anthropic.com ↗</a>. Saved locally in <code>.env</code>.'},
        {"id": "gemini",    "label": "Gemini (Google)",   "sub": "Free API key — Flash, Flash-lite, 1.5",        "badge_class": "badge-free",  "badge_text": "Free",     "placeholder": "AIza…",    "hint": 'Get a free key at <a href="https://aistudio.google.com/apikey" target="_blank">Google AI Studio ↗</a>. Saved locally in <code>.env</code>.'},
    ]
    return render_template("ai_settings.html", providers=providers)


# ── Profile API ───────────────────────────────────────────────────────────────

@app.route("/api/profiles")
def api_profiles_list():
    profiles = list_profiles()
    active_slug = get_active_slug()
    return jsonify({
        "profiles": [
            {"slug": p.slug, "name": p.name, "label": p.label, "initials": p.initials, "color": p.color, "active": p.slug == active_slug}
            for p in profiles
        ],
        "active_slug": active_slug,
    })


@app.route("/api/profiles/active")
def api_profiles_active():
    active = get_active_profile()
    if not active:
        return jsonify({"active": None})
    return jsonify({"active": {"slug": active.slug, "name": active.name, "label": active.label, "initials": active.initials, "color": active.color}})


@app.route("/api/profiles/<slug>/label", methods=["POST"])
def api_set_profile_label(slug):
    err = _require_profile_dir(slug)
    if err:
        return err
    from job.profiles import set_label
    label = (request.get_json(silent=True) or {}).get("label", "")
    if set_label(slug, label):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Could not update label"}), 400


@app.route("/api/profiles/new", methods=["POST"])
def api_profiles_new():
    """Create a blank profile folder but do NOT switch to it yet.
    The switch happens in save-profile once the user has filled in their details."""
    import time as _time
    slug = create_profile(f"new-profile-{int(_time.time())}")
    # Store the pending slug in the session so save-profile knows which folder to use
    from flask import session
    session["pending_profile_slug"] = slug
    return jsonify({"ok": True, "slug": slug})


@app.route("/api/profiles/switch/<slug>", methods=["POST"])
def api_profiles_switch(slug):
    if not set_active(slug):
        return jsonify({"error": "Profile not found"}), 404
    clear_task_state()
    init_db()
    counts = stats()
    job_count = counts.get("pending", 0) + counts.get("applied", 0) + counts.get("skipped", 0)
    # Pre-warm cache for the new profile in background
    import threading as _threading
    from job.web_api import _prewarm_cache
    _threading.Thread(target=_prewarm_cache, daemon=True).start()
    return jsonify({"ok": True, "slug": slug, "empty": job_count == 0})


@app.route("/api/profiles/delete/<slug>", methods=["POST"])
def api_profiles_delete(slug):
    if slug == get_active_slug():
        return jsonify({"error": "Cannot delete the active profile. Switch to another profile first."}), 400
    if not delete_profile(slug):
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/profiles/<slug>/profile-md", methods=["GET"])
def api_profile_md_get(slug):
    if err := _require_profile_dir(slug): return err
    profile_dir = PROFILES_DIR / slug
    profile_md = profile_dir / "profile.md"
    return jsonify({"content": profile_md.read_text(encoding="utf-8") if profile_md.exists() else ""})


@app.route("/api/profiles/<slug>/profile-md", methods=["POST"])
def api_profile_md_save(slug):
    if err := _require_profile_dir(slug): return err
    profile_dir = PROFILES_DIR / slug
    data = request.get_json() or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Profile content is empty"}), 400
    (profile_dir / "profile.md").write_text(content, encoding="utf-8")
    from job.profiles import write_profile_json
    write_profile_json(profile_dir)
    # Update symlinks if this is the active profile
    if slug == get_active_slug():
        from job.profiles import _update_symlinks
        _update_symlinks(profile_dir)
    return jsonify({"ok": True})


@app.route("/api/profiles/<slug>/config", methods=["GET"])
def api_profile_config_get(slug):
    config_p = PROFILES_DIR / slug / "config.yaml"
    if not config_p.exists():
        return jsonify({"searches": [], "title_filter": [], "blacklist": [], "company_blacklist": []})
    return jsonify(_read_config_yaml(config_p))


@app.route("/api/profiles/<slug>/config", methods=["POST"])
def api_profile_config_save(slug):
    if err := _require_profile_dir(slug): return err
    profile_dir = PROFILES_DIR / slug
    data = request.get_json() or {}
    if not isinstance(data.get("searches"), list) or not data["searches"]:
        return jsonify({"error": "At least one search entry required"}), 400
    config_p = profile_dir / "config.yaml"
    _write_config_yaml(config_p, data)
    # If active profile, clear and re-fetch
    if slug == get_active_slug():
        clear_all_jobs()
        clear_task_state()
    return jsonify({"ok": True})


@app.route("/job/<job_id>")
def job_detail_page(job_id):
    row = get_job(job_id)
    if not row:
        return "Job not found", 404
    return render_template("job_detail.html",
                           job_id=job_id,
                           active_profile=get_active_profile())


@app.route("/api/job/<job_id>/description")
def api_job_description(job_id):
    """Return description for a job — from DB if stored, otherwise scrape on demand
    via the source's declared describe capability (see job.fetcher.SOURCE_REGISTRY).
    When a fresh description is fetched and the stored workplace type is Unknown,
    re-infer it from the description (LinkedIn cards don't expose it)."""
    row = get_job(job_id)
    if not row:
        return jsonify({"error": "Job not found"}), 404

    r = dict(row)
    description = r.get("description") or ""
    remote = r.get("remote") or ""

    if not description:
        from job.fetcher import fetch_description as _fetch_desc
        from job.db import update_description, update_remote
        from job.fetcher_utils import infer_remote
        description = _fetch_desc(job_id, r.get("url") or "")
        if description:
            update_description(job_id, description)
            # Backfill workplace type from the full text if we didn't know it
            if remote in ("", RemoteType.UNKNOWN):
                inferred = infer_remote(r.get("title") or "", r.get("location") or "",
                                        description, default=RemoteType.UNKNOWN)
                if inferred != RemoteType.UNKNOWN:
                    update_remote(job_id, inferred)
                    remote = inferred

    # Compute match against the (possibly just-fetched) description so the
    # detail page's skills card reflects on-demand descriptions too.
    match = compute_match(description, get_profile_json())
    return jsonify({"description": description, "remote": remote, "match": match})


@app.route("/api/job/<job_id>")
def api_job_detail(job_id):
    row = get_job(job_id)
    if not row:
        return jsonify({"error": "Job not found"}), 404
    ts = get_task_status(job_id)
    cl_ts = get_cl_task_status(job_id)
    data = _serialize_job(row, {job_id: ts}, {job_id: cl_ts}, get_profile_json())
    r = dict(row)
    data["description"]     = r.get("description") or ""
    data["posted_at"]       = r.get("posted_at") or ""
    data["first_seen_at"]   = r.get("first_seen_at") or ""
    data["status_updated_at"] = r.get("status_updated_at") or ""
    data["employment_type"] = r.get("employment_type") or ""
    data["salary_range"]    = r.get("salary_range") or ""
    return jsonify(data)


@app.route("/api/jobs/similar/<job_id>")
def api_similar_jobs(job_id):
    rows = get_similar_jobs(job_id, limit=5)
    task_statuses   = {r["job_id"]: get_task_status(r["job_id"]) for r in rows}
    cl_task_statuses = {r["job_id"]: get_cl_task_status(r["job_id"]) for r in rows}
    return jsonify([_serialize_job(r, task_statuses, cl_task_statuses) for r in rows])


# ── Job routes ────────────────────────────────────────────────────────────────

@app.route("/api/jobs")
def api_jobs():
    status_filter = request.args.get("status", "pending")
    rows = get_jobs_by_status(status_filter)
    task_statuses = {row["job_id"]: get_task_status(row["job_id"]) for row in rows}
    cl_task_statuses = {row["job_id"]: get_cl_task_status(row["job_id"]) for row in rows}
    profile = get_profile_json()  # loaded once; reused for every job's match signal
    return jsonify([_serialize_job(row, task_statuses, cl_task_statuses, profile) for row in rows])


@app.route("/api/resume/<job_id>", methods=["POST"])
def api_build_resume(job_id):
    row = get_job(job_id)
    if not row:
        return jsonify({"error": "Job not found"}), 404
    trigger_resume(job_id)
    return jsonify({"status": "building"})


@app.route("/api/resume-status/<job_id>")
def api_resume_status(job_id):
    ts = get_task_status(job_id)
    return jsonify({"status": ts.get("status", "idle"), "stage": ts.get("stage", ""), "pdf_url": _pdf_url(ts.get("pdf_path")), "error": ts.get("error"), "rate_limit": ts.get("rate_limit")})


@app.route("/api/cover-letter/<job_id>", methods=["POST"])
def api_build_cover_letter(job_id):
    row = get_job(job_id)
    if not row:
        return jsonify({"error": "Job not found"}), 404
    trigger_cover_letter(job_id)
    return jsonify({"status": "building"})


@app.route("/api/cover-letter-status/<job_id>")
def api_cover_letter_status(job_id):
    ts = get_cl_task_status(job_id)
    return jsonify({"status": ts.get("status", "idle"), "stage": ts.get("stage", ""), "pdf_url": _pdf_url(ts.get("pdf_path")), "error": ts.get("error"), "preview": ts.get("preview", ""), "rate_limit": ts.get("rate_limit")})


@app.route("/api/job-status/<job_id>/<new_status>", methods=["POST"])
def api_job_status(job_id, new_status):
    if new_status not in ("applied", "skipped", "pending"):
        return jsonify({"error": "Invalid status"}), 400
    ok = update_status(job_id, new_status)
    return jsonify({"ok": ok})


@app.route("/api/config", methods=["GET"])
def api_config_get():
    config_p = _config_path()
    if not config_p.exists():
        return jsonify({"searches": [], "title_filter": [], "blacklist": [], "company_blacklist": []})
    return jsonify(_read_config_yaml(config_p))


@app.route("/api/config", methods=["POST"])
def api_config_save():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    if not isinstance(data.get("searches"), list) or not data["searches"]:
        return jsonify({"error": "At least one search entry required"}), 400
    required = {"name", "source", "query"}
    for s in data["searches"]:
        if not required.issubset(s.keys()):
            return jsonify({"error": f"Search entry missing fields: {required - s.keys()}"}), 400
    config_p = _config_path()
    config_p.parent.mkdir(parents=True, exist_ok=True)
    _write_config_yaml(config_p, data)
    return jsonify({"ok": True})


@app.route("/api/ai-settings", methods=["GET"])
def api_ai_settings_get():
    groq_ok      = _get_groq_client() is not None
    anthropic_ok = _get_anthropic_client() is not None
    gemini_ok    = _get_gemini_client() is not None or bool(shutil.which("gemini"))

    preferred = os.environ.get("PREFERRED_PROVIDER", "").strip().lower()

    # active = preferred if it's available, else first available in default order
    if preferred == "groq" and groq_ok:           active = "groq"
    elif preferred == "anthropic" and anthropic_ok: active = "anthropic"
    elif preferred == "gemini" and gemini_ok:     active = "gemini"
    elif groq_ok:                                 active = "groq"
    elif anthropic_ok:                            active = "anthropic"
    elif gemini_ok:                               active = "gemini"
    else:                                         active = None

    def _models_for(provider):
        """Live list with the currently-selected model guaranteed present."""
        models = _list_models(provider)
        current = _get_model(provider)
        if current and current not in models:
            models = [current] + models
        return models

    # Actual stored keys, so the UI's show/hide (eye) toggle can reveal them.
    # Local single-user app — keys already live in plaintext .env. Only real
    # env keys are returned; CLI-detected availability (claude/gemini) has no
    # key to show.
    groq_key      = os.environ.get("GROQ_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or ""
    gemini_key    = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""

    # Token-usage counter: what THIS app has spent per provider, scoped to the
    # currently-active API key (limits are per-key/org, so switching keys must
    # show a fresh count). Best-effort — no profile / empty DB yields zeros.
    from job.limits import usage_reference
    from job.ai_providers import _key_fingerprint
    key_ids = {p: _key_fingerprint(p) for p in ("groq", "gemini", "anthropic")}
    try:
        from job.db import usage_last_24h, usage_today
        u24, utoday = usage_last_24h(key_ids), usage_today(key_ids)
    except Exception:
        u24, utoday = {}, {}

    def _usage_for(provider):
        ref = usage_reference(provider, _get_model(provider))
        return {
            "last_24h_tokens": u24.get(provider, 0),
            "today_tokens":    utoday.get(provider, 0),
            "limit_tpd":       ref["limit_tpd"],
            "approx":          ref["approx"],
            "resets":          ref["resets"],
        }

    return jsonify({
        "active_provider":    active,
        "preferred_provider": preferred or None,
        "providers": {
            "groq": {
                "configured": groq_ok,
                "model":   _get_model("groq"),
                "key_set": bool(os.environ.get("GROQ_API_KEY")),
                "key":     groq_key,
                "models":  _models_for("groq"),
                "usage":   _usage_for("groq"),
            },
            "anthropic": {
                "configured": anthropic_ok,
                "model":   _get_model("anthropic"),
                "key_set": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or shutil.which("claude")),
                "key":     anthropic_key,
                "models":  _models_for("anthropic"),
                "usage":   _usage_for("anthropic"),
            },
            "gemini": {
                "configured": gemini_ok,
                "model":   _get_model("gemini"),
                "key_set": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or shutil.which("gemini")),
                "key":     gemini_key,
                "models":  _models_for("gemini"),
                "usage":   _usage_for("gemini"),
            },
        }
    })


@app.route("/api/ai-settings", methods=["POST"])
def api_ai_settings_save():
    data = request.get_json() or {}
    env_path = BASE / ".env"
    updated_keys = set()

    for field, env_key in [("groq_model", "GROQ_MODEL"), ("anthropic_model", "ANTHROPIC_MODEL"), ("gemini_model", "GEMINI_MODEL")]:
        val = (data.get(field) or "").strip()
        if val:
            _write_env_var(env_path, env_key, val)
            os.environ[env_key] = val
            updated_keys.add(env_key)

    preferred = (data.get("preferred_provider") or "").strip().lower()
    if preferred in ("groq", "anthropic", "gemini", ""):
        if preferred:
            _write_env_var(env_path, "PREFERRED_PROVIDER", preferred)
            os.environ["PREFERRED_PROVIDER"] = preferred
        else:
            _write_env_var(env_path, "PREFERRED_PROVIDER", "")
            # _write_env_var writes KEY= which we then strip to a clean removal
            if env_path.exists():
                lines = [l for l in env_path.read_text(encoding="utf-8").splitlines() if l != "PREFERRED_PROVIDER="]
                env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.environ.pop("PREFERRED_PROVIDER", None)
        updated_keys.add("PREFERRED_PROVIDER")

    return jsonify({"ok": True, "updated": list(updated_keys)})


@app.route("/api/ai-settings/test", methods=["POST"])
def api_ai_settings_test():
    import time
    data = request.get_json() or {}
    provider = data.get("provider", "groq")
    backend = None
    try:
        # Surface diagnostic errors before attempting the real call
        if provider == "groq":
            from job.ai_providers import _load_env
            _load_env()
            if not os.environ.get("GROQ_API_KEY"):
                return jsonify({"ok": False, "error": "GROQ_API_KEY is not set. Add your key in AI Settings."})
            try:
                from groq import Groq  # noqa: F401
            except ImportError:
                return jsonify({"ok": False, "error": "groq package not installed. Close the app, run setup.bat (Windows) or ./setup.sh (Mac/Linux), then try again."})
        elif provider == "anthropic":
            from job.ai_providers import _load_env
            _load_env()
            if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or shutil.which("claude")):
                return jsonify({"ok": False, "error": "No Anthropic credentials found. Add an API key or install Claude Code."})
        elif provider == "gemini":
            from job.ai_providers import _load_env
            _load_env()
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or shutil.which("gemini")):
                return jsonify({"ok": False, "error": "No Gemini credentials found. Add an API key or install the Gemini CLI."})

        t0 = time.time()
        if provider == "groq":
            result = _build_with_groq("You are a test.", "Say OK in one word.")
        elif provider == "anthropic":
            result = _build_with_sdk("You are a test.", "Say OK in one word.")
        elif provider == "gemini":
            from job.web_api import _skill_path
            backend_out = []
            result = _build_with_gemini("You are a test.", "Say OK in one word.", cwd=str(_skill_path()), backend_out=backend_out)
            backend = backend_out[0] if backend_out else None
        else:
            return jsonify({"ok": False, "error": f"Unknown provider: {provider}"}), 400
        latency = round((time.time() - t0) * 1000)
        return jsonify({"ok": True, "model": _get_model(provider), "latency_ms": latency,
                        "backend": backend, "response": result.strip()[:50]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/jobs/clear", methods=["POST"])
def api_jobs_clear():
    clear_all_jobs()
    clear_task_state()
    return jsonify({"ok": True})


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    trigger_fetch()
    return jsonify({"status": "running"})


@app.route("/api/fetch-status")
def api_fetch_status():
    return jsonify(get_fetch_status())


@app.route("/pdf/<path:rel_path>")
def serve_pdf(rel_path):
    base = _resumes_path().resolve()
    pdf = (base / rel_path).resolve()
    if not pdf.is_relative_to(base):
        abort(404)
    if not pdf.exists() or pdf.suffix != ".pdf":
        abort(404)
    return send_file(str(pdf), mimetype="application/pdf")


# ── Setup routes ──────────────────────────────────────────────────────────────

@app.route("/setup")
def setup():
    resp = make_response(render_template("setup.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.route("/api/setup/status")
def api_setup_status():
    profile_p = get_profile_path()
    return jsonify({
        "platform": sys.platform,
        "has_claude": bool(shutil.which("claude")),
        "has_gemini": bool(shutil.which("gemini")),
        "has_pdflatex": bool(shutil.which("pdflatex")),
        "has_node": bool(shutil.which("node")),
        "has_profile": bool(profile_p and profile_p.exists()),
        "gemini_key_set": bool(os.environ.get("GEMINI_API_KEY")),
        "groq_key_set": bool(os.environ.get("GROQ_API_KEY")),
        # Actual keys so the wizard's show/hide (eye) toggle can reveal them.
        "gemini_key": os.environ.get("GEMINI_API_KEY", ""),
        "groq_key": os.environ.get("GROQ_API_KEY", ""),
    })


@app.route("/api/sources")
def api_sources():
    return jsonify([src for src, _ in SOURCES])


@app.route("/api/constants")
def api_constants():
    return jsonify({
        "sources": [src for src, _ in SOURCES],
        "remote_types": RemoteType.ALL,
        "remote_css": {
            RemoteType.REMOTE: "remote-remote",
            RemoteType.HYBRID: "remote-hybrid",
            RemoteType.ONSITE: "remote-onsite",
        },
        "job_statuses": JOB_STATUSES,
        "default_blacklist": DEFAULT_BLACKLIST,
    })


@app.route("/api/setup/suggest-config", methods=["POST"])
def api_setup_suggest_config():
    profile_p = get_profile_path()
    if not profile_p or not profile_p.exists():
        return jsonify({"ok": False, "error": "Profile not found. Complete Step 4 first."})

    profile_text = profile_p.read_text(encoding="utf-8")
    prompt = """Analyze this professional profile and extract job search preferences. Return ONLY valid JSON with this exact structure (no markdown, no explanation):

{
  "titles": ["Primary Job Title", "Secondary Title"],
  "location": "Country or City, Country",
  "remote": true
}

Rules:
- titles: Extract 1-3 job titles the person is qualified for based on their experience
- location: Use the person's current location. If in US, use "United States". If elsewhere, use the country name.
- remote: Set to true if the person seems open to remote work, otherwise false (default to true for tech roles)
- Return ONLY the JSON object, nothing else

Profile:
""" + profile_text[:6000]

    try:
        output = call_ai(prompt)
        if output.startswith("```"):
            output = "\n".join(output.split("\n")[1:])
            output = output.rsplit("```", 1)[0].strip()
        extracted = _json.loads(output)

        titles = extracted.get("titles", [])
        location = extracted.get("location", "United States")
        remote = extracted.get("remote", True)

        if not titles:
            return jsonify({"ok": False, "error": "Could not extract job titles from profile."})

        config_p = _config_path()
        existing = _read_config_yaml(config_p) if config_p.exists() else {}

        primary_title = titles[0]
        searches = [
            {"name": f"{src} - {primary_title}", "source": src,
             "query": primary_title, "location": location, "max_pages": mp, "remote": remote}
            for src, mp in SOURCES
        ]

        new_config = {
            "searches": searches,
            "title_filter": [t.lower() for t in titles],
            "blacklist": existing.get("blacklist", DEFAULT_BLACKLIST),
            "company_blacklist": existing.get("company_blacklist", []),
        }

        clear_all_jobs()
        clear_task_state()

        config_p.parent.mkdir(parents=True, exist_ok=True)
        _write_config_yaml(config_p, new_config)

        return jsonify({"ok": True, "searches": searches, "title_filter": new_config["title_filter"], "location": location})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "AI extraction timed out. Try again."})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Could not parse AI response: {e}"})


@app.route("/api/setup/claude-login", methods=["POST"])
def api_setup_claude_login():
    if not shutil.which("claude"):
        return jsonify({"error": "Claude Code is not installed yet."}), 400
    try:
        # Launch claude login — it opens a browser on the user's machine.
        # Use platform-appropriate flags to detach the process.
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        # shutil.which resolves claude.cmd on Windows; fall back to bare name
        claude_exe = shutil.which("claude") or "claude"
        subprocess.Popen([claude_exe, "login"], **kwargs)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/setup/install-node", methods=["POST"])
def api_setup_install_node():
    if sys.platform == "darwin":
        return jsonify(_run_install(["brew", "install", "node"], 300))
    if sys.platform == "linux":
        if shutil.which("apt-get"):
            return jsonify(_run_install(["sudo", "apt-get", "install", "-y", "nodejs", "npm"], 300))
        if shutil.which("dnf"):
            return jsonify(_run_install(["sudo", "dnf", "install", "-y", "nodejs", "npm"], 300))
        if shutil.which("yum"):
            return jsonify(_run_install(["sudo", "yum", "install", "-y", "nodejs", "npm"], 300))
        if shutil.which("pacman"):
            return jsonify(_run_install(["sudo", "pacman", "-Sy", "--noconfirm", "nodejs", "npm"], 300))
        return jsonify({"ok": False, "output": "No supported package manager found. Install Node.js from https://nodejs.org/"})
    # Windows — use winget
    return jsonify(_run_install(
        ["winget", "install", "--id", "OpenJS.NodeJS.LTS", "--silent",
         "--accept-package-agreements", "--accept-source-agreements"],
        300,
    ))


@app.route("/api/setup/install-cli", methods=["POST"])
def api_setup_install_cli():
    data = request.get_json() or {}
    provider = data.get("provider")
    if provider not in ("claude", "gemini"):
        return jsonify({"error": "Invalid provider"}), 400
    pkg = "@anthropic-ai/claude-code" if provider == "claude" else "@google/gemini-cli"
    # On Windows, npm is npm.cmd (a batch file) and won't be found without the extension
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    return jsonify(_run_install([npm, "install", "-g", pkg], 180))


@app.route("/api/setup/save-groq-key", methods=["POST"])
def api_setup_save_groq_key():
    return _save_api_key("GROQ_API_KEY", "groq")


@app.route("/api/setup/save-gemini-key", methods=["POST"])
def api_setup_save_gemini_key():
    return _save_api_key("GEMINI_API_KEY", "gemini")


@app.route("/api/setup/save-anthropic-key", methods=["POST"])
def api_setup_save_anthropic_key():
    return _save_api_key("ANTHROPIC_API_KEY", "anthropic")


@app.route("/api/setup/install-pdflatex", methods=["POST"])
def api_setup_install_pdflatex():
    if sys.platform == "darwin":
        return jsonify(_run_install(["brew", "install", "--cask", "basictex"], 600))
    if sys.platform == "linux":
        if shutil.which("apt-get"):
            return jsonify(_run_install(["sudo", "apt-get", "install", "-y", "texlive-latex-extra"], 600))
        if shutil.which("dnf"):
            return jsonify(_run_install(["sudo", "dnf", "install", "-y", "texlive-latex", "texlive-collection-latexextra"], 600))
        if shutil.which("yum"):
            return jsonify(_run_install(["sudo", "yum", "install", "-y", "texlive-latex", "texlive-collection-latexextra"], 600))
        if shutil.which("pacman"):
            return jsonify(_run_install(["sudo", "pacman", "-Sy", "--noconfirm", "texlive-latexextra"], 600))
        return jsonify({"ok": False, "output": "No supported package manager found. Install TeX Live from https://tug.org/texlive/"})
    # Windows — use winget
    return jsonify(_run_install(
        ["winget", "install", "--id", "MiKTeX.MiKTeX", "--silent",
         "--accept-package-agreements", "--accept-source-agreements"],
        600,
    ))


@app.route("/api/setup/parse-resume", methods=["POST"])
def api_setup_parse_resume():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    filename = f.filename.lower()
    raw_text = ""
    try:
        if filename.endswith(".pdf"):
            import pypdf, io
            reader = pypdf.PdfReader(io.BytesIO(f.read()))
            raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif filename.endswith(".docx"):
            import zipfile, io
            from xml.etree import ElementTree as ET
            zf = zipfile.ZipFile(io.BytesIO(f.read()))
            xml = zf.read("word/document.xml")
            root = ET.fromstring(xml)
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            raw_text = "\n".join("".join(t.text or "" for t in p.iter(f"{ns}t")) for p in root.iter(f"{ns}p"))
        elif filename.endswith(".txt"):
            raw_text = f.read().decode("utf-8", errors="ignore")
        else:
            return jsonify({"error": "Unsupported file type. Upload a PDF, DOCX, or TXT file."}), 400
    except Exception as e:
        return jsonify({"error": f"Could not read file: {e}"}), 400

    if not raw_text.strip():
        return jsonify({"error": "Could not extract text from the file. Try a different format."}), 400

    prompt = f"""Extract structured information from this resume text and return ONLY valid JSON with exactly this structure (no markdown, no explanation):

{{
  "name": "Full Name", "email": "email@example.com", "phone": "+1 555-000-0000",
  "location": "City, State", "linkedin": "https://linkedin.com/in/...", "auth": "",
  "summary": "2-3 sentence professional summary",
  "competencies": ["skill 1", "skill 2"],
  "experience": [{{"title": "Job Title", "company": "Company Name", "location": "City, Country",
    "start": "Mon Year", "end": "Mon Year or Present",
    "bullets": ["achievement 1"], "projects": [{{"name": "Project", "desc": "description"}}]}}],
  "education": [{{"degree": "Full Degree Name", "school": "Institution", "year": "2024", "location": "City, Country"}}],
  "certifications": ["Cert Name, Issuer (Year)"]
}}

Rules: empty string for missing text, empty array for missing lists, return ONLY JSON.

Resume text:
{raw_text[:8000]}"""

    try:
        output = call_ai(prompt)
        if output.startswith("```"):
            output = "\n".join(output.split("\n")[1:])
            output = output.rsplit("```", 1)[0].strip()
        data = _json.loads(output)
        return jsonify({"ok": True, "data": data})
    except _json.JSONDecodeError:
        return jsonify({"error": f"AI returned unexpected output (not JSON). Raw: {output[:200]}"}), 500
    except Exception as e:
        return jsonify({"error": f"Could not parse AI response: {e}"}), 500


@app.route("/api/setup/save-profile", methods=["POST"])
def api_setup_save_profile():
    data = request.get_json() or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Profile content is empty"}), 400

    # Extract name from first H1 heading for the slug
    from job.profiles import name_from_markdown
    name = name_from_markdown(content) or "default"

    profile_dir = active_profile_dir()

    # Check if we have a pending new profile from the "Add new profile" flow
    from flask import session
    pending_slug = session.pop("pending_profile_slug", None)

    if pending_slug and (PROFILES_DIR / pending_slug).is_dir():
        profile_dir = PROFILES_DIR / pending_slug
        set_active(pending_slug)
        clear_task_state()
    elif not profile_dir:
        slug = create_profile(name)
        profile_dir = PROFILES_DIR / slug
        set_active(slug)

    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "profile.md").write_text(content, encoding="utf-8")

    # Rename the folder to the proper name-based slug if it's still a temp name
    current_slug = profile_dir.name
    proper_slug = slugify(name)
    if current_slug != proper_slug and current_slug.startswith("new-profile-"):
        # Ensure no collision
        target = PROFILES_DIR / proper_slug
        counter = 1
        while target.exists():
            target = PROFILES_DIR / f"{proper_slug}-{counter}"
            counter += 1
        profile_dir.rename(target)
        profile_dir = target
        set_active(target.name)

    from job.profiles import _update_symlinks, write_profile_json
    write_profile_json(profile_dir)
    _update_symlinks(profile_dir)
    init_db()
    return jsonify({"ok": True})


if __name__ == "__main__":
    from startup import run_startup
    run_startup()

    debug = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    app.run(debug=debug, port=5050)
