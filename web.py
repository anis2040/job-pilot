from __future__ import annotations
import concurrent.futures as futures
import os
import sys
import json as _json
import yaml
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_file, abort

from job.db import (
    init_db, get_jobs_by_status, get_jobs_list_by_status, get_job_descriptions,
    update_status, get_job, get_similar_jobs, stats, clear_all_jobs, set_job_match_cache,
)
from job.web_api import trigger_resume, get_task_status, trigger_cover_letter, get_cl_task_status, trigger_fetch, get_fetch_status, clear_task_state, call_ai
from job.web_api import (
    _get_groq_client, _get_anthropic_client, _get_gemini_client, _get_openrouter_client,
    _get_model, _list_models, _clear_model_cache, _build_with_groq, _build_with_sdk, _build_with_gemini,
    _build_with_openrouter,
    _GROQ_MODELS, _ANTHROPIC_MODELS, _GEMINI_MODELS, _OPENROUTER_MODELS, _MODEL_DEFAULTS,
)
from job.profiles import (
    list_profiles, get_active_slug, get_active_profile, set_active,
    create_profile, delete_profile, has_any_profiles, slugify,
    get_profile_path, get_config_path, get_resumes_path, active_profile_dir,
    get_profile_json, safe_profile_dir, ensure_user_dir,
)
from job.user_env import write_user_env_var, remove_user_env_var, mask_secret
from job.auth import init_oauth, register_auth_routes
from job.ai_providers import _env_get

from job.paths import BASE
from job.fetcher import SOURCES
from job.models import RemoteType, DEFAULT_BLACKLIST, JOB_STATUSES
from job.match import compute_match, match_text, semantic_score, get_profile_embedding, profile_content_hash
from job.ai_providers import extract_json_from_llm

app = Flask(__name__, static_folder=None)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.secret_key = os.environ.get("SECRET_KEY", "job-scraper-dev-key-change-in-prod")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_DEBUG", "true").lower() not in ("1", "true", "yes")
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30  # 30 days

init_oauth(app)
register_auth_routes(app)

_FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"


def _serve_spa_index():
    index = _FRONTEND_DIST / "index.html"
    if index.is_file():
        return send_file(str(index))
    return "React app not built. Run: npm --prefix frontend run build", 404


def _serve_spa_file(rel_path: str):
    """Serve a file from frontend/dist if it exists; otherwise SPA index (client router)."""
    if rel_path:
        candidate = (_FRONTEND_DIST / rel_path).resolve()
        try:
            candidate.relative_to(_FRONTEND_DIST.resolve())
        except ValueError:
            abort(404)
        if candidate.is_file():
            return send_file(str(candidate))
    return _serve_spa_index()


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


