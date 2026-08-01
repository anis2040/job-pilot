import os
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request, send_file, abort

from job.db import init_db, get_pending_deduped, get_jobs_by_status, update_status, get_job, stats, last_fetch_at
from job.web_api import trigger_resume, get_task_status, trigger_cover_letter, get_cl_task_status, trigger_fetch, get_fetch_status

BASE = Path(__file__).parent
SKILL_PATH = BASE / "resume-skill"
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
        target = "Yassine_Helaoui_Resume.pdf"
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
        cl_target = "Yassine_Helaoui_Cover_Letter.pdf"
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


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    trigger_fetch()
    return jsonify({"status": "running"})


@app.route("/api/fetch-status")
def api_fetch_status():
    return jsonify(get_fetch_status())


@app.route("/pdf/<company>")
def serve_pdf(company):
    pdf = RESUMES_PATH / company / "Yassine_Helaoui_Resume.pdf"
    if not pdf.exists():
        abort(404)
    return send_file(str(pdf), mimetype="application/pdf")


@app.route("/pdf/<company>/cover")
def serve_cover_letter(company):
    pdf = RESUMES_PATH / company / "Yassine_Helaoui_Cover_Letter.pdf"
    if not pdf.exists():
        abort(404)
    return send_file(str(pdf), mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=False, port=5050)
