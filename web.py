import os
import sys
import yaml
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request, send_file, abort, redirect, url_for

from job.db import init_db, get_pending_deduped, get_jobs_by_status, update_status, get_job, stats, last_fetch_at
from job.web_api import trigger_resume, get_task_status, trigger_cover_letter, get_cl_task_status, trigger_fetch, get_fetch_status
from job.web_api import _candidate_name_slug

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.yaml"
SKILL_PATH = BASE / "resume-skill"
PROFILE_PATH = SKILL_PATH / "references" / "profile.md"
RESUMES_PATH = BASE / "resumes"

app = Flask(__name__, template_folder="templates")
init_db()


def _source_label(search_name: str) -> str:
    n = search_name.lower()
    if "linkedin" in n:
        return "LinkedIn"
    if "jobicy" in n:
        return "Jobicy"
    if "himalayas" in n:
        return "Himalayas"
    if "greenhouse" in n:
        return "Greenhouse"
    return search_name.split("-")[0].strip() if search_name else ""


def _serialize_job(row, task_status: dict, cl_task_status: dict) -> dict:
    r = dict(row)
    salary = ""
    if r.get("salary_min") and r.get("salary_max"):
        salary = f"${r['salary_min']//1000}k–${r['salary_max']//1000}k"
    elif r.get("salary_min"):
        salary = f"${r['salary_min']//1000}k+"

    # Age
    age = ""
    try:
        dt = datetime.fromisoformat(r["first_seen_at"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        mins = int(delta.total_seconds() // 60)
        if mins < 60:
            age = f"{mins}m"
        elif mins < 1440:
            age = f"{mins//60}h"
        else:
            age = f"{mins//1440}d"
    except Exception:
        pass

    # Resume state
    ts = task_status.get(r["job_id"], {})
    resume_status = ts.get("status", "idle")
    pdf_path = ts.get("pdf_path")

    # Cover letter state
    cl_ts = cl_task_status.get(r["job_id"], {})
    cl_status = cl_ts.get("status", "idle")
    cl_pdf_path = cl_ts.get("pdf_path")

    # Check if PDF already exists on disk (from previous run).
    # Skill may sanitize the company name for the folder, so try a few variants then fall back to scanning.
    if resume_status == "idle" and not pdf_path:
        company = r.get("company") or ""
        name_slug = _candidate_name_slug()
        target = f"{name_slug}_Resume.pdf"
        for candidate in [
            RESUMES_PATH / company / target,
            RESUMES_PATH / company.replace(" ", "") / target,
            RESUMES_PATH / company.replace(" ", "").replace("/", "") / target,
        ]:
            if candidate.exists():
                resume_status = "done"
                pdf_path = str(candidate)
                break

    if cl_status == "idle" and not cl_pdf_path:
        company = r.get("company") or ""
        name_slug = _candidate_name_slug()
        cl_target = f"{name_slug}_Cover_Letter.pdf"
        for candidate in [
            RESUMES_PATH / company / cl_target,
            RESUMES_PATH / company.replace(" ", "") / cl_target,
            RESUMES_PATH / company.replace(" ", "").replace("/", "") / cl_target,
        ]:
            if candidate.exists():
                cl_status = "done"
                cl_pdf_path = str(candidate)
                break

    # Posted age
    posted = ""
    try:
        if r.get("posted_at"):
            dt = datetime.fromisoformat(r["posted_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - dt
            days = int(delta.total_seconds() // 86400)
            if days == 0:
                posted = "today"
            elif days == 1:
                posted = "1d ago"
            else:
                posted = f"{days}d ago"
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
        "salary": salary,
        "salary_min": r.get("salary_min") or 0,
        "score": r.get("score") or 0,
        "age": age,
        "posted": posted,
        "status": r.get("status") or "pending",
        "source": _source_label(r.get("search_name") or ""),
        "resume_status": resume_status,
        "resume_stage": ts.get("stage", ""),
        "pdf_url": f"/pdf/{Path(pdf_path).parent.name}" if pdf_path else None,
        "resume_error": ts.get("error"),
        "cl_status": cl_status,
        "cl_stage": cl_ts.get("stage", ""),
        "cl_pdf_url": f"/pdf/{Path(cl_pdf_path).parent.name}/cover" if cl_pdf_path else None,
        "cl_error": cl_ts.get("error"),
    }


@app.route("/")
def index():
    if not PROFILE_PATH.exists():
        return redirect(url_for("setup"))
    counts = stats()
    last = last_fetch_at()
    last_str = ""
    stale = False
    if last:
        dt = datetime.fromisoformat(last)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        last_str = f"{int(hours)}h ago" if hours >= 1 else "just now"
        stale = hours > 24
    return render_template("index.html", counts=counts, last_fetch=last_str, stale=stale)


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
        folder = Path(ts["pdf_path"]).parent.name
        pdf_url = f"/pdf/{folder}"
    return jsonify({
        "status": ts.get("status", "idle"),
        "stage": ts.get("stage", ""),
        "pdf_url": pdf_url,
        "error": ts.get("error"),
    })


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
        folder = Path(ts["pdf_path"]).parent.name
        pdf_url = f"/pdf/{folder}/cover"
    return jsonify({
        "status": ts.get("status", "idle"),
        "stage": ts.get("stage", ""),
        "pdf_url": pdf_url,
        "error": ts.get("error"),
    })


@app.route("/api/job-status/<job_id>/<new_status>", methods=["POST"])
def api_job_status(job_id, new_status):
    if new_status not in ("applied", "skipped", "pending"):
        return jsonify({"error": "Invalid status"}), 400
    ok = update_status(job_id, new_status)
    return jsonify({"ok": ok})


@app.route("/api/config", methods=["GET"])
def api_config_get():
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    return jsonify(data)


@app.route("/api/config", methods=["POST"])
def api_config_save():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    # Basic validation
    if not isinstance(data.get("searches"), list) or not data["searches"]:
        return jsonify({"error": "At least one search entry required"}), 400
    required = {"name", "source", "query"}
    for s in data["searches"]:
        if not required.issubset(s.keys()):
            return jsonify({"error": f"Search entry missing fields: {required - s.keys()}"}), 400
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return jsonify({"ok": True})


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    trigger_fetch()
    return jsonify({"status": "running"})


@app.route("/api/fetch-status")
def api_fetch_status():
    return jsonify(get_fetch_status())


@app.route("/pdf/<company>")
def serve_pdf(company):
    name_slug = _candidate_name_slug()
    pdf = RESUMES_PATH / company / f"{name_slug}_Resume.pdf"
    if not pdf.exists():
        abort(404)
    return send_file(str(pdf), mimetype="application/pdf")


@app.route("/pdf/<company>/cover")
def serve_cover_letter(company):
    name_slug = _candidate_name_slug()
    pdf = RESUMES_PATH / company / f"{name_slug}_Cover_Letter.pdf"
    if not pdf.exists():
        abort(404)
    return send_file(str(pdf), mimetype="application/pdf")


@app.route("/setup")
def setup():
    return render_template("setup.html")


@app.route("/api/setup/status")
def api_setup_status():
    platform = sys.platform  # darwin, win32, linux
    has_claude = bool(shutil.which("claude"))
    has_gemini = bool(shutil.which("gemini"))
    has_pdflatex = bool(shutil.which("pdflatex"))
    has_node = bool(shutil.which("node"))
    has_profile = PROFILE_PATH.exists()
    # Read GEMINI_API_KEY from env
    gemini_key_set = bool(os.environ.get("GEMINI_API_KEY"))
    return jsonify({
        "platform": platform,
        "has_claude": has_claude,
        "has_gemini": has_gemini,
        "has_pdflatex": has_pdflatex,
        "has_node": has_node,
        "has_profile": has_profile,
        "gemini_key_set": gemini_key_set,
    })


@app.route("/api/setup/install-cli", methods=["POST"])
def api_setup_install_cli():
    data = request.get_json()
    provider = data.get("provider")  # "claude" or "gemini"
    if provider not in ("claude", "gemini"):
        return jsonify({"error": "Invalid provider"}), 400
    pkg = "@anthropic-ai/claude-code" if provider == "claude" else "@google/gemini-cli"
    try:
        result = subprocess.run(
            ["npm", "install", "-g", pkg],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            return jsonify({"ok": True, "output": result.stdout[-1000:]})
        return jsonify({"ok": False, "output": result.stderr[-1000:]})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "output": "Install timed out after 3 minutes."})
    except Exception as e:
        return jsonify({"ok": False, "output": str(e)})


@app.route("/api/setup/save-gemini-key", methods=["POST"])
def api_setup_save_gemini_key():
    data = request.get_json()
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "No key provided"}), 400
    # Persist to a .env file the app loads on startup
    env_path = BASE / ".env"
    lines = []
    if env_path.exists():
        lines = [l for l in env_path.read_text().splitlines() if not l.startswith("GEMINI_API_KEY=")]
    lines.append(f"GEMINI_API_KEY={key}")
    env_path.write_text("\n".join(lines) + "\n")
    os.environ["GEMINI_API_KEY"] = key
    return jsonify({"ok": True})


@app.route("/api/setup/install-pdflatex", methods=["POST"])
def api_setup_install_pdflatex():
    platform = sys.platform
    try:
        if platform == "darwin":
            result = subprocess.run(
                ["brew", "install", "--cask", "basictex"],
                capture_output=True, text=True, timeout=600
            )
        elif platform == "linux":
            result = subprocess.run(
                ["sudo", "apt-get", "install", "-y", "texlive-latex-extra"],
                capture_output=True, text=True, timeout=600
            )
        else:
            return jsonify({"ok": False, "output": "Auto-install not supported on Windows. Please install MiKTeX manually from https://miktex.org/download"})
        if result.returncode == 0:
            return jsonify({"ok": True, "output": result.stdout[-1000:]})
        return jsonify({"ok": False, "output": (result.stderr or result.stdout)[-1000:]})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "output": "Install timed out."})
    except Exception as e:
        return jsonify({"ok": False, "output": str(e)})


@app.route("/api/setup/save-profile", methods=["POST"])
def api_setup_save_profile():
    data = request.get_json()
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Profile content is empty"}), 400
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(content)
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Load .env if present (for GEMINI_API_KEY etc.)
    env_path = BASE / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    app.run(debug=False, port=5050)