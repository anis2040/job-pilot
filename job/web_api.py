from __future__ import annotations
import os
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
from .profiles import get_profile_path, get_resumes_path, company_resumes_path, company_cover_letters_path

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


_GROQ_MODELS      = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]
_ANTHROPIC_MODELS = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-6"]
_GEMINI_MODELS    = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-flash-lite-latest"]

_MODEL_DEFAULTS = {
    "groq":      "llama-3.3-70b-versatile",
    "anthropic": "claude-haiku-4-5",
    "gemini":    "gemini-3.5-flash-lite",
}


def _get_model(provider: str) -> str:
    """Return the configured model for a provider, falling back to the default."""
    import os
    _load_env()
    key = f"{provider.upper()}_MODEL"
    val = os.environ.get(key, "").strip()
    return val or _MODEL_DEFAULTS.get(provider, "")


_MODEL_LIST_CACHE = {}   # provider -> (monotonic_expiry, [models])
_MODEL_LIST_TTL = 300     # seconds


def _clear_model_cache(provider: str = None):
    """Invalidate the model-list cache (all providers, or one). Call after a key change."""
    if provider is None:
        _MODEL_LIST_CACHE.clear()
    else:
        _MODEL_LIST_CACHE.pop(provider, None)


def _list_models(provider: str, use_cache: bool = True) -> list:
    """Fetch the live list of usable models for a provider's configured key.
    Cached for _MODEL_LIST_TTL seconds. Falls back to the static list on failure."""
    import time as _time
    if use_cache:
        entry = _MODEL_LIST_CACHE.get(provider)
        if entry and entry[0] > _time.monotonic():
            return entry[1]

    result = _fetch_models(provider)

    # Only cache a successful live fetch (i.e. not the static fallback), so a
    # transient API error doesn't pin the static list for 5 minutes.
    static = {"groq": _GROQ_MODELS, "gemini": _GEMINI_MODELS, "anthropic": _ANTHROPIC_MODELS}.get(provider, [])
    if result and result is not static:
        _MODEL_LIST_CACHE[provider] = (_time.monotonic() + _MODEL_LIST_TTL, result)
    return result


def _fetch_models(provider: str) -> list:
    """Uncached live fetch of usable models for a provider. Static list on failure."""
    try:
        if provider == "groq":
            client = _get_groq_client()
            if client is None:
                return _GROQ_MODELS
            models = [m.id for m in client.models.list().data]
            # Keep only chat/text models; drop whisper/tts/guard/vision-only helpers
            chat = [m for m in models if not any(x in m.lower() for x in ("whisper", "tts", "guard", "embed"))]
            return sorted(chat) or _GROQ_MODELS

        if provider == "gemini":
            client = _get_gemini_client()
            if client is None:
                return _GEMINI_MODELS
            out = []
            for m in client.models.list():
                methods = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", []) or []
                name = m.name.replace("models/", "")
                if "generateContent" in methods and _is_gemini_text_model(name):
                    out.append(name)
            return out or _GEMINI_MODELS

        if provider == "anthropic":
            client = _get_anthropic_client()
            if client is None:
                return _ANTHROPIC_MODELS
            models = [m.id for m in client.models.list().data]
            return models or _ANTHROPIC_MODELS
    except Exception as e:
        print(f"[{provider}] model list failed ({e.__class__.__name__}), using static list")

    return {"groq": _GROQ_MODELS, "gemini": _GEMINI_MODELS, "anthropic": _ANTHROPIC_MODELS}.get(provider, [])


def _is_gemini_text_model(name: str) -> bool:
    """Filter out image/tts/audio/robotics/embedding Gemini models — keep chat text models."""
    n = name.lower()
    if not (n.startswith("gemini") or n.startswith("gemma")):
        return False
    bad = ("image", "tts", "audio", "vision", "embed", "robotics", "computer-use",
           "lyria", "nano-banana", "deep-research", "antigravity", "omni")
    return not any(b in n for b in bad)


