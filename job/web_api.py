import threading
import subprocess
import sys
import time
import shutil
from pathlib import Path

from .db import get_job, update_description, init_db, already_seen, is_duplicate, insert_job, insert_filter_log, log_fetch
from .linkedin_fetcher import fetch_description as li_fetch_description
from .config import load_config
from .fetcher import fetch_search
from .profiles import get_profile_path, get_resumes_path

_BASE = Path(__file__).parent.parent

# In-memory task state: { job_id: { "status": "idle|building|done|error", "pdf_path": str|None, "error": str|None } }
_task_status: dict[str, dict] = {}
_cl_task_status: dict[str, dict] = {}
_fetch_status: dict = {"status": "idle", "message": ""}
_lock = threading.Lock()


def _skill_path() -> Path:
    return _BASE / "resume-skill"


def _cl_skill_path() -> Path:
    return _BASE / "cover-letter-skill"


def _resumes_path() -> Path:
    path = get_resumes_path()
    if not path:
        raise RuntimeError("No active profile")
    return path


def clear_task_state() -> None:
    with _lock:
        _task_status.clear()
        _cl_task_status.clear()


def get_task_status(job_id: str) -> dict:
    with _lock:
        return dict(_task_status.get(job_id, {"status": "idle", "pdf_path": None, "error": None, "stage": ""}))


def get_cl_task_status(job_id: str) -> dict:
    with _lock:
        return dict(_cl_task_status.get(job_id, {"status": "idle", "pdf_path": None, "error": None, "stage": ""}))


def get_fetch_status() -> dict:
    with _lock:
        return dict(_fetch_status)


def trigger_resume(job_id: str) -> None:
    with _lock:
        if _task_status.get(job_id, {}).get("status") == "building":
            return
        _task_status[job_id] = {"status": "building", "pdf_path": None, "error": None, "stage": "Starting…"}
    t = threading.Thread(target=_build_resume, args=(job_id,), daemon=True)
    t.start()


def trigger_cover_letter(job_id: str) -> None:
    with _lock:
        if _cl_task_status.get(job_id, {}).get("status") == "building":
            return
        _cl_task_status[job_id] = {"status": "building", "pdf_path": None, "error": None, "stage": "Starting…"}
    t = threading.Thread(target=_build_cover_letter, args=(job_id,), daemon=True)
    t.start()


def trigger_fetch() -> None:
    with _lock:
        if _fetch_status.get("status") == "running":
            return
        _fetch_status["status"] = "running"
        _fetch_status["message"] = "Starting…"
    t = threading.Thread(target=_run_fetch, daemon=True)
    t.start()


def _set_stage(job_id: str, stage: str) -> None:
    with _lock:
        if job_id in _task_status:
            _task_status[job_id]["stage"] = stage


def _set_cl_stage(job_id: str, stage: str) -> None:
    with _lock:
        if job_id in _cl_task_status:
            _cl_task_status[job_id]["stage"] = stage


def _validate_profile() -> None:
    """Raise a clear error if profile.md is missing or still the example template."""
    profile = get_profile_path()
    if not profile or not profile.exists():
        raise ValueError(
            "profile.md not found. Complete the setup wizard at http://localhost:5050/setup"
        )
    text = profile.read_text().strip()
    if not text:
        raise ValueError(
            "profile.md is empty. Complete the setup wizard at http://localhost:5050/setup"
        )
    if "you@example.com" in text or "City, State" in text:
        raise ValueError(
            "profile.md still contains the example template. "
            "Fill in your real profile at http://localhost:5050/setup"
        )


def _candidate_name_slug() -> str:
    """Read the candidate's name from profile.md and return a filename-safe slug like 'John_Smith'."""
    try:
        profile = get_profile_path()
        if not profile:
            return "Candidate"
        text = profile.read_text()
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                name = line.lstrip("#").split("—")[0].split("-")[0].strip()
                if name:
                    return name.replace(" ", "_")
    except Exception:
        pass
    return "Candidate"


def _inject_name(instructions: str, slug: str) -> str:
    return instructions.replace("{{NAME_SLUG}}", slug).replace("{{CANDIDATE_NAME}}", slug.replace("_", " "))


