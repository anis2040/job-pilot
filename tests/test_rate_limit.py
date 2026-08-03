"""Tests for the Groq rate-limit parser and RateLimitError."""
import pytest

from job.ai_providers import _parse_groq_limit, RateLimitError


_REAL_TPD = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
    "llama-3.3-70b-versatile in organization org_x service tier on_demand on "
    "tokens per day (TPD): Limit 100000, Used 95115, Requested 8712. Please try "
    "again in 55m6.528s. ...'}}"
)


def test_parse_tpd_full_detail():
    d = _parse_groq_limit(_REAL_TPD)
    assert d["scope"] == "TPD"
    assert d["limit"] == 100000
    assert d["used"] == 95115
    # 55m6.528s ≈ 3307s
    assert 3300 <= d["retry_seconds"] <= 3310


def test_parse_tpm_partial():
    msg = ("Request too large for model gpt-oss on tokens per minute (TPM): "
           "Limit 8000, Requested 8362")
    d = _parse_groq_limit(msg)
    assert d["scope"] == "TPM"
    assert d["limit"] == 8000
    assert "used" not in d  # not present in this variant


def test_parse_retry_seconds_only():
    d = _parse_groq_limit("please try again in 12.4s")
    assert d["retry_seconds"] == 12


def test_parse_hours_minutes():
    d = _parse_groq_limit("try again in 1h2m")
    assert d["retry_seconds"] == 3720


def test_parse_no_match_returns_none():
    assert _parse_groq_limit("some unrelated error") is None
    assert _parse_groq_limit("") is None


def test_rate_limit_error_carries_fields():
    e = RateLimitError("msg", provider="groq", used=9, limit=10, retry_seconds=60, scope="TPD")
    d = e.as_dict()
    assert d == {"provider": "groq", "used": 9, "limit": 10, "retry_seconds": 60, "scope": "TPD"}
    assert isinstance(e, RuntimeError)  # still catchable as RuntimeError
