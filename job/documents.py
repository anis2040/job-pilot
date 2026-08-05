from __future__ import annotations
import re
from pathlib import Path

from . import paths
from .db import get_job, update_description, init_db
from .fetcher import fetch_description as fetch_job_description, should_fetch_description
from .profiles import get_profile_path, get_resumes_path
from .ai_providers import (_get_anthropic_client, _get_gemini_client, _get_groq_client,
                           _get_model, _generate_content, call_ai, extract_json_from_llm)
from .latex import _compile_latex, _parse_latex_response
from .latex_render import (_parse_content_json, render_resume_latex, ResumeParseError,
                           _parse_cover_letter_json, render_cover_letter_latex)
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


# Output contract for the cover-letter library path (JSON, rendered in code).
_CL_JSON_OUTPUT_FORMAT = r"""

## Output Format (CRITICAL)

Return ONLY a JSON object with this exact structure — no explanation, no markdown fences, nothing but the JSON:

{
  "company": "Company name from the job description",
  "paragraphs": ["Paragraph 1 text", "Paragraph 2 text", "Paragraph 3 text"],
  "greeting": "Dear Hiring Manager,",
  "closing": "Best regards,"
}

Rules:
- "paragraphs": the 3 body paragraphs as plain-text strings (no LaTeX, no markdown). Follow the three-paragraph structure above.
- Write special characters (& % # $) literally — the application escapes them.
- "greeting"/"closing" are optional (sensible defaults are used if omitted).
- The candidate's name and contact details are added by the application from the profile — do NOT include a signature.
- Output ONLY the JSON object.
"""


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
    # Zero extra tokens vs an LLM pass; steers Tier-1 keyword coverage. Uses the
    # centralized match_text (title + description) so title keywords count too.
    from .skills_vocab import detect_keywords
    from .match import match_text
    detected = detect_keywords(match_text({"title": title, "description": desc}))
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
    skill_text += _CL_JSON_OUTPUT_FORMAT

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


def _run_verifier(system: str, prompt: str) -> dict | None:
    """Run a verification prompt through the strongest reachable model.

    Tries each provider in _verify_providers() until one returns a parseable
    JSON verdict, falling through on failure/unparseable output. Returns the
    parsed dict, or None if no verifier succeeded. Shared by the summary and
    bullet fabrication guards.
    """
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
            return extract_json_from_llm(raw)
        except Exception:
            continue  # unparseable verdict — try the next verifier
    return None


def _verify_content(content: dict, profile_text: str) -> list[str]:
    """LLM fabrication guard for the prose fields — summary + bullets.

    Competencies are grounded deterministically against profile.json elsewhere
    (cheaper + more precise), so this call covers only the prose the model can
    fabricate in ways regex can't judge. One call for both fields. Mutates
    `content`; returns changed field names. Best effort — never blocks.

    Per-field safety: bullets are remapped by position and only applied on a
    same-length response.
    """
    import json as _json

    summary = (content.get("summary") or "").strip()

    flat: list[str] = []
    index: list[tuple[int, int]] = []   # (experience_idx, bullet_idx)
    for ei, exp in enumerate(content.get("experiences", [])):
        for bi, b in enumerate(exp.get("bullets", []) or []):
            if b and b.strip():
                flat.append(b)
                index.append((ei, bi))

    if not summary and not flat:
        return []

    system = (
        "You are a strict fact-checker for a resume. Compare each part against the "
        "PROFILE and correct anything the profile does not support — invented "
        "domains/technologies/skills, inflated scope, or metrics not in the profile. "
        "Be strict: when in doubt, treat it as unsupported. Do not invent "
        "replacements; ground everything in the profile's actual experience. "
        "No filler ('proven track record', 'passionate'). "
        "You are given SUMMARY (string) and BULLETS (string array). Reply with a "
        "JSON object ONLY, echoing each field with corrections applied and "
        "preserving the BULLETS array's exact length and order:\n"
        '{"summary": "<grounded summary>", '
        '"bullets": [<same length/order, unsupported ones rewritten>]}'
    )
    prompt = (
        f"PROFILE:\n{profile_text}\n\n"
        f"SUMMARY:\n{summary}\n\n"
        f"BULLETS (keep this exact length and order):\n{_json.dumps(flat, ensure_ascii=False)}"
    )

    verdict = _run_verifier(system, prompt)
    if not verdict:
        return []

    changed: list[str] = []

    new_summary = verdict.get("summary")
    if isinstance(new_summary, str) and new_summary.strip() and new_summary.strip() != summary:
        content["summary"] = new_summary.strip()
        changed.append("summary")

    new_bullets = verdict.get("bullets")
    if isinstance(new_bullets, list) and len(new_bullets) == len(flat):
        bullet_changed = False
        for pos, (ei, bi) in enumerate(index):
            nb = new_bullets[pos]
            if isinstance(nb, str) and nb.strip() and nb.strip() != flat[pos]:
                content["experiences"][ei]["bullets"][bi] = nb.strip()
                bullet_changed = True
        if bullet_changed:
            changed.append("bullets")

    return changed


