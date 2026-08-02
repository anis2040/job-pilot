from __future__ import annotations
import threading
import subprocess
import sys
import re
import time
import shutil
import json as _json
from pathlib import Path

from .db import get_job, update_description, init_db, already_seen, is_duplicate, insert_job, insert_filter_log, log_fetch
from .linkedin_fetcher import fetch_description as li_fetch_description
from .config import load_config
from .fetcher import fetch_search
from .profiles import get_profile_path, get_resumes_path

_BASE = Path(__file__).parent.parent

# In-memory task state
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
    profile = get_profile_path()
    if not profile or not profile.exists():
        raise ValueError("profile.md not found. Complete the setup wizard at http://localhost:5050/setup")
    text = profile.read_text().strip()
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


def _load_env() -> None:
    """Load .env file from project root into os.environ."""
    import os
    env_path = _BASE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            # Always set ANTHROPIC_API_KEY from .env — it's the explicit user config
            if k == "ANTHROPIC_API_KEY":
                os.environ[k] = v
            else:
                os.environ.setdefault(k, v)


def _get_anthropic_client():
    """Return an Anthropic client pointed at the public API, or None."""
    _load_env()
    try:
        import anthropic
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")

        if api_key:
            # Force the public API URL — ignore ANTHROPIC_BASE_URL proxy overrides
            client = anthropic.Anthropic(
                api_key=api_key,
                base_url="https://api.anthropic.com",
            )
            return client
        elif auth_token:
            client = anthropic.Anthropic(auth_token=auth_token)
        elif shutil.which("claude"):
            client = anthropic.Anthropic()
        else:
            return None

        # For token/OAuth clients, reject proxy endpoints
        base = str(getattr(getattr(client, "_client", None), "base_url", ""))
        if base and "anthropic.com" not in base:
            return None

        return client
    except Exception:
        return None


def _build_with_sdk(system_text: str, user_prompt: str, stage_fn=None) -> str:
    """Call Claude via SDK with prompt caching. Returns response text."""
    import anthropic
    client = _get_anthropic_client()
    if client is None:
        raise RuntimeError("No Anthropic client available")
    if stage_fn:
        stage_fn("Generating with Claude…")
    # Use Haiku — cheapest model, free tier generous, instruction-following is excellent
    model = "claude-haiku-4-5"
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": system_text,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    )
    u = response.usage
    cache_read   = getattr(u, "cache_read_input_tokens",   0) or 0
    cache_write  = getattr(u, "cache_creation_input_tokens", 0) or 0
    uncached     = getattr(u, "input_tokens", 0) or 0
    output_toks  = getattr(u, "output_tokens", 0) or 0
    total_input  = uncached + cache_read + cache_write
    saved_pct    = round(cache_read / total_input * 100) if total_input else 0
    print(
        f"[cache/{model}] input={total_input} "
        f"(uncached={uncached} write={cache_write} read={cache_read}) "
        f"output={output_toks} "
        f"saved={saved_pct}%"
    )
    return response.content[0].text


def _get_gemini_client():
    """Return a configured Gemini client, or None if no credentials available."""
    import os
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _build_with_gemini(system_text: str, user_prompt: str, cwd: str, stage_fn=None) -> str:
    """Call Gemini. Tries SDK first (if billing works), then CLI subprocess."""
    if stage_fn:
        stage_fn("Generating with Gemini…")

    # Try SDK — works when billing is enabled on the API key
    client = _get_gemini_client()
    if client is not None:
        try:
            from google.genai import types
            model = "gemini-2.0-flash"
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_text,
                    max_output_tokens=4096,
                ),
            )
            u = response.usage_metadata
            if u:
                prompt_toks = getattr(u, "prompt_token_count",         0) or 0
                output_toks = getattr(u, "candidates_token_count",     0) or 0
                cached_toks = getattr(u, "cached_content_token_count", 0) or 0
                total_toks  = getattr(u, "total_token_count",          0) or 0
                print(
                    f"[gemini/{model}] input={prompt_toks} output={output_toks} "
                    f"cached={cached_toks} total={total_toks}"
                )
            return response.text
        except Exception as sdk_err:
            # Quota/billing error — fall through to CLI
            print(f"[gemini] SDK failed ({sdk_err.__class__.__name__}), falling back to CLI")

    # CLI fallback — uses personal Google OAuth, no billing required
    if not shutil.which("gemini"):
        raise RuntimeError(
            "No Gemini available. Set GEMINI_API_KEY with billing enabled, "
            "or install the Gemini CLI: npm install -g @google/gemini-cli"
        )
    gemini_md = Path(cwd) / "GEMINI.md"
    gemini_md.write_text(system_text)
    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = subprocess.CREATE_NO_WINDOW
    result = subprocess.run(
        ["gemini", "-p", user_prompt, "--yolo", "--skip-trust", "--output-format", "json"],
        capture_output=True, text=True, cwd=cwd, timeout=600, **extra,
    )
    if gemini_md.exists():
        gemini_md.unlink()
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "gemini subprocess failed")

    # Parse JSON output for token stats and response text
    try:
        data = _json.loads(result.stdout)
        response_text = data.get("response", "")
        stats = data.get("stats", {}).get("models", {})
        for model_name, model_data in stats.items():
            toks = model_data.get("tokens", {})
            input_t  = toks.get("input", 0) or 0
            output_t = toks.get("candidates", 0) or 0
            cached_t = toks.get("cached", 0) or 0
            total_t  = toks.get("total", 0) or 0
            print(
                f"[gemini/cli/{model_name}] input={input_t} output={output_t} "
                f"cached={cached_t} total={total_t}"
            )
    except Exception:
        # Fallback: treat stdout as plain text
        response_text = result.stdout

    return response_text


