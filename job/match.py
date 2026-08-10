"""Deterministic job↔profile match signal.

Computes how well a job's description overlaps the candidate's real skills —
using only the shared tech vocabulary (skills_vocab) intersected with the
structured profile (profile.json). No LLM, no fabricated scores: every number
traces to keywords that actually appear in both the JD and the profile.
"""
from __future__ import annotations

from .skills_vocab import detect_keywords


def semantic_enabled() -> bool:
    """True if semantic (embedding) matching should run: the user toggle is on
    (SEMANTIC_MATCH env, default on) AND an embedding provider is available.
    When False, all embedding calls are skipped and match falls back to the
    (free, deterministic) keyword score."""
    import os
    from .ai_providers import _env_get, embedding_provider
    if os.environ.get("SEMANTIC_MATCH", "").strip().lower() == "off":
        return False
    if _env_get("SEMANTIC_MATCH", "on").strip().lower() == "off":
        return False
    return embedding_provider() is not None


def match_text(job) -> str:
    """The text that represents a job for matching: title + description.

    Single source of truth for match input across the list view, detail view,
    and the resume keyword hint. Title is always present; description is added
    when available. This gives providers that store no description at fetch time
    (LinkedIn, Greenhouse) a real signal from the title alone, instead of a blank
    badge. Accepts a sqlite Row or a dict.
    """
    if job is None:
        return ""
    get = job.get if hasattr(job, "get") else (lambda k, d="": job[k] if k in job.keys() else d)
    title = (get("title", "") or "").strip()
    desc = (get("description", "") or "").strip()
    return f"{title}\n{desc}".strip()


def _profile_skills(profile: dict) -> set[str]:
    """Canonical skill set from the profile: run competencies, summary, and
    experience bullets through detect_keywords so everything is a canonical
    vocab term (lowercased). This is what lets a JD's canonical keyword match
    the profile — a raw competency phrase like 'CI/CD & quality delivery' is
    reduced to the canonical 'CI/CD', which is what the JD side produces too.
    """
    if not profile:
        return set()
    text = " ".join([
        " ".join(profile.get("competencies") or []),
        profile.get("summary", "") or "",
        " ".join(b for e in (profile.get("experience") or []) for b in (e.get("bullets") or [])),
    ])
    return {k.lower() for k in detect_keywords(text)}


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
        "keyword_score": score,
    }


# ── Semantic (embedding) score ────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    import math
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def semantic_score(job_vec, profile_vec) -> int | None:
    """Cosine similarity of job vs profile embeddings → 0-100, or None if either
    vector is missing. Cosine on typical text embeddings lands ~0.5-0.9, so we
    rescale [0.4, 0.9] → [0, 100] to spread the usable range; clamped."""
    if not job_vec or not profile_vec:
        return None
    cos = _cosine(job_vec, profile_vec)
    pct = round((cos - 0.4) / 0.5 * 100)
    return max(0, min(100, pct))


def profile_embedding_text(profile: dict | None) -> str:
    """Flatten the structured profile into a single string to embed."""
    if not profile:
        return ""
    parts = [
        profile.get("name", "") or "",
        profile.get("summary", "") or "",
        " ".join(profile.get("competencies") or []),
    ]
    for e in profile.get("experience") or []:
        parts.append(e.get("title", "") or "")
        parts.extend(e.get("bullets") or [])
    return "\n".join(p for p in parts if p).strip()


def profile_content_hash(profile: dict | None) -> str | None:
    """Hash of profile text used for match-cache and embedding invalidation."""
    text = profile_embedding_text(profile)
    if not text:
        return None
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:16]


_profile_embedding_cache: dict[tuple[str, str], list[float]] = {}


def get_profile_embedding(profile: dict | None):
    """Return the profile's embedding vector, cached in db_meta and recomputed
    only when the profile text changes (hash-guarded). None if unavailable or
    semantic matching is disabled."""
    if not semantic_enabled():
        return None
    text = profile_embedding_text(profile)
    if not text:
        return None
    import hashlib
    from .user_context import get_current_user_id

    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    uid = get_current_user_id()
    proc_key = (uid, h)
    if proc_key in _profile_embedding_cache:
        return _profile_embedding_cache[proc_key]
    try:
        from . import db
        cached = db.get_profile_embedding_meta()
        if cached and cached[0] == h:
            _profile_embedding_cache[proc_key] = cached[1]
            return cached[1]
        from .ai_providers import embed_text
        vec = embed_text(text)
        if vec:
            db.set_profile_embedding_meta(h, vec)
            _profile_embedding_cache[proc_key] = vec
        return vec
    except Exception:
        return None
