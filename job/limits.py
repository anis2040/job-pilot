"""Static free-tier rate-limit reference for AI providers.

We can only *observe* live limits from Groq (its 429s carry Used/Limit/reset).
For Gemini and Anthropic the numbers vary by plan and aren't returned per-call,
so these are documented free-tier approximations, surfaced in the UI labeled as
approximate. Used only to draw the "X / limit" usage bar — never for enforcement.
"""
from __future__ import annotations

# Per-model daily token limit (TPD) for Groq, exact from console.groq.com/docs/rate-limits.
_GROQ_TPD = {
    "llama-3.3-70b-versatile": 100_000,
    "openai/gpt-oss-120b":      200_000,
    "openai/gpt-oss-20b":       200_000,
    "llama-3.1-8b-instant":     500_000,
}
_GROQ_TPD_DEFAULT = 100_000

# Approximate daily token budgets for the others (order-of-magnitude reference).
_GEMINI_TPD_APPROX = 1_000_000     # AI Studio free tier, model-dependent
_ANTHROPIC_TPD_APPROX = 1_000_000  # varies by plan/credits


def usage_reference(provider: str, model: str) -> dict:
    """Return {limit_tpd, approx, resets} for a provider+model.

    - Groq: exact per-model TPD, rolling 24h window.
    - Gemini: approximate; resets midnight Pacific.
    - Anthropic: approximate; plan-dependent.
    """
    if provider == "groq":
        return {"limit_tpd": _GROQ_TPD.get(model, _GROQ_TPD_DEFAULT),
                "approx": False, "resets": "rolling 24h"}
    if provider == "gemini":
        return {"limit_tpd": _GEMINI_TPD_APPROX, "approx": True,
                "resets": "midnight PT"}
    if provider == "anthropic":
        return {"limit_tpd": _ANTHROPIC_TPD_APPROX, "approx": True,
                "resets": "plan-dependent"}
    return {"limit_tpd": 0, "approx": True, "resets": ""}