def _run_ai(prompt: str, system_instructions: str, cwd: str) -> subprocess.Popen:
    """Launch the configured AI CLI (claude or gemini) as a subprocess."""
    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = subprocess.CREATE_NO_WINDOW

    if shutil.which("claude"):
        return subprocess.Popen(
            ["claude", "-p", prompt,
             "--append-system-prompt", system_instructions,
             "--allowedTools", "Bash,Edit,Write,Read"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            **extra,
        )
    if shutil.which("gemini"):
        gemini_md = Path(cwd) / "GEMINI.md"
        gemini_md.write_text(system_instructions)
        return subprocess.Popen(
            ["gemini", "-p", prompt, "--yolo"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            **extra,
        )
    raise RuntimeError(
        "No AI CLI found. Install Claude Code (https://claude.ai/code) or "
        "Gemini CLI (npm install -g @google/gemini-cli)."
    )


def _build_resume(job_id: str) -> None:
    try:
        _validate_profile()
        init_db()
        row = get_job(job_id)
        if not row:
            raise ValueError(f"Job {job_id} not found")

        row = dict(row)

        # Stage 1 — fetch description for LinkedIn jobs
        if job_id.startswith("li_") and (not row.get("description") or len(row["description"]) < 100):
            _set_stage(job_id, "Fetching job description…")
            desc = li_fetch_description(row["url"])
            if desc:
                update_description(job_id, desc)
                row["description"] = desc

        if not row.get("description"):
            raise ValueError("No job description available — cannot build resume")

        company = row.get("company") or "Unknown"
        title = row.get("title") or "Job"

        _set_stage(job_id, "Analyzing job description…")

        prompt = (
            f"Apply to this job for me. Here is the job description:\n\n"
            f"Company: {company}\n"
            f"Title: {title}\n"
            f"Location: {row.get('location') or ''}\n"
            f"URL: {row.get('url') or ''}\n\n"
            f"{row['description']}"
        )

        skill_instructions = (_skill_path() / "SKILL.md").read_text()
        latex_template = _skill_path() / "references" / "latex_template.md"
        if latex_template.exists():
            skill_instructions += f"\n\n## latex_template.md (embedded)\n\n{latex_template.read_text()}"
        profile_path = get_profile_path()
        if profile_path and profile_path.exists():
            skill_instructions += f"\n\n## profile.md (embedded)\n\n{profile_path.read_text()}"

        name_slug = _candidate_name_slug()
        skill_instructions = _inject_name(skill_instructions, name_slug)

        proc = _run_ai(prompt, skill_instructions, cwd=str(_skill_path()))

        # Stream stdout and detect stages from Claude's output
        for line in proc.stdout:
            line_lower = line.lower()
            if any(k in line_lower for k in ("step 1", "analyz", "job description", "keyword")):
                _set_stage(job_id, "Analyzing job description…")
            elif any(k in line_lower for k in ("step 2", "step 3", "writing", "bullet", "summary", "competenc")):
                _set_stage(job_id, "Writing resume content…")
            elif any(k in line_lower for k in ("step 4", "latex", ".tex", "generate", "\\documentclass")):
                _set_stage(job_id, "Generating LaTeX…")
            elif any(k in line_lower for k in ("pdflatex", "compil", "step 5")):
                _set_stage(job_id, "Compiling PDF…")
            elif any(k in line_lower for k in ("step 6", "deliver", "cover note", "output path")):
                _set_stage(job_id, "Finalizing…")

        try:
            proc.wait(timeout=600)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("Resume build timed out after 10 minutes")

        if proc.returncode != 0:
            err = proc.stderr.read() if proc.stderr else "claude subprocess failed"
            raise RuntimeError(err)

        _set_stage(job_id, "Locating PDF…")

        name_slug = _candidate_name_slug()
        pdf_path = None
        target = f"{name_slug}_Resume.pdf"
        for candidate in [
            _resumes_path() / company / target,
            _resumes_path() / company.replace(" ", "") / target,
            _resumes_path() / company.replace(" ", "").replace("/", "") / target,
        ]:
            if candidate.exists():
                pdf_path = str(candidate)
                break
        if not pdf_path:
            for p in sorted(_resumes_path().rglob(target), key=lambda f: f.stat().st_mtime, reverse=True):
                pdf_path = str(p)
                break

        with _lock:
            _task_status[job_id] = {
                "status": "done",
                "pdf_path": pdf_path,
                "error": None,
            }

    except Exception as e:
        with _lock:
            _task_status[job_id] = {
                "status": "error",
                "pdf_path": None,
                "error": str(e),
            }


def _build_cover_letter(job_id: str) -> None:
    try:
        _validate_profile()
        init_db()
        row = get_job(job_id)
        if not row:
            raise ValueError(f"Job {job_id} not found")

        row = dict(row)

        if not row.get("description"):
            raise ValueError("No job description available — cannot build cover letter")

        company = row.get("company") or "Unknown"
        title = row.get("title") or "Job"

        # Find the resume tex for this job so the skill can read it
        name_slug = _candidate_name_slug()
        resume_tex = None
        for candidate in [
            _resumes_path() / company / f"{name_slug}_Resume.tex",
            _resumes_path() / company.replace(" ", "") / f"{name_slug}_Resume.tex",
            _resumes_path() / company.replace(" ", "").replace("/", "") / f"{name_slug}_Resume.tex",
        ]:
            if candidate.exists():
                resume_tex = str(candidate)
                break

        _set_cl_stage(job_id, "Reading resume…")

        prompt = (
            f"Write a cover letter for this job application.\n\n"
            f"Company: {company}\n"
            f"Title: {title}\n"
            f"Location: {row.get('location') or ''}\n"
            f"URL: {row.get('url') or ''}\n\n"
            f"Job description:\n{row['description']}"
            + (f"\n\nThe resume for this role is at: {resume_tex}" if resume_tex else "")
        )

        skill_instructions = (_cl_skill_path() / "SKILL.md").read_text()
        profile_path = get_profile_path()
        if profile_path and profile_path.exists():
            skill_instructions += f"\n\n## profile.md (embedded)\n\n{profile_path.read_text()}"
        skill_instructions = _inject_name(skill_instructions, name_slug)

        proc = _run_ai(prompt, skill_instructions, cwd=str(_cl_skill_path()))

        for line in proc.stdout:
            line_lower = line.lower()
            if any(k in line_lower for k in ("analyz", "job description", "reading")):
                _set_cl_stage(job_id, "Analyzing job…")
            elif any(k in line_lower for k in ("paragraph", "writing", "draft")):
                _set_cl_stage(job_id, "Writing letter…")
            elif any(k in line_lower for k in ("latex", ".tex", "generate")):
                _set_cl_stage(job_id, "Generating LaTeX…")
            elif any(k in line_lower for k in ("pdflatex", "compil")):
                _set_cl_stage(job_id, "Compiling PDF…")
            elif any(k in line_lower for k in ("deliver", "output")):
                _set_cl_stage(job_id, "Finalizing…")

        try:
            proc.wait(timeout=600)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("Cover letter build timed out after 10 minutes")

        if proc.returncode != 0:
            err = proc.stderr.read() if proc.stderr else "claude subprocess failed"
            raise RuntimeError(err)

        _set_cl_stage(job_id, "Locating PDF…")

        target = f"{name_slug}_Cover_Letter.pdf"
        pdf_path = None
        for candidate in [
            _resumes_path() / company / target,
            _resumes_path() / company.replace(" ", "") / target,
            _resumes_path() / company.replace(" ", "").replace("/", "") / target,
        ]:
            if candidate.exists():
                pdf_path = str(candidate)
                break
        if not pdf_path:
            for p in sorted(_resumes_path().rglob(target), key=lambda f: f.stat().st_mtime, reverse=True):
                pdf_path = str(p)
                break

        with _lock:
            _cl_task_status[job_id] = {
                "status": "done",
                "pdf_path": pdf_path,
                "error": None,
            }

    except Exception as e:
        with _lock:
            _cl_task_status[job_id] = {
                "status": "error",
                "pdf_path": None,
                "error": str(e),
            }


def _run_fetch() -> None:
    try:
        init_db()
        config = load_config()
        total_new = 0

        for search in config.searches:
            with _lock:
                _fetch_status["message"] = f"Fetching {search.name}…"

            jobs = fetch_search(search)
            new_count = 0

            for job in jobs:
                if already_seen(job.job_id):
                    continue
                if job.company and job.company.lower() in config.company_blacklist:
                    continue
                if config.title_filter:
                    if not any(kw in job.title.lower() for kw in config.title_filter):
                        continue
                from .cli import _blacklisted
                kw = _blacklisted(job.title + " " + job.description, config.blacklist)
                if kw:
                    insert_filter_log(job.job_id, job.title, kw)
                    continue
                if is_duplicate(job.title, job.company):
                    continue
                insert_job(
                    job_id=job.job_id, url=job.url, title=job.title,
                    company=job.company, location=job.location, remote=job.remote,
                    experience=job.experience, description=job.description,
                    posted_at=job.posted_at, search_name=search.name,
                )
                new_count += 1

            log_fetch(search.source, new_count)
            total_new += new_count

        with _lock:
            _fetch_status["status"] = "done"
            _fetch_status["message"] = f"Done — {total_new} new job(s) found"

    except Exception as e:
        with _lock:
            _fetch_status["status"] = "error"
            _fetch_status["message"] = str(e)