def _restore_env(key: str, value: str | None) -> None:
    import os
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def _verify_cover_letter(content: dict, profile_text: str) -> bool:
    """Fabrication guard for cover-letter paragraphs (mirrors _verify_content).

    Cover letters are free prose — the most fabrication-prone surface. A strong
    model rewrites any paragraph that claims a client/company/project/metric/tool
    not supported by the profile. Mutates content["paragraphs"] in place; returns
    True if changed. Best effort — never blocks the build.
    """
    paras = [p for p in content.get("paragraphs", []) if isinstance(p, str) and p.strip()]
    if not paras:
        return False
    import json as _json
    system = (
        "You are a strict fact-checker for a cover letter. Each paragraph may only "
        "reference employers, clients, projects, skills, and metrics found in the "
        "PROFILE. Rewrite any paragraph that claims something the profile doesn't "
        "support (invented clients/projects, inflated scope, metrics not in the "
        "profile), keeping it natural and the same length. Leave grounded "
        "paragraphs unchanged. No filler ('proven track record', 'passionate'). "
        "Reply with a JSON object only: "
        '{"ok": true} if every paragraph is grounded, or '
        '{"ok": false, "paragraphs": [<same length and order, unsupported ones rewritten>]} otherwise.'
    )
    prompt = (
        f"PROFILE:\n{profile_text}\n\n"
        f"PARAGRAPHS (keep this exact length and order):\n{_json.dumps(paras, ensure_ascii=False)}"
    )
    verdict = _run_verifier(system, prompt)
    if not verdict or verdict.get("ok") is not False:
        return False
    fixed = verdict.get("paragraphs")
    if not isinstance(fixed, list) or len(fixed) != len(paras):
        return False  # length mismatch — don't risk scrambling paragraph order
    changed = False
    out = list(content["paragraphs"])
    # Map corrected non-empty paragraphs back onto their original positions.
    pos = 0
    for i, p in enumerate(content["paragraphs"]):
        if isinstance(p, str) and p.strip():
            nb = fixed[pos]
            if isinstance(nb, str) and nb.strip() and nb.strip() != p.strip():
                out[i] = nb.strip()
                changed = True
            pos += 1
    if changed:
        content["paragraphs"] = out
    return changed


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

        if should_fetch_description(job_id, row.get("description")):
            stage_fn(job_id, "Fetching job description…")
            desc = fetch_job_description(job_id, row.get("url") or "")
            if desc and len(desc) > len(row.get("description") or ""):
                update_description(job_id, desc)
                row["description"] = desc
        if not is_resume:
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
            content["company"] = company

            stage_fn(job_id, "Rendering document…")
            profile_text = get_profile_path().read_text(encoding="utf-8")

            # Deterministic competency grounding (free, precise): drop any
            # competency not supported by the structured profile. Runs before
            # the LLM guard, which now only covers the prose fields.
            from .profiles import get_profile_json
            from .latex_render import ground_competencies
            pj = get_profile_json()
            if pj:
                orig = content.get("core_competencies", [])
                kept, dropped = ground_competencies(orig, pj)
                if kept != orig:
                    content["core_competencies"] = kept
                if dropped:
                    print(f"[resume-check] {job_id}: dropped unsupported competencies: {', '.join(dropped)}")

            # Semantic guard: one strong-model call grounds the prose fields
            # (summary + bullets) — the fabrication regex can't judge.
            stage_fn(job_id, "Checking accuracy…")
            fixed = _verify_content(content, profile_text)
            if fixed:
                print(f"[resume-check] {job_id}: rewritten by fabrication guard: {', '.join(fixed)}")

            # Deterministic cleanup (free, guaranteed): strip em-dashes the model
            # was told to avoid, order bullets metrics-first. Runs last so it also
            # normalizes anything the fabrication guard rewrote.
            from .latex_render import clean_content
            clean_content(content)

            latex_content = render_resume_latex(content, profile_text)
            company_folder = _sanitize_folder_name(company, folder_fallback)

            # Deterministic quality check (non-fatal): flag likely fabrication +
            # ATS keyword coverage. Logged for visibility; doesn't block the build.
            from .skills_vocab import detect_keywords
            from .latex_render import validate_resume_content
            from .match import match_text
            issues = validate_resume_content(content, profile_text,
                                              detect_keywords(match_text(row)))
            for w in issues:
                print(f"[resume-check] {job_id}: {w}")
        else:
            # Cover letter: model returns JSON paragraphs; code renders the .tex.
            try:
                content = _parse_cover_letter_json(response_text)
            except ResumeParseError as e:
                stage_fn(job_id, "Fixing response format…")
                repair = (
                    f"Your previous response was not valid cover-letter JSON: {e}\n\n"
                    "Output ONLY the JSON object matching the required schema. "
                    "No explanation, no markdown fences."
                )
                response_text = _generate_content(skill_text, repair, cwd=str(skill_dir),
                                                  stage_fn=lambda s: stage_fn(job_id, s))
                content = _parse_cover_letter_json(response_text)
            content["company"] = company

            profile_text = get_profile_path().read_text(encoding="utf-8")
            stage_fn(job_id, "Checking accuracy…")
            if _verify_cover_letter(content, profile_text):
                print(f"[cl-check] {job_id}: paragraph(s) rewritten (fabrication guard)")

            stage_fn(job_id, "Rendering document…")
            latex_content = render_cover_letter_latex(content, profile_text)
            company_folder = _sanitize_folder_name(content.get("company", company), folder_fallback)

        stage_fn(job_id, "Compiling PDF…")
        output_dir = _resumes_path() / company_folder / ("resumes" if is_resume else "cover-letters")
        output_dir.mkdir(parents=True, exist_ok=True)

        tex_path = output_dir / f"{name_slug}_{tex_suffix}.tex"
        tex_path.write_text(latex_content, encoding="utf-8")
        if is_resume:
            (output_dir / "job_description.txt").write_text(row.get("description", ""), encoding="utf-8")
        # Both are now rendered from fixed templates — always valid, no repair loop.
        pdf_path = _compile_latex(tex_path)

        with task_state._lock:
            status_dict[job_id] = {"status": "done", "pdf_path": str(pdf_path), "error": None}

    except Exception as e:
        from .ai_providers import RateLimitError
        entry = {"status": "error", "pdf_path": None, "error": str(e)}
        if isinstance(e, RateLimitError):
            entry["rate_limit"] = e.as_dict()
        with task_state._lock:
            status_dict[job_id] = entry


def _build_resume(job_id: str) -> None:
    _build_document(job_id, "resume")


def _build_cover_letter(job_id: str) -> None:
    _build_document(job_id, "cover_letter")
