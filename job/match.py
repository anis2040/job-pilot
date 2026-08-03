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
    """Return a match signal for a job description vs the profile, or None when
    there's nothing to score (no profile, or the JD names no known tech keywords).

    Fields:
      matched     — the candidate's skills this job asks for (list)
      missing     — tech the job asks for that isn't in the profile (list)
      matched_count — len(matched); the PRIMARY, honest signal (absolute overlap)
      score       — coverage %, but on a floored denominator so a JD that names
                    very few keywords can't post a misleadingly high %. Kept as a
                    secondary hint, not the ranking key.

    Rationale (validated on real data): ranking by raw matched/detected rewarded
    vague postings (2 generic keywords → 67%) over detailed ones that genuinely
    matched more skills. matched_count ranks true fit far better.
    """
    if not profile or not description:
        return None
    jd_keywords = detect_keywords(description)
    if not jd_keywords:
        return None
    skills = _profile_skills(profile)
    matched = [k for k in jd_keywords if k.lower() in skills]
    missing = [k for k in jd_keywords if k.lower() not in skills]
    # Floor the denominator at 5 so a JD naming only 2-3 keywords can't inflate
    # the percentage; a substantive JD (>=5 keywords) uses its real count.
    denom = max(len(jd_keywords), 5)
    score = round(100 * len(matched) / denom)
    return {
        "matched": matched,
        "missing": missing,
        "matched_count": len(matched),
        "score": score,
    }
