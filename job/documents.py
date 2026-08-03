from __future__ import annotations
import re
from pathlib import Path

from . import paths
from .db import get_job, update_description, init_db
from .fetcher import fetch_description as fetch_job_description
from .profiles import get_profile_path, get_resumes_path
from .ai_providers import (_get_anthropic_client, _get_gemini_client, _get_groq_client,
                           _get_model, _generate_content, call_ai)
from .latex import _compile_latex, _parse_latex_response
from .latex_render import _parse_content_json, render_resume_latex, ResumeParseError
from . import task_state


def _skill_path() -> Path:
    return paths.BASE / "resume-skill"


# Output contract for the resume library path. Kept out of SKILL.md so the CLI
# agentic path (which produces LaTeX directly) is unaffected — SKILL.md holds
# only writing/ATS rules; each caller appends its own output format.
_JSON_OUTPUT_FORMAT = r"""

## Output Format (CRITICAL)

Return ONLY a JSON object with this exact structure — no explanation, no markdown fences, nothing but the JSON:

{
  "company": "Company name inferred from the job description",
  "summary": "3-5 sentence professional summary as a single plain-text string",
  "core_competencies": ["Competency 1", "Competency 2"],
  "experiences": [
    {
      "title": "Job Title",
      "employer": "Employer name",
      "location": "City, Country",
      "dates": "Mon YYYY - Mon YYYY",
      "bullets": ["Achievement 1", "Achievement 2"],
      "projects": [{"name": "Project", "description": "Scope and outcome in 1-2 sentences"}]
    }
  ],
  "education": [{"degree": "Full Degree Name", "institution": "School", "year": "2020"}],
  "certifications": [{"name": "Certification", "issuer": "Issuer"}],
  "margin": "0.75in",
  "itemsep": "1pt"
}

Rules:
- All values are PLAIN TEXT. No LaTeX, no markdown. Write special characters (& % # $ _) literally — the application escapes them.
- Use straight quotes, not curly quotes.
- "dates": use "Mon YYYY - Mon YYYY" or "Mon YYYY - Present".
- "projects" and "certifications" are optional (omit or use []). "company", "summary", "core_competencies", "experiences", "education" are required.
- "margin": "1in" for light content, "0.75in" normally, "0.5in" only if needed to fit one page. "itemsep": "2pt" normally, "1pt" for dense content.
- Contact details and the candidate's name are added by the application from the profile — do NOT include them.
- Output ONLY the JSON object.
"""


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
    """Build system skill_text and user_prompt for a resume. Returns (skill_text, user_prompt).

    The model returns structured JSON content (see _JSON_OUTPUT_FORMAT); Python
    renders the .tex. The LaTeX template is NOT embedded — layout is code's job.
    """
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    skill_text = _append_profile(skill_text)
    skill_text = _inject_name(skill_text, name_slug)
    skill_text += _JSON_OUTPUT_FORMAT

    desc = row.get("description") or ""
    job_context = desc if len(desc) > 50 else (
        f"No full job description available. "
        f"Tailor the resume for a {title} role at {company} "
        f"based on typical responsibilities for this position."
    )
    # Deterministic ATS hint: skills from our vocabulary that this JD mentions.
    # Zero extra tokens vs an LLM pass; steers Tier-1 keyword coverage.
    from .skills_vocab import detect_keywords
    detected = detect_keywords(desc)
    kw_hint = (
        f"\n\nKey skills detected in this job description (prioritize covering "
        f"these where profile.md supports them): {', '.join(detected)}"
        if detected else ""
    )
    user_prompt = (
        f"Apply to this job for me. Here is the job description:\n\n"
        f"Company: {company}\n"
        f"Title: {title}\n"
        f"Location: {row.get('location') or ''}\n"
        f"URL: {row.get('url') or ''}\n\n"
        f"{job_context}"
        f"{kw_hint}"
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


def _latex_to_prose(text: str) -> str:
    """Best-effort strip of LaTeX markup for a readable live preview of the
    cover letter as it streams. Not exhaustive — just enough to read as prose."""
    s = text
    # Drop the preamble up to and including \begin{document} if present
    m = re.search(r"\\begin\{document\}", s)
    if m:
        s = s[m.end():]
    s = re.split(r"\\end\{document\}", s)[0]
    s = re.sub(r"%.*", "", s)                                  # comments
    s = re.sub(r"\\(documentclass|usepackage|geometry|pagestyle|[a-z]+font)\b[^\n]*", "", s)
    s = re.sub(r"\\(begin|end)\{[^}]*\}", "", s)               # environments
    s = re.sub(r"\\\\", "\n", s)                                # line breaks
    s = re.sub(r"\\(textbf|textit|emph|underline|large|Large|small|section\*?|subsection\*?)\s*\{([^}]*)\}", r"\2", s)
    s = re.sub(r"\\[a-zA-Z]+\*?\s*(\{[^}]*\})?", "", s)         # remaining commands
    s = s.replace("{", "").replace("}", "").replace("~", " ")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _cl_preview_cb(job_id: str):
    """Return an on_delta callback that stores a stripped live preview."""
    def cb(text_so_far: str):
        task_state._set_cl_preview(job_id, _latex_to_prose(text_so_far))
    return cb


def _compile_and_repair(tex_path, latex_content: str, skill_dir, stage_fn, job_id: str):
    """Compile the LaTeX; on failure, ask the model to fix it once and recompile.

    Weak models occasionally emit LaTeX that won't compile (unescaped chars,
    unbalanced braces, undefined commands). Rather than fail the whole build,
    feed the actual pdflatex error back to the model for a single repair pass.
    Only fires on failure — zero overhead on the happy path. If the repair also
    fails to compile, the original error is raised so the user sees a real cause.
    """
    try:
        return _compile_latex(tex_path)
    except RuntimeError as first_err:
        stage_fn(job_id, "Fixing LaTeX and recompiling…")
        repair_system = (
            "You are a LaTeX repair tool. The following LaTeX failed to compile "
            "with pdflatex. Fix ONLY the compilation error — do not rewrite content, "
            "change wording, or alter the layout. Common causes: unescaped & % # _ $, "
            "unbalanced braces, or a command/package not in the preamble. "
            "Return ONLY the corrected LaTeX, starting with \\documentclass and ending "
            "with \\end{document}. No explanation, no markdown fences."
        )
        repair_prompt = (
            f"pdflatex error:\n{first_err}\n\n"
            f"Broken LaTeX:\n{latex_content}"
        )
        try:
            fixed_text = _generate_content(repair_system, repair_prompt, cwd=str(skill_dir))
            fixed_latex, _ = _parse_latex_response(fixed_text)  # sanitizes internally
            if not fixed_latex.strip():
                raise first_err
            tex_path.write_text(fixed_latex, encoding="utf-8")
            return _compile_latex(tex_path)
        except RuntimeError:
            # Repair didn't help — surface the ORIGINAL error, it's more diagnostic.
            raise first_err


def _verify_providers() -> list[tuple[str, str]]:
    """Ordered list of (provider, model) to try for the verification step,
    strongest-and-most-reachable first. A capable verifier is what makes the
    fabrication guard reliable — a weak model can't reliably judge fabrication.

    We prefer the provider the user is actively using for generation (it's
    proven reachable), then other configured strong providers. _verify_summary
    falls through this list on failure, so a configured-but-unfunded provider
    (e.g. Anthropic with no credits) no longer silently disables the guard.
    """
    import os, shutil
    pref = os.environ.get("PREFERRED_PROVIDER", "").strip().lower()
    cands: list[tuple[str, str]] = []

    def add(provider, model):
        if (provider, model) not in cands:
            cands.append((provider, model))

    # Strong model on the user's active provider first (proven reachable).
    if pref == "groq" and _get_groq_client() is not None:
        add("groq", "openai/gpt-oss-120b")
    if pref == "gemini" and (_get_gemini_client() is not None or shutil.which("gemini")):
        add("gemini", _get_model("gemini"))
    if pref == "anthropic" and _get_anthropic_client() is not None:
        add("anthropic", _get_model("anthropic"))

    # Then any other configured strong provider, best-first.
    if _get_anthropic_client() is not None:
        add("anthropic", _get_model("anthropic"))
    if _get_gemini_client() is not None or shutil.which("gemini"):
        add("gemini", _get_model("gemini"))
    if _get_groq_client() is not None:
        add("groq", "openai/gpt-oss-120b")
    return cands


def _verify_summary(summary: str, profile_text: str) -> str | None:
    """Semantic guard against prose fabrication in the summary.

    Weak models, when told to rewrite the summary, sometimes invent a
    background that fits the JD but not the candidate (e.g. a "data engineering"
    summary for a frontend profile). Deterministic checks can't catch this, so
    a *strong* model judges the summary against the profile and, if it invents
    anything, returns a corrected summary grounded only in the profile.

    Tries each verifier in _verify_providers() until one returns a usable
    verdict, so a configured-but-unreachable provider doesn't disable the guard.
    Returns a corrected summary if a fix is needed, else None. Best effort —
    never blocks the build.
    """
    if not summary.strip():
        return None

    system = (
        "You are a strict fact-checker for resume summaries. Compare the SUMMARY "
        "against the PROFILE. FLAG it if the summary mentions ANY domain, industry, "
        "technology, or skill that does not clearly appear in the profile — even if "
        "it sounds plausible. Examples of fabrication: claiming 'distributed systems' "
        "or 'data engineering' for a frontend profile, or naming a language the "
        "profile never lists. Be strict: when in doubt, flag it. "
        "Reply with a JSON object only: "
        '{"ok": true} only if EVERY claim is directly supported by the profile, or '
        '{"ok": false, "summary": "<corrected summary of similar length, grounded '
        "ONLY in the profile's actual experience and skills, no filler like 'proven "
        "track record' or 'passionate'>\"} otherwise."
    )
    prompt = f"PROFILE:\n{profile_text}\n\nSUMMARY TO CHECK:\n{summary}"

    import os, json as _json
    for provider, model in _verify_providers():
        saved_pref = os.environ.get("PREFERRED_PROVIDER")
        saved_model = os.environ.get(f"{provider.upper()}_MODEL")
        try:
            os.environ["PREFERRED_PROVIDER"] = provider
            os.environ[f"{provider.upper()}_MODEL"] = model
            raw = call_ai(prompt, system=system)
        except Exception:
            continue  # this verifier failed — fall through to the next
        finally:
            _restore_env("PREFERRED_PROVIDER", saved_pref)
            _restore_env(f"{provider.upper()}_MODEL", saved_model)
        try:
            if raw.strip().startswith("```"):
                raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0]
            verdict = _json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        except Exception:
            continue  # unparseable verdict — try the next verifier
        if verdict.get("ok") is True:
            return None
        if verdict.get("ok") is False and verdict.get("summary", "").strip():
            return verdict["summary"].strip()
        # ambiguous verdict — try the next verifier
    return None


