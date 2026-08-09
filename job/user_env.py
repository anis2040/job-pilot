"""Per-user AI settings stored in profiles/<user_id>/.env."""
from __future__ import annotations

from pathlib import Path

from .profiles import ensure_user_dir, user_env_path
from .user_context import get_current_user_id

AI_ENV_KEYS = frozenset({
    "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "ANTHROPIC_AUTH_TOKEN", "PREFERRED_PROVIDER", "GROQ_MODEL",
    "ANTHROPIC_MODEL", "GEMINI_MODEL", "SEMANTIC_MATCH",
    "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
})


def read_user_env(user_id: str | None = None) -> dict[str, str]:
    path = user_env_path(user_id)
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                out[k] = v
    return out


def write_user_env_var(key: str, value: str, user_id: str | None = None) -> Path:
    ensure_user_dir(user_id)
    path = user_env_path(user_id)
    lines = []
    if path.exists():
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if not l.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def remove_user_env_var(key: str, user_id: str | None = None) -> None:
    path = user_env_path(user_id)
    if not path.exists():
        return
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if not l.startswith(f"{key}=")]
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def get_user_setting(key: str, default: str = "", user_id: str | None = None) -> str:
    return read_user_env(user_id).get(key, default)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "••••"
    return "••••" + value[-4:]
