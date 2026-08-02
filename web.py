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

from job.db import init_db, get_pending_deduped, get_jobs_by_status, update_status, get_job, stats, last_fetch_at, clear_all_jobs
from job.web_api import trigger_resume, get_task_status, trigger_cover_letter, get_cl_task_status, trigger_fetch, get_fetch_status, clear_task_state
from job.web_api import _candidate_name_slug
from job.profiles import (
    list_profiles, get_active_slug, get_active_profile, set_active,
    create_profile, delete_profile, has_any_profiles, slugify,
    get_profile_path, get_config_path, get_resumes_path, active_profile_dir,
    PROFILES_DIR,
)

BASE = Path(__file__).parent

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.secret_key = os.environ.get("SECRET_KEY", "job-scraper-dev-key-change-in-prod")


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


def _serialize_job(row, task_status: dict, cl_task_status: dict) -> dict:
    r = dict(row)

    age = ""
    try:
        dt = datetime.fromisoformat(r["first_seen_at"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        mins = int(delta.total_seconds() // 60)
        if mins < 60:       age = f"{mins}m"
        elif mins < 1440:   age = f"{mins//60}h"
        else:               age = f"{mins//1440}d"
    except Exception:
        pass

    ts = task_status.get(r["job_id"], {})
    resume_status = ts.get("status", "idle")
    pdf_path = ts.get("pdf_path")

    cl_ts = cl_task_status.get(r["job_id"], {})
    cl_status = cl_ts.get("status", "idle")
    cl_pdf_path = cl_ts.get("pdf_path")

    try:
        resumes = _resumes_path()
        company = r.get("company") or ""
        name_slug = _candidate_name_slug()
        if resume_status == "idle" and not pdf_path:
            target = f"{name_slug}_Resume.pdf"
            for candidate in [
                resumes / company / target,
                resumes / company.replace(" ", "") / target,
                resumes / company.replace(" ", "").replace("/", "") / target,
            ]:
                if candidate.exists():
                    resume_status = "done"
                    pdf_path = str(candidate)
                    break
        if cl_status == "idle" and not cl_pdf_path:
            cl_target = f"{name_slug}_Cover_Letter.pdf"
            for candidate in [
                resumes / company / cl_target,
                resumes / company.replace(" ", "") / cl_target,
                resumes / company.replace(" ", "").replace("/", "") / cl_target,
            ]:
                if candidate.exists():
                    cl_status = "done"
                    cl_pdf_path = str(candidate)
                    break
    except RuntimeError:
        pass

    posted = ""
    try:
        if r.get("posted_at"):
            dt = datetime.fromisoformat(r["posted_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - dt
            days = int(delta.total_seconds() // 86400)
            if days == 0:   posted = "today"
            elif days == 1: posted = "1d ago"
            else:           posted = f"{days}d ago"
    except Exception:
        pass

    return {
        "job_id": r["job_id"],
        "url": r.get("url") or "",
        "title": r.get("title") or "",
        "company": r.get("company") or "",
        "location": r.get("location") or "",
        "remote": r.get("remote") or "",
        "experience": r.get("experience") or "",
        "age": age,
        "posted": posted,
        "status": r.get("status") or "pending",
        "source": _source_label(r.get("search_name") or ""),
        "resume_status": resume_status,
        "resume_stage": ts.get("stage", ""),
        "pdf_url": f"/pdf/{Path(pdf_path).parent.name}/{Path(pdf_path).name}" if pdf_path else None,
        "resume_error": ts.get("error"),
        "cl_status": cl_status,
        "cl_stage": cl_ts.get("stage", ""),
        "cl_pdf_url": f"/pdf/{Path(cl_pdf_path).parent.name}/{Path(cl_pdf_path).name}" if cl_pdf_path else None,
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
    profile_dir = PROFILES_DIR / slug
    if not profile_dir.is_dir():
        return jsonify({"error": "Profile not found"}), 404
    import sqlite3
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


# ── Profile API ───────────────────────────────────────────────────────────────

@app.route("/api/profiles")
def api_profiles_list():
    profiles = list_profiles()
    active_slug = get_active_slug()
    return jsonify({
        "profiles": [
            {"slug": p.slug, "name": p.name, "initials": p.initials, "color": p.color, "active": p.slug == active_slug}
            for p in profiles
        ],
        "active_slug": active_slug,
    })


@app.route("/api/profiles/active")
def api_profiles_active():
    active = get_active_profile()
    if not active:
        return jsonify({"active": None})
    return jsonify({"active": {"slug": active.slug, "name": active.name, "initials": active.initials, "color": active.color}})


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
    job_count = stats().get("pending", 0) + stats().get("applied", 0) + stats().get("skipped", 0)
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
    profile_dir = PROFILES_DIR / slug
    if not profile_dir.is_dir():
        return jsonify({"error": "Profile not found"}), 404
    profile_md = profile_dir / "profile.md"
    return jsonify({"content": profile_md.read_text() if profile_md.exists() else ""})


@app.route("/api/profiles/<slug>/profile-md", methods=["POST"])
def api_profile_md_save(slug):
    profile_dir = PROFILES_DIR / slug
    if not profile_dir.is_dir():
        return jsonify({"error": "Profile not found"}), 404
    data = request.get_json()
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Profile content is empty"}), 400
    (profile_dir / "profile.md").write_text(content)
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
    with open(config_p) as f:
        return jsonify(yaml.safe_load(f) or {})


@app.route("/api/profiles/<slug>/config", methods=["POST"])
def api_profile_config_save(slug):
    profile_dir = PROFILES_DIR / slug
    if not profile_dir.is_dir():
        return jsonify({"error": "Profile not found"}), 404
    data = request.get_json()
    if not isinstance(data.get("searches"), list) or not data["searches"]:
        return jsonify({"error": "At least one search entry required"}), 400
    config_p = profile_dir / "config.yaml"
    with open(config_p, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    # If active profile, clear and re-fetch
    if slug == get_active_slug():
        clear_all_jobs()
        clear_task_state()
    return jsonify({"ok": True})


# ── Job routes ────────────────────────────────────────────────────────────────

@app.route("/api/jobs")
def api_jobs():
    status_filter = request.args.get("status", "pending")
    rows = get_jobs_by_status(status_filter)
    task_statuses = {row["job_id"]: get_task_status(row["job_id"]) for row in rows}
    cl_task_statuses = {row["job_id"]: get_cl_task_status(row["job_id"]) for row in rows}
    return jsonify([_serialize_job(row, task_statuses, cl_task_statuses) for row in rows])


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
    pdf_url = None
    if ts.get("pdf_path"):
        p = Path(ts["pdf_path"])
        pdf_url = f"/pdf/{p.parent.name}/{p.name}"
    return jsonify({"status": ts.get("status", "idle"), "stage": ts.get("stage", ""), "pdf_url": pdf_url, "error": ts.get("error")})


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
    pdf_url = None
    if ts.get("pdf_path"):
        p = Path(ts["pdf_path"])
        pdf_url = f"/pdf/{p.parent.name}/{p.name}"
    return jsonify({"status": ts.get("status", "idle"), "stage": ts.get("stage", ""), "pdf_url": pdf_url, "error": ts.get("error")})


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
    with open(config_p) as f:
        data = yaml.safe_load(f)
    return jsonify(data)


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
    with open(config_p, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return jsonify({"ok": True})


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


@app.route("/pdf/<company>/<filename>")
def serve_pdf(company, filename):
    pdf = _resumes_path() / company / filename
    if not pdf.exists():
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
    })


@app.route("/api/setup/suggest-config", methods=["POST"])
def api_setup_suggest_config():
    profile_p = get_profile_path()
    if not profile_p or not profile_p.exists():
        return jsonify({"ok": False, "error": "Profile not found. Complete Step 4 first."})

    profile_text = profile_p.read_text()
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

    ai_cmd = ["claude", "-p", prompt, "--output-format", "text"] if shutil.which("claude") else \
              (["gemini", "-p", prompt] if shutil.which("gemini") else None)
    if not ai_cmd:
        return jsonify({"ok": False, "error": "No AI CLI installed. Complete Step 2 first."})

    try:
        result = subprocess.run(ai_cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout.strip()
        stderr = result.stderr.strip()

        if not output:
            hint = " Make sure you have logged in ('claude login') or set your GEMINI_API_KEY."
            return jsonify({"ok": False, "error": f"AI CLI returned no response.{hint} Detail: {stderr[:200] or 'none'}"})

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
        existing = {}
        if config_p.exists():
            with open(config_p) as f:
                existing = yaml.safe_load(f) or {}

        primary_title = titles[0]
        searches = [
            {"name": f"{src.capitalize()} - {primary_title}", "source": src,
             "query": primary_title, "location": location, "max_pages": mp, "remote": remote}
            for src, mp in [("linkedin", 3), ("jobicy", 3), ("himalayas", 2), ("greenhouse", 3)]
        ]

        new_config = {
            "searches": searches,
            "title_filter": [t.lower() for t in titles],
            "blacklist": existing.get("blacklist", ["internship", "junior", "unpaid", "staffing"]),
            "company_blacklist": existing.get("company_blacklist", []),
        }

        clear_all_jobs()
        clear_task_state()

        config_p.parent.mkdir(parents=True, exist_ok=True)
        with open(config_p, "w") as f:
            yaml.dump(new_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

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
        subprocess.Popen(["claude", "login"], **kwargs)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/setup/install-node", methods=["POST"])
def api_setup_install_node():
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["brew", "install", "node"], capture_output=True, text=True, timeout=300)
        elif sys.platform == "linux":
            r = subprocess.run(["sudo", "apt-get", "install", "-y", "nodejs", "npm"], capture_output=True, text=True, timeout=300)
        else:
            return jsonify({"ok": False, "output": "Auto-install not supported on Windows. Download from https://nodejs.org/en/download"})
        return jsonify({"ok": r.returncode == 0, "output": (r.stdout or r.stderr)[-500:]})
    except Exception as e:
        return jsonify({"ok": False, "output": str(e)})


@app.route("/api/setup/install-cli", methods=["POST"])
def api_setup_install_cli():
    data = request.get_json()
    provider = data.get("provider")
    if provider not in ("claude", "gemini"):
        return jsonify({"error": "Invalid provider"}), 400
    pkg = "@anthropic-ai/claude-code" if provider == "claude" else "@google/gemini-cli"
    try:
        r = subprocess.run(["npm", "install", "-g", pkg], capture_output=True, text=True, timeout=180)
        return jsonify({"ok": r.returncode == 0, "output": (r.stdout or r.stderr)[-1000:]})
    except Exception as e:
        return jsonify({"ok": False, "output": str(e)})


@app.route("/api/setup/save-groq-key", methods=["POST"])
def api_setup_save_groq_key():
    data = request.get_json()
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "No key provided"}), 400
    env_path = BASE / ".env"
    lines = [l for l in env_path.read_text().splitlines() if not l.startswith("GROQ_API_KEY=")] if env_path.exists() else []
    lines.append(f"GROQ_API_KEY={key}")
    env_path.write_text("\n".join(lines) + "\n")
    os.environ["GROQ_API_KEY"] = key
    return jsonify({"ok": True})


@app.route("/api/setup/save-gemini-key", methods=["POST"])
def api_setup_save_gemini_key():
    data = request.get_json()
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "No key provided"}), 400
    env_path = BASE / ".env"
    lines = [l for l in env_path.read_text().splitlines() if not l.startswith("GEMINI_API_KEY=")] if env_path.exists() else []
    lines.append(f"GEMINI_API_KEY={key}")
    env_path.write_text("\n".join(lines) + "\n")
    os.environ["GEMINI_API_KEY"] = key
    return jsonify({"ok": True})


@app.route("/api/setup/install-pdflatex", methods=["POST"])
def api_setup_install_pdflatex():
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["brew", "install", "--cask", "basictex"], capture_output=True, text=True, timeout=600)
        elif sys.platform == "linux":
            r = subprocess.run(["sudo", "apt-get", "install", "-y", "texlive-latex-extra"], capture_output=True, text=True, timeout=600)
        else:
            return jsonify({"ok": False, "output": "Auto-install not supported on Windows. Install MiKTeX from https://miktex.org/download"})
        return jsonify({"ok": r.returncode == 0, "output": (r.stdout or r.stderr)[-1000:]})
    except Exception as e:
        return jsonify({"ok": False, "output": str(e)})


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

    ai_cmd = ["claude", "-p", prompt, "--output-format", "text"] if shutil.which("claude") else \
              (["gemini", "-p", prompt] if shutil.which("gemini") else None)
    if not ai_cmd:
        return jsonify({"error": "No AI CLI installed. Complete Step 2 first."}), 400

    try:
        result = subprocess.run(ai_cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout.strip()
        stderr = result.stderr.strip()

        # Empty output means the AI CLI failed — likely not logged in
        if not output:
            hint = ""
            if "claude" in ai_cmd[0]:
                hint = " Make sure you have logged in with 'claude login' (or use the login button in the setup wizard)."
            elif "gemini" in ai_cmd[0]:
                hint = " Make sure your GEMINI_API_KEY is set correctly in the setup wizard."
            err_detail = stderr[:300] if stderr else "No output from AI CLI."
            return jsonify({"error": f"AI CLI returned no response. {hint} Detail: {err_detail}"}), 500

        if output.startswith("```"):
            output = "\n".join(output.split("\n")[1:])
            output = output.rsplit("```", 1)[0].strip()
        data = _json.loads(output)
        return jsonify({"ok": True, "data": data})
    except _json.JSONDecodeError:
        return jsonify({"error": f"AI returned unexpected output (not JSON). Raw output: {output[:200]}"}), 500
    except Exception as e:
        return jsonify({"error": f"Could not parse AI response: {e}"}), 500


@app.route("/api/setup/save-profile", methods=["POST"])
def api_setup_save_profile():
    data = request.get_json()
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Profile content is empty"}), 400

    # Extract name from first H1 heading for the slug
    name = "default"
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            name = line.lstrip("#").split("—")[0].split("-")[0].strip() or name
            break

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
    (profile_dir / "profile.md").write_text(content)
    (profile_dir / "resumes").mkdir(exist_ok=True)

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

    from job.profiles import _update_symlinks
    _update_symlinks(profile_dir)
    init_db()
    return jsonify({"ok": True})


if __name__ == "__main__":
    env_path = BASE / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    # Repair symlinks and migrate legacy root resumes/ on startup
    active_slug = get_active_slug()
    if active_slug:
        from job.profiles import _update_symlinks
        _update_symlinks(PROFILES_DIR / active_slug)
        init_db()
        # Migrate any resumes still in the legacy project-root resumes/ folder
        import shutil as _shutil
        legacy_resumes = BASE / "resumes"
        profile_resumes = get_resumes_path()
        if legacy_resumes.exists() and profile_resumes:
            for company_dir in legacy_resumes.iterdir():
                if company_dir.is_dir():
                    dest = profile_resumes / company_dir.name
                    if not dest.exists():
                        _shutil.copytree(company_dir, dest)
    # Clean up orphaned new-profile-* folders (created but never completed)
    if PROFILES_DIR.exists():
        import shutil as _shutil2
        for d in PROFILES_DIR.iterdir():
            if d.is_dir() and d.name.startswith("new-profile-") and not (d / "profile.md").exists():
                _shutil2.rmtree(d, ignore_errors=True)

    # Pre-warm the Anthropic prompt cache in background (1h TTL)
    import threading as _threading
    from job.web_api import _prewarm_cache
    _threading.Thread(target=_prewarm_cache, daemon=True).start()

    app.run(debug=False, port=5050)
