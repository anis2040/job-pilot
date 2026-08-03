"""Deterministic job↔profile match signal.

Computes how well a job's description overlaps the candidate's real skills —
using only the shared tech vocabulary (skills_vocab) intersected with the
structured profile (profile.json). No LLM, no fabricated scores: every number
traces to keywords that actually appear in both the JD and the profile.
"""
from __future__ import annotations

from .skills_vocab import detect_keywords


def _profile_skills(profile: dict) -> set[str]:
    """Lowercased skill set from the profile: competencies + skills detected in
    its summary and experience bullets (so 'built Angular apps' counts)."""
    if not profile:
        return set()
    skills = {c.strip().lower() for c in (profile.get("competencies") or []) if c and c.strip()}
    text = " ".join([
        profile.get("summary", "") or "",
        " ".join(b for e in (profile.get("experience") or []) for b in (e.get("bullets") or [])),
    ])
    skills |= {k.lower() for k in detect_keywords(text)}
    return skills


def compute_match(description: str, profile: dict | None) -> dict | None:
    """Return {score, matched, missing} for a job description vs the profile,
    or None when there's nothing to score (no profile, or the JD mentions no
    known tech keywords — better to show nothing than a misleading 0%).

    score = round(100 * matched / detected-in-JD).
    matched / missing are the JD's tech keywords split by whether the profile
    supports them.
    """
    if not profile or not description:
        return None
    jd_keywords = detect_keywords(description)
    if not jd_keywords:
        return None
    skills = _profile_skills(profile)
    matched = [k for k in jd_keywords if k.lower() in skills]
    missing = [k for k in jd_keywords if k.lower() not in skills]
    score = round(100 * len(matched) / len(jd_keywords))
    return {"score": score, "matched": matched, "missing": missing}