def _call_ai_with_timeout(prompt: str, *, timeout: int = 90) -> str:
    """Guard AI extraction routes so the UI is never left waiting forever.

    Runs in a worker thread, so Flask ``g`` is unavailable there — copy the
    current user into a contextvar so per-user ``.env`` keys (Gemini/Groq)
    still resolve.
    """
    from job.user_context import get_current_user_id, user_context

    uid = get_current_user_id()

    def _run() -> str:
        with user_context(uid):
            return call_ai(prompt)

    executor = futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_run)
        return future.result(timeout=timeout)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _read_config_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_config_yaml(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


_DEFAULT_WORK_STYLES = (RemoteType.REMOTE, RemoteType.HYBRID)


def _norm_config_value(value) -> str:
    return str(value or "").strip().lower()


def _norm_config_set(values) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {_norm_config_value(v) for v in values if _norm_config_value(v)}


def _work_styles_for_search(search: dict) -> set[str]:
    styles = search.get("work_styles")
    if isinstance(styles, list):
        valid = {str(s) for s in styles if str(s) in RemoteType.ALL}
        if valid:
            return valid
    return {RemoteType.HYBRID, RemoteType.ONSITE} if search.get("remote") is False else set(_DEFAULT_WORK_STYLES)


def _companies_covered(old_search: dict, new_search: dict) -> bool:
    old_companies = _norm_config_set(old_search.get("companies"))
    new_companies = _norm_config_set(new_search.get("companies"))
    if not old_companies:
        return True
    if not new_companies:
        return False
    return new_companies.issubset(old_companies)


def _max_pages(search: dict) -> int:
    try:
        return int(search.get("max_pages") or 3)
    except (TypeError, ValueError):
        return 3


def _search_covers(old_search: dict, new_search: dict) -> bool:
    if _norm_config_value(old_search.get("source")) != _norm_config_value(new_search.get("source")):
        return False
    if _norm_config_value(old_search.get("query")) != _norm_config_value(new_search.get("query")):
        return False
    if _norm_config_value(old_search.get("location")) != _norm_config_value(new_search.get("location")):
        return False
    if _max_pages(old_search) < _max_pages(new_search):
        return False
    if not _work_styles_for_search(new_search).issubset(_work_styles_for_search(old_search)):
        return False
    return _companies_covered(old_search, new_search)


def _allowed_terms_covered(old_values, new_values) -> bool:
    old_set = _norm_config_set(old_values)
    new_set = _norm_config_set(new_values)
    if not old_set:
        return True
    if not new_set:
        return False
    return new_set.issubset(old_set)


def _exclusions_covered(old_values, new_values) -> bool:
    # Adding exclusions is narrowing and can be handled locally; removing one
    # can reveal jobs that were skipped during fetch, so it needs a scrape.
    return _norm_config_set(old_values).issubset(_norm_config_set(new_values))


def _config_fetch_required(old_config: dict, new_config: dict) -> bool:
    old_searches = old_config.get("searches") if isinstance(old_config.get("searches"), list) else []
    new_searches = new_config.get("searches") if isinstance(new_config.get("searches"), list) else []
    if not old_searches:
        return True
    if not _allowed_terms_covered(old_config.get("title_filter"), new_config.get("title_filter")):
        return True
    if not _exclusions_covered(old_config.get("blacklist"), new_config.get("blacklist")):
        return True
    if not _exclusions_covered(old_config.get("company_blacklist"), new_config.get("company_blacklist")):
        return True
    return any(
        not any(_search_covers(old_search, new_search) for old_search in old_searches)
        for new_search in new_searches
    )


def _save_api_key(env_key: str, provider: str):
    data = request.get_json() or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "No key provided"}), 400
    write_user_env_var(env_key, key)
    # Prefer the provider the user just configured (setup + AI settings).
    pref = {"groq": "groq", "gemini": "gemini", "anthropic": "anthropic"}.get(provider)
    if pref:
        write_user_env_var("PREFERRED_PROVIDER", pref)
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
    if not safe_profile_dir(slug):
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
    company_variants = _company_keys(company)
    search_dirs: list[Path] = []
    for co in company_variants:
        search_dirs.append(profile_dir / co / subdir)
        search_dirs.append(profile_dir / co / "resumes")
        search_dirs.append(profile_dir / "resumes" / co)

    seen: set[Path] = set()
    for d in search_dirs:
        if d in seen or not d.is_dir():
            continue
        seen.add(d)
        matches = sorted(d.glob(f"*{suffix}"))
        if matches:
            return str(matches[0])
    return None


def _company_keys(company: str) -> list[str]:
    return [
        company,
        company.replace(" ", ""),
        company.replace(" ", "").replace("/", ""),
    ]


def _register_pdf_index_entry(index: dict[tuple[str, str], str], company: str, suffix: str, path: Path) -> None:
    for key in _company_keys(company):
        k = (key, suffix)
        if k not in index:
            index[k] = str(path)


def _build_pdf_index(profile_dir: Path) -> dict[tuple[str, str], str]:
    """One filesystem scan per /api/jobs request — maps (company, suffix) → pdf path."""
    index: dict[tuple[str, str], str] = {}
    if not profile_dir.is_dir():
        return index

    for co_dir in profile_dir.iterdir():
        if not co_dir.is_dir() or co_dir.name == "resumes":
            continue
        for sub, suffix in (("resumes", "_Resume.pdf"), ("cover-letters", "_Cover_Letter.pdf")):
            d = co_dir / sub
            if not d.is_dir():
                continue
            for pdf in sorted(d.glob(f"*{suffix}")):
                _register_pdf_index_entry(index, co_dir.name, suffix, pdf)
        resumes_here = co_dir / "resumes"
        if resumes_here.is_dir():
            for suffix in ("_Resume.pdf", "_Cover_Letter.pdf"):
                for pdf in sorted(resumes_here.glob(f"*{suffix}")):
                    _register_pdf_index_entry(index, co_dir.name, suffix, pdf)

    legacy = profile_dir / "resumes"
    if legacy.is_dir():
        for co_dir in legacy.iterdir():
            if not co_dir.is_dir():
                continue
            for suffix in ("_Resume.pdf", "_Cover_Letter.pdf"):
                for pdf in sorted(co_dir.glob(f"*{suffix}")):
                    _register_pdf_index_entry(index, co_dir.name, suffix, pdf)

    return index


def _lookup_pdf_index(index: dict[tuple[str, str], str] | None, company: str, suffix: str) -> str | None:
    if not index:
        return None
    for key in _company_keys(company):
        path = index.get((key, suffix))
        if path:
            return path
    return None


