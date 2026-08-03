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
    assert m["score"] == 40  # 2 / max(2,5) = 40%, not 100%


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
