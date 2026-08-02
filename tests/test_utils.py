"""Unit tests for job.utils — pure string logic, no I/O."""
import pytest

from job.utils import parse_experience, location_matches, _normalise


class TestParseExperience:
    @pytest.mark.parametrize("text,expected", [
        ("We need 5+ years of experience", "5+ years"),
        ("Looking for 3-5 years in the field", "3-5 years"),
        ("Minimum 3 years required", "3+ years"),
        ("At least 2 years experience", "2+ years"),
        ("4 years of experience preferred", "4+ years"),
    ])
    def test_explicit_years(self, text, expected):
        assert parse_experience(text) == expected

    def test_seniority_inference(self):
        assert parse_experience("Senior Engineer role") == "5+ years (inferred)"
        assert parse_experience("Principal Architect") == "7+ years (inferred)"
        assert parse_experience("Lead Developer") == "7+ years (inferred)"

    def test_no_signal(self):
        assert parse_experience("Great place to work") == ""

    def test_empty(self):
        assert parse_experience("") == ""
        assert parse_experience(None) == ""


class TestLocationMatches:
    def test_empty_search_matches_all(self):
        assert location_matches("Berlin, Germany", "") is True

    def test_worldwide_search_matches_all(self):
        assert location_matches("Tokyo, Japan", "worldwide") is True
        assert location_matches("Anywhere", "remote") is True

    def test_job_with_no_location_passes(self):
        assert location_matches("", "Germany") is True
        assert location_matches("Remote", "Germany") is True

    def test_matching_country(self):
        assert location_matches("Berlin, Germany", "Germany") is True
        assert location_matches("Munich", "germany") is True

    def test_mismatched_country_rejected(self):
        assert location_matches("Paris, France", "Germany") is False
        assert location_matches("London, UK", "United States") is False

    def test_us_state_signals(self):
        assert location_matches("San Francisco, CA", "United States") is True
        assert location_matches("Remote US", "United States") is True

    def test_unknown_country_substring_fallback(self):
        # Portugal isn't in the signals map — falls back to substring
        assert location_matches("Lisbon, Portugal", "Portugal") is True
        assert location_matches("Somewhere else", "Portugal") is False


def test_normalise():
    assert _normalise("  Berlin, GERMANY  ") == "berlin, germany"