def _build_match(
    r: dict,
    profile: dict | None,
    profile_vec: list | None,
    profile_hash: str | None = None,
    *,
    persist_cache: bool = False,
) -> dict | None:
    """Assemble the match signal: keyword overlap + semantic fit score."""
    if profile_hash:
        cached = r.get("match_cache")
        if cached and (r.get("match_profile_hash") or "") == profile_hash:
            try:
                return _json.loads(cached)
            except Exception:
                pass

    km = compute_match(match_text(r), profile)
    sem = None
    emb_raw = r.get("embedding")
    if emb_raw and profile_vec:
        try:
            sem = semantic_score(_json.loads(emb_raw), profile_vec)
        except Exception:
            sem = None
    if km is None and sem is None:
        return None
    keyword_score = km["keyword_score"] if km else None
    result = {
        "matched": km["matched"] if km else [],
        "missing": km["missing"] if km else [],
        "matched_count": km["matched_count"] if km else 0,
        "keyword_score": keyword_score,
        "semantic_score": sem,
        "score": sem if sem is not None else (keyword_score or 0),
        "score_kind": "fit" if sem is not None else "skills",
    }
    if persist_cache and profile_hash:
        job_id = r.get("job_id")
        if job_id:
            try:
                set_job_match_cache(job_id, profile_hash, _json.dumps(result))
            except Exception:
                pass
    return result


def _serialize_job(
    row,
    task_status: dict,
    cl_task_status: dict,
    profile: dict | None = None,
    profile_vec: list | None = None,
    *,
    profile_hash: str | None = None,
    persist_match_cache: bool = False,
    pdf_index: dict[tuple[str, str], str] | None = None,
    persist_remote: bool = True,
) -> dict:
    r = dict(row)
    job_id = r["job_id"]
    company = r.get("company") or ""
    title = r.get("title") or ""
    location = r.get("location") or ""
    remote = _maybe_update_remote_from_text(
        job_id,
        title,
        location,
        r.get("description") or "",
        r.get("remote") or "",
        persist=persist_remote,
    )

    ts = task_status.get(job_id, {})
    resume_status = ts.get("status", "idle")
    pdf_path = ts.get("pdf_path")

    cl_ts = cl_task_status.get(job_id, {})
    cl_status = cl_ts.get("status", "idle")
    cl_pdf_path = cl_ts.get("pdf_path")

    try:
        profile_dir = _resumes_path()
        if resume_status == "idle" and not pdf_path:
            pdf_path = _lookup_pdf_index(pdf_index, company, "_Resume.pdf")
            if pdf_path is None and pdf_index is None:
                pdf_path = _find_pdf_path(profile_dir, company, "resumes", "_Resume.pdf")
            if pdf_path:
                resume_status = "done"
        if cl_status == "idle" and not cl_pdf_path:
            cl_pdf_path = _lookup_pdf_index(pdf_index, company, "_Cover_Letter.pdf")
            if cl_pdf_path is None and pdf_index is None:
                cl_pdf_path = _find_pdf_path(profile_dir, company, "cover-letters", "_Cover_Letter.pdf")
            if cl_pdf_path:
                cl_status = "done"
    except RuntimeError:
        pass

    return {
        "job_id": job_id,
        "url": r.get("url") or "",
        "title": title,
        "company": company,
        "location": location,
        "remote": remote,
        "experience": r.get("experience") or "",
        "age": _format_relative_age(r.get("first_seen_at")),
        "posted": _format_posted(r.get("posted_at")),
        "posted_at": r.get("posted_at") or "",
        "first_seen_at": r.get("first_seen_at") or "",
        "status": r.get("status") or "pending",
        "source": _source_label(r.get("search_name") or ""),
        "match": _build_match(
            r, profile, profile_vec, profile_hash, persist_cache=persist_match_cache,
        ),
        "resume_status": resume_status,
        "resume_stage": ts.get("stage", ""),
        "pdf_url": _pdf_url(pdf_path),
        "resume_error": ts.get("error"),
        "cl_status": cl_status,
        "cl_stage": cl_ts.get("stage", ""),
        "cl_pdf_url": _pdf_url(cl_pdf_path),
        "cl_error": cl_ts.get("error"),
    }


def _should_apply_remote_inference(current: str, inferred: str) -> bool:
    if not inferred or inferred == RemoteType.UNKNOWN or inferred == current:
        return False
    if current in ("", RemoteType.UNKNOWN):
        return True
    return inferred == RemoteType.HYBRID and current != RemoteType.HYBRID