def _restore_env(key: str, value: str | None) -> None:
    import os
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


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
                                          stage_fn=lambda s: stage_fn(job_id, s),
                                          on_delta=_cl_preview_cb(job_id) if not is_resume else None)

        if is_resume:
            # Model returns JSON content; code renders and compiles the .tex.
            # A malformed-JSON response gets one repair retry before failing.
            try:
                content = _parse_content_json(response_text)
            except ResumeParseError as e:
                stage_fn(job_id, "Fixing response format…")
                repair = (
                    f"Your previous response was not valid resume JSON: {e}\n\n"
                    "Output ONLY the JSON object matching the required schema. "
                    "No explanation, no markdown fences."
                )
                response_text = _generate_content(skill_text, repair, cwd=str(skill_dir),
                                                  stage_fn=lambda s: stage_fn(job_id, s))
                content = _parse_content_json(response_text)

            stage_fn(job_id, "Rendering document…")
            profile_text = get_profile_path().read_text(encoding="utf-8")

            # Semantic guard: catch summary prose that invents a background the
            # profile doesn't support (weak models do this when rewriting).
            stage_fn(job_id, "Checking accuracy…")
            fixed_summary = _verify_summary(content.get("summary", ""), profile_text)
            if fixed_summary:
                print(f"[resume-check] {job_id}: summary rewritten (fabrication guard)")
                content["summary"] = fixed_summary

            latex_content = render_resume_latex(content, profile_text)
            company_folder = _sanitize_folder_name(content.get("company", company), folder_fallback)

            # Deterministic quality check (non-fatal): flag likely fabrication +
            # ATS keyword coverage. Logged for visibility; doesn't block the build.
            from .skills_vocab import detect_keywords
            from .latex_render import validate_resume_content
            issues = validate_resume_content(content, profile_text,
                                              detect_keywords(row.get("description") or ""))
            for w in issues:
                print(f"[resume-check] {job_id}: {w}")
        else:
            latex_content, meta = _parse_latex_response(response_text)
            company_folder = _sanitize_folder_name(meta.get("company", company), folder_fallback)

        stage_fn(job_id, "Compiling PDF…")
        output_dir = _resumes_path() / company_folder / ("resumes" if is_resume else "cover-letters")
        output_dir.mkdir(parents=True, exist_ok=True)

        tex_path = output_dir / f"{name_slug}_{tex_suffix}.tex"
        tex_path.write_text(latex_content, encoding="utf-8")
        if is_resume:
            (output_dir / "job_description.txt").write_text(row.get("description", ""), encoding="utf-8")
            # Rendered from a fixed template — always valid, no repair loop needed.
            pdf_path = _compile_latex(tex_path)
        else:
            # Model-authored LaTeX — keep the error-feedback repair loop.
            pdf_path = _compile_and_repair(tex_path, latex_content, skill_dir, stage_fn, job_id)

        with task_state._lock:
            status_dict[job_id] = {"status": "done", "pdf_path": str(pdf_path), "error": None}

    except Exception as e:
        with task_state._lock:
            status_dict[job_id] = {"status": "error", "pdf_path": None, "error": str(e)}


def _build_resume(job_id: str) -> None:
    _build_document(job_id, "resume")


def _build_cover_letter(job_id: str) -> None:
    _build_document(job_id, "cover_letter")