def _log_tokens(tag: str, model: str, **counts: int) -> None:
    parts = " ".join(f"{k}={v}" for k, v in counts.items())
    print(f"[{tag}/{model}] {parts}")


def _blacklisted(text: str, blacklist: list[str]) -> str | None:
    combined = text.lower()
    for kw in blacklist:
        if kw in combined:
            return kw
    return None


def _get_groq_client():
    """Return a Groq client if GROQ_API_KEY is set, else None."""
    _load_env()
    import os
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except Exception:
        return None


def _build_with_groq(system_text: str, user_prompt: str, stage_fn=None) -> str:
    """Call Groq API — free tier, fast, no billing required."""
    client = _get_groq_client()
    if client is None:
        raise RuntimeError("No Groq client available")
    if stage_fn:
        stage_fn("Generating with Groq…")
    model = _get_model("groq")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=4096,
            temperature=0.3,
        )
    except Exception as e:
        msg = str(e)
        # Free-tier TPM limit is per-model; small models (e.g. llama-3.1-8b-instant,
        # 6k TPM) can't fit a full resume prompt. Surface a clear, actionable error.
        if "rate_limit" in msg or "413" in msg or "too large" in msg.lower():
            raise RuntimeError(
                f"Groq model '{model}' hit its token/rate limit for this request. "
                f"Pick a model with a larger limit (e.g. llama-3.3-70b-versatile) "
                f"in AI Settings, or wait a minute and retry."
            ) from e
        raise
    u = response.usage
    _log_tokens("groq", model,
                input=getattr(u, "prompt_tokens", 0) or 0,
                output=getattr(u, "completion_tokens", 0) or 0,
                total=getattr(u, "total_tokens", 0) or 0)
    return response.choices[0].message.content