def _maybe_update_remote_from_text(job_id: str, title: str, location: str,
                                   description: str, current: str, *, persist: bool = True) -> str:
    if not description:
        return current or ""
    from job.fetcher_utils import infer_remote
    inferred = infer_remote(title, location, description, default=RemoteType.UNKNOWN)
    if not _should_apply_remote_inference(current or "", inferred):
        return current or ""
    if persist:
        from job.db import update_remote
        update_remote(job_id, inferred)
    return inferred


# ── Main routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return _serve_spa_index()


@app.route("/profiles")
def profile_picker():
    return _serve_spa_index()


@app.route("/api/profiles/<slug>/clear-jobs", methods=["POST"])
def api_profile_clear_jobs(slug):
    if err := _require_profile_dir(slug): return err
    import sqlite3
    profile_dir = safe_profile_dir(slug)
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
    return _serve_spa_index()


@app.route("/manage-profiles")
def manage_profiles():
    return _serve_spa_index()


@app.route("/ai-settings")
def ai_settings_page():
    return _serve_spa_index()


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
    profile_dir = safe_profile_dir(slug)
    profile_md = profile_dir / "profile.md"
    return jsonify({"content": profile_md.read_text(encoding="utf-8") if profile_md.exists() else ""})


@app.route("/api/profiles/<slug>/profile-md", methods=["POST"])
def api_profile_md_save(slug):
    if err := _require_profile_dir(slug): return err
    profile_dir = safe_profile_dir(slug)
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
    profile_dir = safe_profile_dir(slug)
    if not profile_dir:
        return jsonify({"error": "Profile not found"}), 404
    config_p = profile_dir / "config.yaml"
    if not config_p.exists():
        return jsonify({"searches": [], "title_filter": [], "blacklist": [], "company_blacklist": []})
    return jsonify(_read_config_yaml(config_p))


@app.route("/api/profiles/<slug>/config", methods=["POST"])
def api_profile_config_save(slug):
    if err := _require_profile_dir(slug): return err
    profile_dir = safe_profile_dir(slug)
    data = request.get_json() or {}
    if not isinstance(data.get("searches"), list) or not data["searches"]:
        return jsonify({"error": "At least one search entry required"}), 400
    config_p = profile_dir / "config.yaml"
    old_config = _read_config_yaml(config_p) if config_p.exists() else {}
    fetch_required = _config_fetch_required(old_config, data)
    _write_config_yaml(config_p, data)
    if slug == get_active_slug():
        clear_task_state()
    return jsonify({"ok": True, "fetch_required": fetch_required})


@app.route("/job/<job_id>")
def job_detail_page(job_id):
    return _serve_spa_index()


@app.route("/api/job/<job_id>/description")
def api_job_description(job_id):
    """Return description for a job — from DB if stored, otherwise scrape on demand
    via the source's declared describe capability (see job.fetcher.SOURCE_REGISTRY).
    Re-infer workplace type from the full text when it carries a better signal."""
    row = get_job(job_id)
    if not row:
        return jsonify({"error": "Job not found"}), 404

    r = dict(row)
    description = r.get("description") or ""
    remote = r.get("remote") or ""

    from job.fetcher import fetch_description as _fetch_desc, should_fetch_description
    if should_fetch_description(job_id, description):
        from job.db import update_description
        fetched_description = _fetch_desc(job_id, r.get("url") or "")
        if fetched_description and len(fetched_description) > len(description):
            description = fetched_description
            update_description(job_id, description)
    remote = _maybe_update_remote_from_text(
        job_id,
        r.get("title") or "",
        r.get("location") or "",
        description,
        remote,
    )

    # Lazily compute + cache this job's embedding (off the list render path) so
    # the detail card and future list loads get the semantic score.
    from job.db import get_job_embedding, set_job_embedding
    from job.ai_providers import embed_text
    from job.match import semantic_enabled
    emb = get_job_embedding(job_id)
    if emb is None and description and semantic_enabled():
        emb = embed_text(match_text({"title": r.get("title") or "", "description": description}))
        if emb:
            set_job_embedding(job_id, emb)

    _prof = get_profile_json()
    profile_hash = profile_content_hash(_prof)
    row_for_match = {
        "job_id": job_id,
        "title": r.get("title") or "",
        "description": description,
        "embedding": _json.dumps(emb) if emb else r.get("embedding"),
        "match_cache": r.get("match_cache"),
        "match_profile_hash": r.get("match_profile_hash"),
    }
    match = _build_match(
        row_for_match, _prof, get_profile_embedding(_prof), profile_hash, persist_cache=bool(profile_hash),
    )
    return jsonify({"description": description, "remote": remote, "match": match})


