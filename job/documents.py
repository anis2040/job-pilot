from __future__ import annotations
import re
from pathlib import Path

from . import paths
from .db import get_job, update_description, init_db
from .fetcher import fetch_description as fetch_job_description
from .profiles import get_profile_path, get_resumes_path
from .ai_providers import _get_anthropic_client, _get_model, _generate_content
from .latex import _compile_latex, _parse_latex_response
from . import task_state


def _skill_path() -> Path:
    return paths.BASE / "resume-skill"


def _cl_skill_path() -> Path:
    return paths.BASE / "cover-letter-skill"


def _resumes_path() -> Path:
    path = get_resumes_path()
    if not path:
        raise RuntimeError("No active profile")
    return path


def _validate_profile() -> None:
    profile = get_profile_path()
    if not profile or not profile.exists():
        raise ValueError("profile.md not found. Complete the setup wizard at http://localhost:5050/setup")
    text = profile.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("profile.md is empty. Complete the setup wizard at http://localhost:5050/setup")
    if "you@example.com" in text or "City, State" in text:
        raise ValueError(
            "profile.md still contains the example template. "
            "Fill in your real profile at http://localhost:5050/setup"
        )


def _candidate_name_slug() -> str:
    try:
        profile = get_profile_path()
        if not profile:
            return "Candidate"
        from .profiles import name_from_markdown
        name = name_from_markdown(profile.read_text(encoding="utf-8"))
        if name:
            return name.replace(" ", "_")
    except Exception:
        pass
    return "Candidate"


def _inject_name(instructions: str, slug: str) -> str:
    return instructions.replace("{{NAME_SLUG}}", slug).replace("{{CANDIDATE_NAME}}", slug.replace("_", " "))


def _append_profile(skill_text: str) -> str:
    """Append the active profile.md to skill_text if it exists. Returns updated text."""
    profile_path = get_profile_path()
    if profile_path and profile_path.exists():
        skill_text += f"\n\n## profile.md (embedded)\n\n{profile_path.read_text(encoding='utf-8')}"
    return skill_text


def _sanitize_folder_name(name: str, fallback: str = "Output") -> str:
    return re.sub(r'[^\w\-_]', '', name.replace(" ", ""))[:64] or fallback