def _generate_content(system_text: str, user_prompt: str, cwd: str, stage_fn=None) -> str:
    """Use best available AI: Anthropic SDK (cached) → Gemini SDK → Gemini CLI."""
    client = _get_anthropic_client()
    if client is not None:
        return _build_with_sdk(system_text, user_prompt, stage_fn=stage_fn)
    if _get_gemini_client() is not None or shutil.which("gemini"):
        return _build_with_gemini(system_text, user_prompt, cwd=cwd, stage_fn=stage_fn)
    raise RuntimeError(
        "No AI available. Install Claude Code and run 'claude login', "
        "or install Gemini CLI and set GEMINI_API_KEY."
    )


def _prewarm_cache() -> None:
    """Write the stable skill prompt to Anthropic's cache on startup.
    Costs one cache-write; every subsequent build within 1h is a cache hit."""
    client = _get_anthropic_client()
    if client is None:
        return
    try:
        from job.profiles import get_profile_path
        profile = get_profile_path()
        if not profile or not profile.exists():
            return  # no profile yet — nothing to cache

        skill_text = (_skill_path() / "SKILL.md").read_text()
        latex = _skill_path() / "references" / "latex_template.md"
        if latex.exists():
            skill_text += f"\n\n## latex_template.md (embedded)\n\n{latex.read_text()}"
        if profile.exists():
            skill_text += f"\n\n## profile.md (embedded)\n\n{profile.read_text()}"
        slug = _candidate_name_slug()
        skill_text = _inject_name(skill_text, slug)

        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=0,
            system=[{"type": "text", "text": skill_text,
                     "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            messages=[{"role": "user", "content": "warmup"}],
        )
        print("[cache] pre-warmed on startup (1h TTL)")
    except Exception:
        pass  # pre-warm is best-effort, never block startup
    """Run pdflatex on a .tex file. Returns path to the generated PDF."""
    tex_dir = tex_path.parent
    tex_name = tex_path.name

    # Find pdflatex
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        # Try common macOS BasicTeX path
        common = Path("/usr/local/texlive/2026basic/bin/universal-darwin/pdflatex")
        if common.exists():
            pdflatex = str(common)
    if not pdflatex:
        raise RuntimeError(
            "pdflatex not found. Install BasicTeX (macOS: brew install --cask basictex) "
            "or MiKTeX (Windows: miktex.org/download) or texlive-latex-extra (Linux)."
        )

    env = None
    if sys.platform == "darwin":
        import os
        env = os.environ.copy()
        env["PATH"] = "/usr/local/texlive/2026basic/bin/universal-darwin:" + env.get("PATH", "")

    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = subprocess.CREATE_NO_WINDOW

    result = subprocess.run(
        [pdflatex, "-interaction=nonstopmode", tex_name],
        cwd=str(tex_dir),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        **extra,
    )

    pdf_path = tex_dir / tex_path.stem / ".." / tex_path.with_suffix(".pdf").name
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        err_snippet = result.stdout[-1000:] if result.stdout else result.stderr[-500:]
        raise RuntimeError(f"pdflatex failed. Log tail:\n{err_snippet}")

    # Clean up build artifacts
    for pattern in ["*.aux", "*.log", "*.out", "*.toc", "*.fls", "*.fdb_latexmk", "*.synctex.gz"]:
        for f in tex_dir.glob(pattern):
            try:
                f.unlink()
            except Exception:
                pass

    return pdf_path


def _parse_latex_response(response_text: str) -> tuple[str, dict]:
    """Extract LaTeX content and metadata JSON from model response."""
    # Find the JSON block after \end{document}
    meta = {}
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            meta = _json.loads(json_match.group(1))
        except Exception:
            pass
        response_text = response_text[:json_match.start()]

    # Extract LaTeX — everything from \documentclass to \end{document}
    latex_match = re.search(r'(\\documentclass.*?\\end\{document\})', response_text, re.DOTALL)
    if latex_match:
        return latex_match.group(1), meta

    # Fallback: strip markdown code fences
    text = response_text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        text = text.rsplit("```", 1)[0].strip()
    return text, meta


def _build_resume(job_id: str) -> None:
    try:
        _validate_profile()
        init_db()
        row = get_job(job_id)
        if not row:
            raise ValueError(f"Job {job_id} not found")

        row = dict(row)

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

        _set_stage(job_id, "Generating resume…")

        # Build the cached system prompt: SKILL.md + latex_template + profile
        skill_text = (_skill_path() / "SKILL.md").read_text()
        latex_template = _skill_path() / "references" / "latex_template.md"
        if latex_template.exists():
            skill_text += f"\n\n## latex_template.md (embedded)\n\n{latex_template.read_text()}"
        profile_path = get_profile_path()
        if profile_path and profile_path.exists():
            skill_text += f"\n\n## profile.md (embedded)\n\n{profile_path.read_text()}"

        name_slug = _candidate_name_slug()
        skill_text = _inject_name(skill_text, name_slug)

        user_prompt = (
            f"Apply to this job for me. Here is the job description:\n\n"
            f"Company: {company}\n"
            f"Title: {title}\n"
            f"Location: {row.get('location') or ''}\n"
            f"URL: {row.get('url') or ''}\n\n"
            f"{row['description']}"
        )

        response_text = _generate_content(skill_text, user_prompt, cwd=str(_skill_path()),
                                         stage_fn=lambda s: _set_stage(job_id, s))

        _set_stage(job_id, "Compiling PDF…")
        latex_content, meta = _parse_latex_response(response_text)

        # Use company from meta if available, sanitize for filesystem
        company_folder = meta.get("company", company)
        company_folder = re.sub(r'[^\w\-_]', '', company_folder.replace(" ", ""))[:64] or "Resume"

        output_dir = _resumes_path() / company_folder
        output_dir.mkdir(parents=True, exist_ok=True)

        tex_path = output_dir / f"{name_slug}_Resume.tex"
        tex_path.write_text(latex_content)
        (output_dir / "job_description.txt").write_text(row.get("description", ""))

        pdf_path = _compile_latex(tex_path)

        with _lock:
            _task_status[job_id] = {"status": "done", "pdf_path": str(pdf_path), "error": None}

    except Exception as e:
        with _lock:
            _task_status[job_id] = {"status": "error", "pdf_path": None, "error": str(e)}


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
        name_slug = _candidate_name_slug()

        # Find the resume tex for context
        resume_tex_content = ""
        for candidate in [
            _resumes_path() / company / f"{name_slug}_Resume.tex",
            _resumes_path() / company.replace(" ", "") / f"{name_slug}_Resume.tex",
            _resumes_path() / company.replace(" ", "").replace("/", "") / f"{name_slug}_Resume.tex",
        ]:
            if candidate.exists():
                resume_tex_content = f"\n\nThe resume for this role (for consistency):\n```latex\n{candidate.read_text()[:3000]}\n```"
                break

        _set_cl_stage(job_id, "Generating cover letter…")

        # Build cached system prompt
        skill_text = (_cl_skill_path() / "SKILL.md").read_text()
        profile_path = get_profile_path()
        if profile_path and profile_path.exists():
            skill_text += f"\n\n## profile.md (embedded)\n\n{profile_path.read_text()}"
        skill_text = _inject_name(skill_text, name_slug)

        # Update cover letter skill to also return raw LaTeX
        skill_text += "\n\n## Output format\nReturn ONLY the raw LaTeX content (starting with \\documentclass), no explanations. After \\end{document} include a JSON block: ```json {\"company\": \"<name>\"} ```"

        user_prompt = (
            f"Write a cover letter for this job.\n\n"
            f"Company: {company}\n"
            f"Title: {title}\n"
            f"Location: {row.get('location') or ''}\n\n"
            f"Job description:\n{row['description']}"
            f"{resume_tex_content}"
        )

        response_text = _generate_content(skill_text, user_prompt, cwd=str(_cl_skill_path()),
                                         stage_fn=lambda s: _set_cl_stage(job_id, s))

        _set_cl_stage(job_id, "Compiling PDF…")
        latex_content, meta = _parse_latex_response(response_text)

        company_folder = meta.get("company", company)
        company_folder = re.sub(r'[^\w\-_]', '', company_folder.replace(" ", ""))[:64] or "CoverLetter"

        output_dir = _resumes_path() / company_folder
        output_dir.mkdir(parents=True, exist_ok=True)

        tex_path = output_dir / f"{name_slug}_Cover_Letter.tex"
        tex_path.write_text(latex_content)

        pdf_path = _compile_latex(tex_path)

        with _lock:
            _cl_task_status[job_id] = {"status": "done", "pdf_path": str(pdf_path), "error": None}

    except Exception as e:
        with _lock:
            _cl_task_status[job_id] = {"status": "error", "pdf_path": None, "error": str(e)}


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

        # Replace relative ../resumes with the absolute profile resumes path
        # so the AI writes to profiles/<slug>/resumes/ not the project root
        resumes_abs = str(_resumes_path())
        skill_instructions = skill_instructions.replace("../resumes", resumes_abs)

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

        # Replace relative ../resumes with absolute profile resumes path
        resumes_abs = str(_resumes_path())
        skill_instructions = skill_instructions.replace("../resumes", resumes_abs)

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