@app.route("/api/job/<job_id>")
def api_job_detail(job_id):
    row = get_job(job_id)
    if not row:
        return jsonify({"error": "Job not found"}), 404
    ts = get_task_status(job_id)
    cl_ts = get_cl_task_status(job_id)
    _prof = get_profile_json()
    profile_hash = profile_content_hash(_prof)
    profile_vec = get_profile_embedding(_prof)
    data = _serialize_job(
        row, {job_id: ts}, {job_id: cl_ts}, _prof, profile_vec,
        profile_hash=profile_hash,
        persist_match_cache=bool(profile_hash),
        persist_remote=True,
    )
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
    profile = get_profile_json()
    profile_hash = profile_content_hash(profile) or ""
    profile_vec = get_profile_embedding(profile)
    rows, stale_ids = get_jobs_list_by_status(status_filter, profile_hash)
    descriptions = get_job_descriptions(stale_ids) if stale_ids else {}
    task_statuses = {row["job_id"]: get_task_status(row["job_id"]) for row in rows}
    cl_task_statuses = {row["job_id"]: get_cl_task_status(row["job_id"]) for row in rows}
    try:
        pdf_index = _build_pdf_index(_resumes_path())
    except RuntimeError:
        pdf_index = {}
    payload = []
    for row in rows:
        r = dict(row)
        if r["job_id"] in descriptions:
            r["description"] = descriptions[r["job_id"]]
        else:
            r.setdefault("description", "")
        payload.append(_serialize_job(
            r,
            task_statuses,
            cl_task_statuses,
            profile,
            profile_vec,
            profile_hash=profile_hash or None,
            persist_match_cache=bool(profile_hash),
            pdf_index=pdf_index,
            persist_remote=False,
        ))
    return jsonify(payload)


@app.route("/api/job-counts")
def api_job_counts():
    counts = stats()
    return jsonify({"pending": counts.get("pending", 0), "applied": counts.get("applied", 0), "skipped": counts.get("skipped", 0)})


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
    old_config = _read_config_yaml(config_p) if config_p.exists() else {}
    fetch_required = _config_fetch_required(old_config, data)
    _write_config_yaml(config_p, data)
    clear_task_state()
    return jsonify({"ok": True, "fetch_required": fetch_required})


@app.route("/api/ai-settings", methods=["GET"])
def api_ai_settings_get():
    groq_ok      = _get_groq_client() is not None
    anthropic_ok = _get_anthropic_client() is not None
    gemini_ok    = _get_gemini_client() is not None or bool(shutil.which("gemini"))
    openrouter_ok = _get_openrouter_client() is not None

    preferred = _env_get("PREFERRED_PROVIDER", "").strip().lower()

    # active = preferred if it's available, else first available in default order
    if preferred == "groq" and groq_ok:           active = "groq"
    elif preferred == "anthropic" and anthropic_ok: active = "anthropic"
    elif preferred == "gemini" and gemini_ok:     active = "gemini"
    elif preferred == "openrouter" and openrouter_ok: active = "openrouter"
    elif groq_ok:                                 active = "groq"
    elif anthropic_ok:                            active = "anthropic"
    elif gemini_ok:                               active = "gemini"
    elif openrouter_ok:                           active = "openrouter"
    else:                                         active = None

    def _models_for(provider):
        """Live list with the currently-selected model guaranteed present."""
        models = _list_models(provider)
        current = _get_model(provider)
        if current and current not in models:
            models = [current] + models
        return models

    # Masked keys only — never return full secrets over the network.
    groq_key      = _env_get("GROQ_API_KEY", "")
    anthropic_key = _env_get("ANTHROPIC_API_KEY") or _env_get("ANTHROPIC_AUTH_TOKEN") or ""
    gemini_key    = _env_get("GEMINI_API_KEY") or _env_get("GOOGLE_API_KEY") or ""
    openrouter_key = _env_get("OPENROUTER_API_KEY", "")

    # Token-usage counter: what THIS app has spent per provider, scoped to the
    # currently-active API key (limits are per-key/org, so switching keys must
    # show a fresh count). Best-effort — no profile / empty DB yields zeros.
    from job.limits import usage_reference
    from job.ai_providers import _key_fingerprint
    key_ids = {p: _key_fingerprint(p) for p in ("groq", "gemini", "anthropic", "openrouter")}
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

    from job.ai_providers import embedding_provider
    emb_available = embedding_provider() is not None
    semantic_on = _env_get("SEMANTIC_MATCH", "on").strip().lower() != "off"

    return jsonify({
        "active_provider":    active,
        "preferred_provider": preferred or None,
        "semantic_match":     semantic_on,
        "embeddings_available": emb_available,
        "providers": {
            "groq": {
                "configured": groq_ok,
                "model":   _get_model("groq"),
                "key_set": bool(groq_key),
                "key":     mask_secret(groq_key),
                "models":  _models_for("groq"),
                "usage":   _usage_for("groq"),
            },
            "anthropic": {
                "configured": anthropic_ok,
                "model":   _get_model("anthropic"),
                "key_set": bool(anthropic_key or shutil.which("claude")),
                "key":     mask_secret(anthropic_key),
                "models":  _models_for("anthropic"),
                "usage":   _usage_for("anthropic"),
            },
            "gemini": {
                "configured": gemini_ok,
                "model":   _get_model("gemini"),
                "key_set": bool(gemini_key or shutil.which("gemini")),
                "key":     mask_secret(gemini_key),
                "models":  _models_for("gemini"),
                "usage":   _usage_for("gemini"),
            },
            "openrouter": {
                "configured": openrouter_ok,
                "model":   _get_model("openrouter"),
                "key_set": bool(openrouter_key),
                "key":     mask_secret(openrouter_key),
                "models":  _models_for("openrouter"),
                "usage":   _usage_for("openrouter"),
            },
            "claude": {
                "configured": bool(shutil.which("claude")),
                "model":   "claude-cli",
                "key_set": bool(shutil.which("claude")),
                "key":     "",
                "models":  [],
                "usage":   {},
            },
        }
    })


