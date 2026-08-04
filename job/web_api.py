"""Facade for the job backend, kept for backward-compatible imports.

The implementation was split into focused modules (task_state, ai_providers,
latex, documents, fetch_worker). This module re-exports the public surface so
existing `from job.web_api import ...` (web.py) and `from .web_api import ...`
(cli.py, tests) imports keep working unchanged.
"""
from __future__ import annotations
import os  # noqa: F401  (test_imports asserts job.web_api exposes `os`)

from . import paths

# Back-compat alias: tests and older code referenced job.web_api._BASE.
_BASE = paths.BASE

# ── Task-state / threading orchestration ────────────────────────────────────
from .task_state import (  # noqa: F401,E402
    clear_task_state, get_task_status, get_cl_task_status, get_fetch_status,
    trigger_resume, trigger_cover_letter, trigger_fetch,
    _set_stage, _set_cl_stage,
    _task_status, _cl_task_status, _fetch_status, _lock,
)

# ── AI providers, model listing, dispatch ───────────────────────────────────
from .ai_providers import (  # noqa: F401,E402
    _load_env,
    _get_anthropic_client, _get_groq_client, _get_gemini_client,
    _get_model, _list_models, _clear_model_cache, _fetch_models,
    _is_gemini_text_model, _log_tokens, _clean_gemini_error,
    _build_with_groq, _build_with_sdk,
    _build_with_gemini, _build_with_gemini_sdk, _build_with_gemini_cli,
    _generate_content, call_ai, call_ai_fast,
    _GROQ_MODELS, _ANTHROPIC_MODELS, _GEMINI_MODELS, _MODEL_DEFAULTS,
    _MODEL_LIST_CACHE, _MODEL_LIST_TTL,
)

# ── LaTeX compilation & parsing ─────────────────────────────────────────────
from .latex import _compile_latex, _parse_latex_response  # noqa: F401,E402

# ── Document / prompt building ──────────────────────────────────────────────
from .documents import (  # noqa: F401,E402
    _skill_path, _cl_skill_path, _resumes_path,
    _validate_profile, _candidate_name_slug, _inject_name,
    _append_profile, _sanitize_folder_name, _prewarm_cache,
    _build_resume_prompt, _build_cover_letter_prompt,
    _build_document, _build_resume, _build_cover_letter,
)

# ── Fetch worker ────────────────────────────────────────────────────────────
from .fetch_worker import _blacklisted, _should_include_job, _run_fetch  # noqa: F401,E402
