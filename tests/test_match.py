"""Tests for job/match.py — deterministic job↔profile match signal."""
from job.match import compute_match


_PROFILE = {
    "competencies": ["Angular", "TypeScript", "NgRx"],
    "summary": "Frontend engineer.",
    "experience": [{"bullets": ["Built React and GraphQL apps with AWS"]}],
}


def test_full_match():
    m = compute_match("We need Angular and TypeScript.", _PROFILE)
    assert set(m["matched"]) == {"Angular", "TypeScript"}
    assert m["missing"] == []
    assert m["matched_count"] == 2


def test_partial_match():
    m = compute_match("Angular, React, Kafka, Python required.", _PROFILE)
    assert set(m["matched"]) == {"Angular", "React"}       # React from a bullet
    assert set(m["missing"]) == {"Kafka", "Python"}
    assert m["matched_count"] == 2


def test_score_denominator_floored():
    # A JD naming only 2 keywords, both matched, must NOT read as 100% —
    # the floored denominator (min 5) prevents vague-JD inflation.
    m = compute_match("Angular and TypeScript.", _PROFILE)
    assert m["matched_count"] == 2
    assert m["keyword_score"] == 40  # 2 / max(2,5) = 40%, not 100%


def test_skills_from_bullets_and_summary_count():
    # AWS is only in a bullet, not the competencies list — still counts.
    m = compute_match("AWS experience needed.", _PROFILE)
    assert m["matched"] == ["AWS"] and m["matched_count"] == 1


def test_r_not_matched_as_false_positive():
    # "R" (removed from vocab) must not match R&D / stray letters.
    m = compute_match("Join our R&D team building Angular apps.", _PROFILE)
    assert "R" not in (m["matched"] + m["missing"])
    assert "Angular" in m["matched"]


def test_zero_keyword_jd_returns_none():
    assert compute_match("We want a passionate team player.", _PROFILE) is None


def test_no_profile_returns_none():
    assert compute_match("Angular role", None) is None
    assert compute_match("Angular role", {}) is None


def test_empty_description_returns_none():
    assert compute_match("", _PROFILE) is None


def test_synonym_alignment():
    # Profile lists "React"; JD says "ReactJS" — synonym canonicalization means
    # they align and it counts as matched, not missing.
    prof = {"competencies": ["React"], "summary": "", "experience": []}
    m = compute_match("We need ReactJS and Postgres.", prof)
    assert "React" in m["matched"]
    assert "PostgreSQL" in m["missing"]  # profile lacks it, canonicalized


def test_descriptive_competency_phrases_canonicalize():
    # Regression: a profile listing a rich phrase like 'CI/CD & quality delivery'
    # must still match a JD's canonical 'CI/CD' (not be treated as a separate
    # raw string that never matches).
    prof = {"competencies": ["CI/CD & quality-driven delivery", "Angular architecture"],
            "summary": "", "experience": []}
    m = compute_match("We use CI/CD pipelines and Angular.", prof)
    assert "CI/CD" in m["matched"]
    assert "Angular" in m["matched"]
    assert m["missing"] == []


# ── match_text (title + description, centralized) ─────────────────────────────

from job.match import match_text


def test_match_text_title_plus_description():
    assert match_text({"title": "Senior Angular Engineer", "description": "Build with NgRx"}) \
        == "Senior Angular Engineer\nBuild with NgRx"


def test_match_text_title_only_when_no_description():
    assert match_text({"title": "React Developer"}) == "React Developer"
    assert match_text({"title": "React Developer", "description": ""}) == "React Developer"


def test_match_text_none_safe():
    assert match_text(None) == ""


def test_match_scores_from_title_when_no_description():
    # A LinkedIn-style job with no description still scores from its title.
    prof = {"competencies": ["Angular", "TypeScript"], "summary": "", "experience": []}
    text = match_text({"title": "Senior Angular Engineer", "description": ""})
    m = compute_match(text, prof)
    assert m is not None
    assert "Angular" in m["matched"]


# ── semantic_score + blend ────────────────────────────────────────────────────

from job.match import semantic_score


def test_semantic_score_range():
    v = [1.0, 0.0, 0.0]
    assert semantic_score(v, v) == 100          # cos 1 -> clamped 100
    assert semantic_score(v, [0.0, 1.0, 0.0]) == 0   # cos 0 -> clamped 0
    assert semantic_score(None, v) is None
    assert semantic_score(v, None) is None


def test_semantic_score_midrange():
    # cos 0.65 -> (0.65-0.4)/0.5*100 = 50
    import math
    # build two unit vectors with cosine ~0.65
    a = [1.0, 0.0]
    import math as _m
    theta = _m.acos(0.65)
    b = [_m.cos(theta), _m.sin(theta)]
    assert abs(semantic_score(a, b) - 50) <= 1


def test_embed_text_no_key_returns_none(monkeypatch):
    # No Gemini client -> embed helpers return None/None-list, never raise.
    import job.ai_providers as ai
    monkeypatch.setattr(ai, "_get_gemini_client", lambda: None)
    assert ai.embed_text("Angular engineer") is None
    assert ai.embed_texts(["a", "b"]) == [None, None]


# ── semantic_enabled gate ─────────────────────────────────────────────────────

def test_semantic_enabled_off_skips_embedding(monkeypatch):
    import job.match as m, job.ai_providers as ai
    monkeypatch.setenv("SEMANTIC_MATCH", "off")
    monkeypatch.setattr(ai, "_load_env", lambda: None)
    monkeypatch.setattr(ai, "embedding_provider", lambda: "gemini")  # provider present
    assert m.semantic_enabled() is False
    # get_profile_embedding must NOT call embed when disabled
    called = []
    monkeypatch.setattr(ai, "embed_text", lambda t: called.append(1) or [0.1])
    assert m.get_profile_embedding({"name": "X", "summary": "eng", "competencies": ["Angular"]}) is None
    assert not called


def test_semantic_enabled_on_but_no_provider(monkeypatch):
    import job.match as m, job.ai_providers as ai
    monkeypatch.setenv("SEMANTIC_MATCH", "on")
    monkeypatch.setattr(ai, "_load_env", lambda: None)
    monkeypatch.setattr(ai, "embedding_provider", lambda: None)  # no gemini
    assert m.semantic_enabled() is False


def test_semantic_enabled_on_with_provider(monkeypatch):
    import job.match as m, job.ai_providers as ai
    monkeypatch.setenv("SEMANTIC_MATCH", "on")
    monkeypatch.setattr(ai, "_load_env", lambda: None)
    monkeypatch.setattr(ai, "embedding_provider", lambda: "gemini")
    assert m.semantic_enabled() is True