@app.route("/api/ai-settings", methods=["POST"])
def api_ai_settings_save():
    data = request.get_json() or {}
    updated_keys = set()

    for field, env_key in [("groq_model", "GROQ_MODEL"), ("anthropic_model", "ANTHROPIC_MODEL"), ("gemini_model", "GEMINI_MODEL"), ("openrouter_model", "OPENROUTER_MODEL")]:
        val = (data.get(field) or "").strip()
        if val:
            write_user_env_var(env_key, val)
            updated_keys.add(env_key)

    preferred = (data.get("preferred_provider") or "").strip().lower()
    if preferred in ("groq", "anthropic", "gemini", "claude", "openrouter", ""):
        if preferred == "anthropic" and not (data.get("anthropic_model") or "").strip():
            default_model = _MODEL_DEFAULTS["anthropic"]
            write_user_env_var("ANTHROPIC_MODEL", default_model)
            updated_keys.add("ANTHROPIC_MODEL")
        if preferred:
            write_user_env_var("PREFERRED_PROVIDER", preferred)
        else:
            remove_user_env_var("PREFERRED_PROVIDER")
        updated_keys.add("PREFERRED_PROVIDER")

    if "semantic_match" in data:
        val = "on" if data.get("semantic_match") else "off"
        write_user_env_var("SEMANTIC_MATCH", val)
        updated_keys.add("SEMANTIC_MATCH")

    clear_task_state()
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
            if not _env_get("GROQ_API_KEY"):
                return jsonify({"ok": False, "error": "GROQ_API_KEY is not set. Add your key in AI Settings."})
            try:
                from groq import Groq  # noqa: F401
            except ImportError:
                return jsonify({"ok": False, "error": "groq package not installed. Close the app, run npm run dev (or npm run backend), then try again."})
        elif provider == "anthropic":
            if not (_env_get("ANTHROPIC_API_KEY") or _env_get("ANTHROPIC_AUTH_TOKEN") or shutil.which("claude")):
                return jsonify({"ok": False, "error": "No Anthropic credentials found. Add an API key or install Claude Code."})
        elif provider == "gemini":
            if not (_env_get("GEMINI_API_KEY") or _env_get("GOOGLE_API_KEY") or shutil.which("gemini")):
                return jsonify({"ok": False, "error": "No Gemini credentials found. Add an API key or install the Gemini CLI."})
        elif provider == "claude":
            if not shutil.which("claude"):
                return jsonify({"ok": False, "error": "Claude Code CLI not found. Install it with: npm install -g @anthropic-ai/claude-code"})
        elif provider == "openrouter":
            if not _env_get("OPENROUTER_API_KEY"):
                return jsonify({"ok": False, "error": "OPENROUTER_API_KEY is not set. Add your key in AI Settings."})

        t0 = time.time()
        if provider == "groq":
            result = _build_with_groq("You are a test.", "Say OK in one word.")
        elif provider == "anthropic":
            result = _build_with_sdk("You are a test.", "Say OK in one word.")
        elif provider == "openrouter":
            result = _build_with_openrouter("You are a test.", "Say OK in one word.")
        elif provider == "gemini":
            from job.web_api import _skill_path
            backend_out = []
            result = _build_with_gemini("You are a test.", "Say OK in one word.", cwd=str(_skill_path()), backend_out=backend_out)
            backend = backend_out[0] if backend_out else None
        elif provider == "claude":
            from job.ai_providers import _build_with_claude_cli
            from job.web_api import _skill_path
            result = _build_with_claude_cli("You are a test.", "Say OK in one word.", cwd=str(_skill_path()))
        else:
            return jsonify({"ok": False, "error": f"Unknown provider: {provider}"}), 400
        latency = round((time.time() - t0) * 1000)
        return jsonify({"ok": True, "model": _get_model(provider) if provider != "claude" else "claude-cli", "latency_ms": latency,
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
    started = trigger_fetch()
    if not started:
        st = get_fetch_status()
        return jsonify({
            "status": st.get("status", "idle"),
            "started": False,
            "message": st.get("message", "Could not start fetch"),
        }), 429
    return jsonify({"status": "running", "started": True})


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
    resp = _serve_spa_index()
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


def _flask_debug() -> bool:
    return os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")


def _require_setup_dev():
    """Block host-install setup actions outside FLASK_DEBUG (Docker/Fly prod)."""
    if _flask_debug():
        return None
    return jsonify({"ok": False, "error": "Install helpers are only available in development mode."}), 403


@app.route("/api/setup/status")
def api_setup_status():
    profile_p = get_profile_path()
    anthropic_key = _env_get("ANTHROPIC_API_KEY") or _env_get("ANTHROPIC_AUTH_TOKEN") or ""
    return jsonify({
        "platform": sys.platform,
        "debug": _flask_debug(),
        "has_claude": bool(shutil.which("claude")),
        "has_gemini": bool(shutil.which("gemini")),
        "has_pdflatex": bool(shutil.which("pdflatex")),
        "has_node": bool(shutil.which("node")),
        "has_profile": bool(profile_p and profile_p.exists()),
        "gemini_key_set": bool(_env_get("GEMINI_API_KEY") or _env_get("GOOGLE_API_KEY")),
        "groq_key_set": bool(_env_get("GROQ_API_KEY")),
        "anthropic_key_set": bool(anthropic_key),
        "openrouter_key_set": bool(_env_get("OPENROUTER_API_KEY")),
        # Masked keys only — full secrets are never returned over the API.
        "gemini_key": mask_secret(_env_get("GEMINI_API_KEY") or _env_get("GOOGLE_API_KEY")),
        "groq_key": mask_secret(_env_get("GROQ_API_KEY")),
        "anthropic_key": mask_secret(anthropic_key),
        "openrouter_key": mask_secret(_env_get("OPENROUTER_API_KEY")),
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
        output = _call_ai_with_timeout(prompt)
        extracted = extract_json_from_llm(output)

        titles = extracted.get("titles", [])
        location = extracted.get("location", "United States")
        remote = extracted.get("remote", True)

        if not titles:
            return jsonify({"ok": False, "error": "Could not extract job titles from profile."})

        config_p = _config_path()
        existing = _read_config_yaml(config_p) if config_p.exists() else {}

        work_styles = ['Remote', 'Hybrid', 'On-site'] if not remote else ['Remote', 'Hybrid']
        searches = [
            {
                "group_id": f"search-{title_idx + 1}",
                "name": f"{src} - {title}",
                "source": src,
                "query": title,
                "location": location,
                "max_pages": mp,
                "remote": remote,
                "work_styles": work_styles,
            }
            for title_idx, title in enumerate(titles)
            for src, mp in SOURCES
        ]

        new_config = {
            "searches": searches,
            "title_filter": [t.lower() for t in titles],
            "blacklist": existing.get("blacklist", DEFAULT_BLACKLIST),
            "company_blacklist": existing.get("company_blacklist", []),
        }

        config_p.parent.mkdir(parents=True, exist_ok=True)
        _write_config_yaml(config_p, new_config)

        return jsonify({"ok": True, "searches": searches, "title_filter": new_config["title_filter"], "location": location})
    except (subprocess.TimeoutExpired, futures.TimeoutError):
        return jsonify({"ok": False, "error": "AI extraction timed out. Try again."})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Could not parse AI response: {e}"})


@app.route("/api/setup/claude-login", methods=["POST"])
def api_setup_claude_login():
    blocked = _require_setup_dev()
    if blocked:
        return blocked
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
    blocked = _require_setup_dev()
    if blocked:
        return blocked
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
    blocked = _require_setup_dev()
    if blocked:
        return blocked
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


@app.route("/api/setup/save-openrouter-key", methods=["POST"])
def api_setup_save_openrouter_key():
    return _save_api_key("OPENROUTER_API_KEY", "openrouter")


@app.route("/api/setup/install-pdflatex", methods=["POST"])
def api_setup_install_pdflatex():
    blocked = _require_setup_dev()
    if blocked:
        return blocked
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

    # Normalize double-spaces and redundant newlines that pypdf introduces
    import re as _re
    raw_text = _re.sub(r'[ \t]{2,}', ' ', raw_text)
    raw_text = _re.sub(r'\n{3,}', '\n\n', raw_text)

    # Limit to 20k chars — enough for even long CVs without hitting token limits
    text_for_ai = raw_text[:20000]

    prompt = f"""Extract ALL structured information from this resume and return ONLY valid JSON. No markdown, no explanation, just JSON.

Use exactly this structure:
{{
  "name": "Full Name",
  "email": "email@example.com",
  "phone": "+1 555-000-0000",
  "location": "City, Country",
  "linkedin": "https://linkedin.com/in/...",
  "auth": "",
  "summary": "2-3 sentence professional summary",
  "competencies": ["skill 1", "skill 2", "skill 3"],
  "experience": [
    {{
      "title": "Exact Job Title",
      "company": "Company Name",
      "location": "City, Country",
      "start": "Mon Year",
      "end": "Mon Year or Present",
      "bullets": [
        "Accomplishment or responsibility 1 — extract EVERY bullet/line from this role",
        "Accomplishment or responsibility 2"
      ],
      "projects": [{{"name": "Project Name", "desc": "What you built/did"}}]
    }}
  ],
  "education": [{{"degree": "Full Degree Name", "school": "Institution Name", "year": "2024", "location": "City, Country"}}],
  "certifications": ["Cert Name, Issuer (Year)"]
}}

Critical rules:
- Extract EVERY job role, even short ones
- For each role, extract ALL bullet points, responsibilities, and achievements verbatim — do not summarize or drop any
- If bullets are listed as plain lines under a role, include each line as a separate bullet
- competencies: extract ALL technical skills, tools, languages, frameworks mentioned anywhere
- Empty string for missing text fields, empty array [] for missing list fields
- Return ONLY the JSON object

Resume:
{text_for_ai}"""

    try:
        output = _call_ai_with_timeout(prompt)
        data = extract_json_from_llm(output)
        return jsonify({"ok": True, "data": data})
    except (subprocess.TimeoutExpired, futures.TimeoutError):
        return jsonify({"error": "AI extraction timed out. Try again."}), 504
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
    root = ensure_user_dir()

    # Check if we have a pending new profile from the "Add new profile" flow
    from flask import session
    pending_slug = session.pop("pending_profile_slug", None)

    pending_dir = safe_profile_dir(pending_slug) if pending_slug else None
    if pending_dir:
        profile_dir = pending_dir
        set_active(pending_slug)
        clear_task_state()
    elif not profile_dir:
        slug = create_profile(name)
        profile_dir = safe_profile_dir(slug)
        set_active(slug)

    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "profile.md").write_text(content, encoding="utf-8")

    # Rename the folder to the proper name-based slug if it's still a temp name
    current_slug = profile_dir.name
    proper_slug = slugify(name)
    if current_slug != proper_slug and current_slug.startswith("new-profile-"):
        # Ensure no collision
        target = root / proper_slug
        counter = 1
        while target.exists():
            target = root / f"{proper_slug}-{counter}"
            counter += 1
        profile_dir.rename(target)
        profile_dir = target
        set_active(target.name)

    from job.profiles import _update_symlinks, write_profile_json
    write_profile_json(profile_dir)
    _update_symlinks(profile_dir)
    init_db()
    return jsonify({"ok": True})


@app.route("/app", defaults={"path": ""})
@app.route("/app/<path:path>")
def serve_spa(path: str):
    # Prefer real files (e.g. /app/assets/…) so Vite builds work; fall back to index.
    return _serve_spa_file(path)


@app.route("/login")
def serve_login():
    return _serve_spa_index()


@app.route("/assets/<path:filename>")
def serve_vite_assets(filename: str):
    """Vite default asset path (/assets/…) for production builds."""
    return _serve_spa_file(f"assets/{filename}")


@app.route("/spa-assets/<path:filename>")
def serve_spa_assets(filename: str):
    """Legacy alias used by older docs / auth public-path list."""
    return _serve_spa_file(f"assets/{filename}")


@app.route("/favicon.svg")
@app.route("/favicon.ico")
def serve_favicon():
    for name in ("favicon.svg", "favicon.ico"):
        candidate = _FRONTEND_DIST / name
        if candidate.is_file():
            return send_file(str(candidate))
    abort(404)


if __name__ == "__main__":
    from startup import run_startup
    run_startup()

    debug = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5050"))
    app.run(host=host, debug=debug, port=port)