def _prewarm_cache() -> None:
    """Write the stable skill prompt to Anthropic's cache on startup.
    Costs one cache-write; every subsequent build within 1h is a cache hit."""
    client = _get_anthropic_client()
    if client is None:
        return
    try:
        from .profiles import get_profile_path
        profile = get_profile_path()
        if not profile or not profile.exists():
            return  # no profile yet — nothing to cache

        skill_text = (_skill_path() / "SKILL.md").read_text(encoding="utf-8")
        latex = _skill_path() / "references" / "latex_template.md"
        if latex.exists():
            skill_text += f"\n\n## latex_template.md (embedded)\n\n{latex.read_text(encoding='utf-8')}"
        skill_text = _append_profile(skill_text)
        slug = _candidate_name_slug()
        skill_text = _inject_name(skill_text, slug)

        client.messages.create(
            model=_get_model("anthropic"),
            max_tokens=0,
            system=[{"type": "text", "text": skill_text,
                     "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            messages=[{"role": "user", "content": "warmup"}],
        )
        print("[cache] pre-warmed on startup (1h TTL)")
    except Exception:
        pass  # pre-warm is best-effort, never block startup


def _build_resume_prompt(row: dict, company: str, title: str, name_slug: str, skill_dir) -> tuple[str, str]:
    """Build system skill_text and user_prompt for a resume. Returns (skill_text, user_prompt)."""
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    latex_template = skill_dir / "references" / "latex_template.md"
    if latex_template.exists():
        skill_text += f"\n\n## latex_template.md (embedded)\n\n{latex_template.read_text(encoding='utf-8')}"
    skill_text = _append_profile(skill_text)
    skill_text = _inject_name(skill_text, name_slug)

    desc = row.get("description") or ""
    job_context = desc if len(desc) > 50 else (
        f"No full job description available. "
        f"Tailor the resume for a {title} role at {company} "
        f"based on typical responsibilities for this position."
    )
    user_prompt = (
        f"Apply to this job for me. Here is the job description:\n\n"
        f"Company: {company}\n"
        f"Title: {title}\n"
        f"Location: {row.get('location') or ''}\n"
        f"URL: {row.get('url') or ''}\n\n"
        f"{job_context}"
    )
    return skill_text, user_prompt


def _build_cover_letter_prompt(row: dict, company: str, title: str, name_slug: str, skill_dir) -> tuple[str, str]:
    """Build system skill_text and user_prompt for a cover letter. Returns (skill_text, user_prompt)."""
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    skill_text = _append_profile(skill_text)
    skill_text = _inject_name(skill_text, name_slug)
    skill_text += "\n\n## Output format\nReturn ONLY the raw LaTeX content (starting with \\documentclass), no explanations. After \\end{document} include a JSON block: ```json {\"company\": \"<name>\"} ```"

    resume_tex_content = ""
    for candidate in [
        _resumes_path() / company / "resumes" / f"{name_slug}_Resume.tex",
        _resumes_path() / company.replace(" ", "") / "resumes" / f"{name_slug}_Resume.tex",
        _resumes_path() / company.replace(" ", "").replace("/", "") / "resumes" / f"{name_slug}_Resume.tex",
    ]:
        if candidate.exists():
            resume_tex_content = f"\n\nThe resume for this role (for consistency):\n```latex\n{candidate.read_text(encoding='utf-8')[:3000]}\n```"
            break

    user_prompt = (
        f"Write a cover letter for this job.\n\n"
        f"Company: {company}\n"
        f"Title: {title}\n"
        f"Location: {row.get('location') or ''}\n\n"
        f"Job description:\n{row['description']}"
        f"{resume_tex_content}"
    )
    return skill_text, user_prompt


def _build_document(job_id: str, doc_type: str) -> None:
    """Shared document builder for resumes and cover letters."""
    is_resume = doc_type == "resume"
    status_dict = task_state._task_status if is_resume else task_state._cl_task_status
    stage_fn = task_state._set_stage if is_resume else task_state._set_cl_stage
    skill_dir = _skill_path() if is_resume else _cl_skill_path()
    tex_suffix = "Resume" if is_resume else "Cover_Letter"
    folder_fallback = "Resume" if is_resume else "CoverLetter"

    try:
        _validate_profile()
        init_db()
        row = get_job(job_id)
        if not row:
            raise ValueError(f"Job {job_id} not found")
        row = dict(row)

        if is_resume:
            if (not row.get("description") or len(row["description"]) < 100):
                stage_fn(job_id, "Fetching job description…")
                desc = fetch_job_description(job_id, row.get("url") or "")
                if desc:
                    update_description(job_id, desc)
                    row["description"] = desc
        else:
            if not row.get("description"):
                stage_fn(job_id, "Fetching job description…")
                desc = fetch_job_description(job_id, row.get("url") or "")
                if desc:
                    update_description(job_id, desc)
                    row["description"] = desc
            if not row.get("description"):
                raise ValueError("No job description available — cannot build cover letter")

        company = row.get("company") or "Unknown"
        title = row.get("title") or "Job"
        name_slug = _candidate_name_slug()

        if is_resume:
            stage_fn(job_id, "Generating resume…")
            skill_text, user_prompt = _build_resume_prompt(row, company, title, name_slug, skill_dir)
        else:
            stage_fn(job_id, "Generating cover letter…")
            skill_text, user_prompt = _build_cover_letter_prompt(row, company, title, name_slug, skill_dir)

        response_text = _generate_content(skill_text, user_prompt, cwd=str(skill_dir),
                                          stage_fn=lambda s: stage_fn(job_id, s))

        stage_fn(job_id, "Compiling PDF…")
        latex_content, meta = _parse_latex_response(response_text)

        company_folder = _sanitize_folder_name(meta.get("company", company), folder_fallback)

        output_dir = _resumes_path() / company_folder / ("resumes" if is_resume else "cover-letters")
        output_dir.mkdir(parents=True, exist_ok=True)

        tex_path = output_dir / f"{name_slug}_{tex_suffix}.tex"
        tex_path.write_text(latex_content, encoding="utf-8")
        if is_resume:
            (output_dir / "job_description.txt").write_text(row.get("description", ""), encoding="utf-8")

        pdf_path = _compile_latex(tex_path)

        with task_state._lock:
            status_dict[job_id] = {"status": "done", "pdf_path": str(pdf_path), "error": None}

    except Exception as e:
        with task_state._lock:
            status_dict[job_id] = {"status": "error", "pdf_path": None, "error": str(e)}


def _build_resume(job_id: str) -> None:
    _build_document(job_id, "resume")


def _build_cover_letter(job_id: str) -> None:
    _build_document(job_id, "cover_letter")