def _build_with_sdk(system_text: str, user_prompt: str, stage_fn=None) -> str:
    """Call Claude via SDK with prompt caching. Returns response text."""
    import anthropic
    client = _get_anthropic_client()
    if client is None:
        raise RuntimeError("No Anthropic client available")
    if stage_fn:
        stage_fn("Generating with Claude…")
    model = _get_model("anthropic")
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
    cache_read   = getattr(u, "cache_read_input_tokens",     0) or 0
    cache_write  = getattr(u, "cache_creation_input_tokens", 0) or 0
    uncached     = getattr(u, "input_tokens",                0) or 0
    output_toks  = getattr(u, "output_tokens",               0) or 0
    total_input  = uncached + cache_read + cache_write
    saved_pct    = round(cache_read / total_input * 100) if total_input else 0
    print(
        f"[cache/{model}] input={total_input} "
        f"(uncached={uncached} write={cache_write} read={cache_read}) "
        f"output={output_toks} saved={saved_pct}%"
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


def _clean_gemini_error(raw: str) -> str:
    """Extract a short human-readable message from the CLI's noisy error output."""
    if not raw:
        return "gemini subprocess failed"
    try:
        obj = _json.loads(raw)
        err = obj.get("error", obj)
        msg = err.get("message", "")
        try:
            inner = _json.loads(msg)
            err = inner.get("error", inner)
            msg = err.get("message", msg)
        except Exception:
            pass
        code   = err.get("code", "")
        status = err.get("status", "")
        parts  = [str(p) for p in (code, status, msg) if p]
        if parts:
            return " ".join(parts)[:300]
    except Exception:
        pass
    for kw in ("PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "UNAUTHENTICATED", "403", "429", "401"):
        if kw in raw:
            return f"Gemini API error ({kw})"
    return raw.strip().splitlines()[-1][:300] if raw.strip() else "gemini subprocess failed"


def _build_with_gemini_sdk(system_text: str, user_prompt: str, backend_out=None) -> str:
    """Call Gemini via SDK. Raises on any error (caller falls back to CLI)."""
    from google.genai import types
    client = _get_gemini_client()
    if client is None:
        raise RuntimeError("No Gemini SDK client available")
    model = _get_model("gemini")
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
        _log_tokens("gemini", model,
                    input=getattr(u, "prompt_token_count", 0) or 0,
                    output=getattr(u, "candidates_token_count", 0) or 0,
                    cached=getattr(u, "cached_content_token_count", 0) or 0,
                    total=getattr(u, "total_token_count", 0) or 0)
    if backend_out is not None:
        backend_out.append("sdk")
    return response.text


def _build_with_gemini_cli(system_text: str, user_prompt: str, cwd: str, backend_out=None) -> str:
    """Call Gemini via CLI subprocess (personal OAuth, no billing required)."""
    if not shutil.which("gemini"):
        raise RuntimeError(
            "No Gemini available. Set GEMINI_API_KEY with billing enabled, "
            "or install the Gemini CLI: npm install -g @google/gemini-cli"
        )
    if backend_out is not None:
        backend_out.append("cli")
    gemini_md = Path(cwd) / "GEMINI.md"
    gemini_md.write_text(system_text)
    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = subprocess.CREATE_NO_WINDOW
    model = _get_model("gemini")
    result = subprocess.run(
        ["gemini", "-m", model, "-p", user_prompt, "--yolo", "--skip-trust", "--output-format", "json"],
        capture_output=True, text=True, cwd=cwd, timeout=600, **extra,
    )
    if gemini_md.exists():
        gemini_md.unlink()
    if result.returncode != 0:
        raise RuntimeError(_clean_gemini_error(result.stderr or result.stdout))
    try:
        data = _json.loads(result.stdout)
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(_clean_gemini_error(result.stdout))
        response_text = data.get("response", "")
        stats = data.get("stats", {}).get("models", {})
        for model_name, model_data in stats.items():
            toks = model_data.get("tokens", {})
            _log_tokens(f"gemini/cli", model_name,
                        input=toks.get("input", 0) or 0,
                        output=toks.get("candidates", 0) or 0,
                        cached=toks.get("cached", 0) or 0,
                        total=toks.get("total", 0) or 0)
    except RuntimeError:
        raise
    except Exception:
        response_text = result.stdout
    return response_text


def _build_with_gemini(system_text: str, user_prompt: str, cwd: str, stage_fn=None, backend_out=None) -> str:
    """Call Gemini. Tries SDK first (if billing works), then CLI subprocess."""
    if stage_fn:
        stage_fn("Generating with Gemini…")
    client = _get_gemini_client()
    if client is not None:
        try:
            return _build_with_gemini_sdk(system_text, user_prompt, backend_out)
        except Exception as sdk_err:
            print(f"[gemini] SDK failed ({sdk_err.__class__.__name__}), falling back to CLI")
    return _build_with_gemini_cli(system_text, user_prompt, cwd, backend_out)


def _generate_content(system_text: str, user_prompt: str, cwd: str, stage_fn=None) -> str:
    """Use PREFERRED_PROVIDER if set and available, otherwise Groq → Anthropic → Gemini."""
    preferred = os.environ.get("PREFERRED_PROVIDER", "").strip().lower()

    def _try_groq():
        if _get_groq_client() is not None:
            return _build_with_groq(system_text, user_prompt, stage_fn=stage_fn)
        return None

    def _try_anthropic():
        if _get_anthropic_client() is not None:
            return _build_with_sdk(system_text, user_prompt, stage_fn=stage_fn)
        return None

    def _try_gemini():
        if _get_gemini_client() is not None or shutil.which("gemini"):
            return _build_with_gemini(system_text, user_prompt, cwd=cwd, stage_fn=stage_fn)
        return None

    _order = {"groq": [_try_groq, _try_anthropic, _try_gemini],
              "anthropic": [_try_anthropic, _try_groq, _try_gemini],
              "gemini": [_try_gemini, _try_groq, _try_anthropic]}
    fns = _order.get(preferred, [_try_groq, _try_anthropic, _try_gemini])

    for fn in fns:
        result = fn()
        if result is not None:
            return result

    raise RuntimeError(
        "No AI provider configured. Add a GROQ_API_KEY to .env "
        "(free at console.groq.com) or install Gemini CLI."
    )


def _append_profile(skill_text: str) -> str:
    """Append the active profile.md to skill_text if it exists. Returns updated text."""
    profile_path = get_profile_path()
    if profile_path and profile_path.exists():
        skill_text += f"\n\n## profile.md (embedded)\n\n{profile_path.read_text()}"
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
        from job.profiles import get_profile_path
        profile = get_profile_path()
        if not profile or not profile.exists():
            return  # no profile yet — nothing to cache

        skill_text = (_skill_path() / "SKILL.md").read_text()
        latex = _skill_path() / "references" / "latex_template.md"
        if latex.exists():
            skill_text += f"\n\n## latex_template.md (embedded)\n\n{latex.read_text()}"
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


def _compile_latex(tex_path: Path) -> Path:
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


def _build_resume_prompt(row: dict, company: str, title: str, name_slug: str, skill_dir) -> tuple[str, str]:
    """Build system skill_text and user_prompt for a resume. Returns (skill_text, user_prompt)."""
    skill_text = (skill_dir / "SKILL.md").read_text()
    latex_template = skill_dir / "references" / "latex_template.md"
    if latex_template.exists():
        skill_text += f"\n\n## latex_template.md (embedded)\n\n{latex_template.read_text()}"
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
    skill_text = (skill_dir / "SKILL.md").read_text()
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
            resume_tex_content = f"\n\nThe resume for this role (for consistency):\n```latex\n{candidate.read_text()[:3000]}\n```"
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
    status_dict = _task_status if is_resume else _cl_task_status
    stage_fn = _set_stage if is_resume else _set_cl_stage
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
            if job_id.startswith("li_") and (not row.get("description") or len(row["description"]) < 100):
                stage_fn(job_id, "Fetching job description…")
                desc = li_fetch_description(row["url"])
                if desc:
                    update_description(job_id, desc)
                    row["description"] = desc
        else:
            if job_id.startswith("li_") and not row.get("description"):
                stage_fn(job_id, "Fetching job description…")
                desc = li_fetch_description(row["url"])
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
        tex_path.write_text(latex_content)
        if is_resume:
            (output_dir / "job_description.txt").write_text(row.get("description", ""))

        pdf_path = _compile_latex(tex_path)

        with _lock:
            status_dict[job_id] = {"status": "done", "pdf_path": str(pdf_path), "error": None}

    except Exception as e:
        with _lock:
            status_dict[job_id] = {"status": "error", "pdf_path": None, "error": str(e)}


def _build_resume(job_id: str) -> None:
    _build_document(job_id, "resume")


def _build_cover_letter(job_id: str) -> None:
    _build_document(job_id, "cover_letter")


def _should_include_job(job, config) -> tuple[bool, str | None]:
    """Return (True, None) if job passes all filters, else (False, matched_keyword_or_reason).
    Pure — no I/O, no DB access."""
    if job.company and job.company.lower() in config.company_blacklist:
        return False, None
    if config.title_filter and not any(kw in job.title.lower() for kw in config.title_filter):
        return False, None
    kw = _blacklisted(job.title + " " + job.description, config.blacklist)
    if kw:
        return False, kw
    return True, None


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
                include, kw = _should_include_job(job, config)
                if not include:
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




def call_ai(prompt: str, system: str = "") -> str:
    """Call the best available AI provider. Used by web.py for suggest-config and parse-resume."""
    return _generate_content(
        system_text=system or "Return only the requested output as valid JSON. No explanation.",
        user_prompt=prompt,
        cwd=str(_skill_path()),
    )
