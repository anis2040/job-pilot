"""Tests for job/match.py — deterministic job↔profile match signal."""
from job.match import compute_match


_PROFILE = {
    "competencies": ["Angular", "TypeScript", "NgRx"],
    "summary": "Frontend engineer.",
    "experience": [{"bullets": ["Built React and GraphQL apps with AWS"]}],
}


def test_full_match():
    m = compute_match("We need Angular and TypeScript.", _PROFILE)
    assert m["score"] == 100
    assert set(m["matched"]) == {"Angular", "TypeScript"}
    assert m["missing"] == []


def test_partial_match():
    m = compute_match("Angular, React, Kafka, Python required.", _PROFILE)
    assert set(m["matched"]) == {"Angular", "React"}       # React from a bullet
    assert set(m["missing"]) == {"Kafka", "Python"}
    assert m["score"] == 50


def test_skills_from_bullets_and_summary_count():
    # AWS is only in a bullet, not the competencies list — still counts.
    m = compute_match("AWS experience needed.", _PROFILE)
    assert m["matched"] == ["AWS"] and m["score"] == 100


def test_zero_keyword_jd_returns_none():
    assert compute_match("We want a passionate team player.", _PROFILE) is None


def test_no_profile_returns_none():
    assert compute_match("Angular role", None) is None
    assert compute_match("Angular role", {}) is None


def test_empty_description_returns_none():
    assert compute_match("", _PROFILE) is None
