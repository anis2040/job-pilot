"""Smoke tests for the profile management module.

All tests run fully offline. PROFILES_DIR and ACTIVE_FILE are monkeypatched to
a tmp_path directory, and _update_symlinks is stubbed to avoid touching the
real filesystem outside the test sandbox.
"""
import pytest

import job.profiles as profiles


@pytest.fixture
def temp_profiles(tmp_path, monkeypatch):
    pdir = tmp_path / "profiles"
    pdir.mkdir()
    monkeypatch.setattr(profiles, "PROFILES_DIR", pdir)
    monkeypatch.setattr(profiles, "ACTIVE_FILE", pdir / ".active")
    monkeypatch.setattr(profiles, "_update_symlinks", lambda d: None)
    return pdir


# ── list / create ─────────────────────────────────────────────────────────────

def test_list_empty(temp_profiles):
    assert profiles.list_profiles() == []


def test_create_makes_directory(temp_profiles):
    slug = profiles.create_profile("John Doe")
    assert slug == "john-doe"
    assert (temp_profiles / "john-doe").is_dir()


def test_list_after_create(temp_profiles):
    profiles.create_profile("John Doe")
    result = profiles.list_profiles()
    assert len(result) == 1
    assert result[0].slug == "john-doe"


def test_create_collision_adds_suffix(temp_profiles):
    slug1 = profiles.create_profile("John Doe")
    slug2 = profiles.create_profile("John Doe")
    assert slug1 == "john-doe"
    assert slug2 == "john-doe-1"
    assert (temp_profiles / "john-doe-1").is_dir()


# ── set_active / get_active_slug ──────────────────────────────────────────────

def test_get_active_slug_none_when_unset(temp_profiles):
    assert profiles.get_active_slug() is None


def test_set_active_writes_file(temp_profiles):
    profiles.create_profile("John Doe")
    result = profiles.set_active("john-doe")
    assert result is True
    assert (temp_profiles / ".active").read_text().strip() == "john-doe"


def test_get_active_slug_returns_slug(temp_profiles):
    profiles.create_profile("John Doe")
    profiles.set_active("john-doe")
    assert profiles.get_active_slug() == "john-doe"


def test_set_active_invalid_returns_false(temp_profiles):
    assert profiles.set_active("nonexistent") is False


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_removes_directory(temp_profiles):
    profiles.create_profile("Jane Doe")
    assert profiles.delete_profile("jane-doe") is True
    assert not (temp_profiles / "jane-doe").exists()


def test_delete_active_profile_blocked(temp_profiles):
    profiles.create_profile("Jane Doe")
    profiles.set_active("jane-doe")
    assert profiles.delete_profile("jane-doe") is False
    assert (temp_profiles / "jane-doe").is_dir()


def test_delete_nonexistent_returns_false(temp_profiles):
    assert profiles.delete_profile("nobody") is False


# ── utility functions ─────────────────────────────────────────────────────────

def test_slugify_basic():
    assert profiles.slugify("John Doe") == "john-doe"


def test_slugify_removes_apostrophes():
    assert profiles.slugify("John O'Malley") == "john-omalley"


def test_slugify_handles_multiple_spaces():
    assert profiles.slugify("  Jane  Doe  ") == "jane-doe"


def test_name_from_markdown_extracts_h1():
    text = "# Jane Doe — Senior Engineer\nSome content"
    assert profiles.name_from_markdown(text) == "Jane Doe"


def test_name_from_markdown_dash_separator():
    text = "# Jane Doe - Engineer"
    assert profiles.name_from_markdown(text) == "Jane Doe"


def test_name_from_markdown_returns_none_if_no_heading():
    assert profiles.name_from_markdown("Just some text\nno heading") is None
