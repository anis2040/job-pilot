from __future__ import annotations
import os
import sys
import subprocess
import shutil
import json as _json
from pathlib import Path

from . import paths


def _load_env() -> None:
    """Load .env file from project root into os.environ."""
    env_path = paths.BASE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            # Always overwrite API keys and provider preference from .env
            # so that keys saved via the UI take effect without a restart
            if k in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY",
                     "GOOGLE_API_KEY", "ANTHROPIC_AUTH_TOKEN", "PREFERRED_PROVIDER"):
                os.environ[k] = v
            else:
                os.environ.setdefault(k, v)


def _get_anthropic_client():
    """Return an Anthropic client pointed at the public API, or None."""
    _load_env()
    try:
        import anthropic
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
            # For token/OAuth clients, reject proxy endpoints
            base = str(getattr(getattr(client, "_client", None), "base_url", ""))
            if base and "anthropic.com" not in base:
                return None
            return client
        else:
            # No explicit credentials — don't attempt to create a client.
            # The claude CLI subprocess path handles OAuth login separately.
            return None
    except Exception:
        return None


_GROQ_MODELS      = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.1-8b-instant"]
_ANTHROPIC_MODELS = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-6"]
_GEMINI_MODELS    = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-flash-lite-latest"]

_MODEL_DEFAULTS = {
    "groq":      "llama-3.3-70b-versatile",
    "anthropic": "claude-haiku-4-5",
    "gemini":    "gemini-3.5-flash-lite",
}


def _get_model(provider: str) -> str:
    """Return the configured model for a provider, falling back to the default."""
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


def _get_groq_client():
    """Return a Groq client if GROQ_API_KEY is set, else None."""
    _load_env()
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
            max_tokens=4096,  # Groq free tier counts input+output vs an 8-12K TPM cap; keep headroom
            temperature=0.3,
        )
    except Exception as e:
        msg = str(e)
        # Free-tier limits are per-model (TPM and TPD): smaller models and
        # gpt-oss (8K TPM) can't fit a full resume prompt + output. Surface a
        # clear, actionable error.
        if "rate_limit" in msg or "413" in msg or "429" in msg or "too large" in msg.lower():
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


def _build_with_sdk(system_text: str, user_prompt: str, stage_fn=None, on_delta=None) -> str:
    """Call Claude via SDK with prompt caching. Returns response text.

    If `on_delta` is provided, streams the response and calls on_delta(text_so_far)
    as tokens arrive — used to drive a live preview. Falls back to a single
    non-streamed call if streaming isn't possible."""
    import anthropic
    client = _get_anthropic_client()
    if client is None:
        raise RuntimeError("No Anthropic client available")
    if stage_fn:
        stage_fn("Generating with Claude…")
    model = _get_model("anthropic")
    system = [{
        "type": "text",
        "text": system_text,
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    }]
    messages = [{"role": "user", "content": user_prompt}]

    if on_delta is not None:
        # Stream tokens; report cumulative text to on_delta.
        acc = []
        with client.messages.stream(model=model, max_tokens=8192,
                                    system=system, messages=messages) as stream:
            for text in stream.text_stream:
                acc.append(text)
                try:
                    on_delta("".join(acc))
                except Exception:
                    pass  # preview is best-effort; never break generation
        return "".join(acc)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=messages,
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
            max_output_tokens=8192,
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
    gemini_md.write_text(system_text, encoding="utf-8")
    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = subprocess.CREATE_NO_WINDOW
    model = _get_model("gemini")
    gemini_exe = shutil.which("gemini") or "gemini"
    result = subprocess.run(
        [gemini_exe, "-m", model, "-p", user_prompt, "--yolo", "--skip-trust", "--output-format", "json"],
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


def _generate_content(system_text: str, user_prompt: str, cwd: str, stage_fn=None, on_delta=None) -> str:
    """Use PREFERRED_PROVIDER if set and available, otherwise Groq → Anthropic → Gemini.

    `on_delta(text_so_far)` streams a live preview when the chosen provider
    supports it (currently Claude); other providers ignore it."""
    preferred = os.environ.get("PREFERRED_PROVIDER", "").strip().lower()

    def _try_groq():
        if _get_groq_client() is not None:
            return _build_with_groq(system_text, user_prompt, stage_fn=stage_fn)
        return None

    def _try_anthropic():
        if _get_anthropic_client() is not None:
            return _build_with_sdk(system_text, user_prompt, stage_fn=stage_fn, on_delta=on_delta)
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


def call_ai(prompt: str, system: str = "") -> str:
    """Call the best available AI provider. Used by web.py for suggest-config and parse-resume."""
    from .documents import _skill_path
    return _generate_content(
        system_text=system or "Return only the requested output as valid JSON. No explanation.",
        user_prompt=prompt,
        cwd=str(_skill_path()),
    )
