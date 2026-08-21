"""Tests for the Build CV positioning config (job/build_cv_config.py).

Fully offline. A temp profile directory backs config.yaml; no network, no model.
Covers defaults, round-trip, validation, forward-compat, the read-modify-write
guarantee (build_cv save must not clobber searches/blacklist), and that each
stance produces a distinguishable prompt block.
"""
import pytest
import yaml

import job.profiles as profiles
from job.build_cv_config import BuildCvConfig, MAX_INSTRUCTIONS_LEN
from job.user_context import LOCAL_USER_ID


@pytest.fixture
def temp_profile(tmp_path, monkeypatch):
    pdir = tmp_path / "profiles"
    pdir.mkdir()
    monkeypatch.setattr(profiles, "PROFILES_DIR", pdir)
    monkeypatch.setattr(profiles, "_update_symlinks", lambda d: None)
    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.setattr(profiles, "get_current_user_id", lambda: LOCAL_USER_ID)
    slug = profiles.create_profile("Jane Doe")
    return slug


def _config_path(slug):
    return profiles.safe_profile_dir(slug) / "config.yaml"


# ── defaults ──────────────────────────────────────────────────────────────────

def test_defaults():
    cfg = BuildCvConfig()
    assert cfg.experience_positioning == "balanced"
    assert cfg.additional_instructions == ""
    assert cfg.resume_template_id == "us"


def test_missing_file_loads_defaults(temp_profile):
    # create_profile writes a config.yaml without a build_cv: key
    cfg = BuildCvConfig.load(temp_profile)
    assert cfg.experience_positioning == "balanced"
    assert cfg.additional_instructions == ""
    assert cfg.resume_template_id == "us"


def test_missing_build_cv_key_loads_defaults(temp_profile):
    _config_path(temp_profile).write_text("searches: []\nblacklist: []\n")
    cfg = BuildCvConfig.load(temp_profile)
    assert cfg.experience_positioning == "balanced"


# ── round-trip ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", ["conservative", "balanced", "aggressive"])
def test_round_trip(temp_profile, level):
    BuildCvConfig(experience_positioning=level, additional_instructions="focus on X", resume_template_id="eu").save(temp_profile)
    cfg = BuildCvConfig.load(temp_profile)
    assert cfg.experience_positioning == level
    assert cfg.additional_instructions == "focus on X"
    assert cfg.resume_template_id == "eu"


# ── validation / forward-compat ─────────────────────────────────────────────

def test_invalid_enum_falls_back_to_balanced(temp_profile):
    _config_path(temp_profile).write_text(
        yaml.dump({"build_cv": {"experience_positioning": "nuclear"}}))
    assert BuildCvConfig.load(temp_profile).experience_positioning == "balanced"


def test_unknown_keys_ignored(temp_profile):
    _config_path(temp_profile).write_text(
        yaml.dump({"build_cv": {"experience_positioning": "conservative", "future_dial": 7}}))
    cfg = BuildCvConfig.load(temp_profile)
    assert cfg.experience_positioning == "conservative"


def test_instructions_clamped(temp_profile):
    long = "x" * (MAX_INSTRUCTIONS_LEN + 200)
    BuildCvConfig(additional_instructions=long).save(temp_profile)
    assert len(BuildCvConfig.load(temp_profile).additional_instructions) == MAX_INSTRUCTIONS_LEN


def test_non_string_instructions_coerced(temp_profile):
    _config_path(temp_profile).write_text(
        yaml.dump({"build_cv": {"experience_positioning": "balanced", "additional_instructions": 123}}))
    assert BuildCvConfig.load(temp_profile).additional_instructions == ""


def test_invalid_template_falls_back_to_default(temp_profile):
    _config_path(temp_profile).write_text(
        yaml.dump({"build_cv": {"experience_positioning": "balanced", "resume_template_id": "moon"}}))
    assert BuildCvConfig.load(temp_profile).resume_template_id == "us"


# ── read-modify-write guarantee (the §5 clobber bug regression) ───────────────

def test_save_preserves_other_config_keys(temp_profile):
    path = _config_path(temp_profile)
    path.write_text(yaml.dump({
        "searches": [{"name": "s1", "query": "eng"}],
        "blacklist": ["intern"],
        "company_blacklist": ["BadCo"],
        "title_filter": ["senior"],
    }))
    BuildCvConfig(experience_positioning="aggressive").save(temp_profile)
    data = yaml.safe_load(path.read_text())
    assert data["searches"] == [{"name": "s1", "query": "eng"}]
    assert data["blacklist"] == ["intern"]
    assert data["company_blacklist"] == ["BadCo"]
    assert data["title_filter"] == ["senior"]
    assert data["build_cv"]["experience_positioning"] == "aggressive"
    assert data["build_cv"]["resume_template_id"] == "us"


# ── stance block composition ─────────────────────────────────────────────────

def test_stance_blocks_are_distinguishable():
    blocks = {lvl: BuildCvConfig(experience_positioning=lvl).to_stance_block()
              for lvl in ("conservative", "balanced", "aggressive")}
    assert len({blocks["conservative"], blocks["balanced"], blocks["aggressive"]}) == 3
    # Conservative forbids transferable framing; balanced/aggressive invite it.
    assert "only skills and terminology" in blocks["conservative"].lower()
    assert "transferable" in blocks["balanced"].lower()
    assert "reach further" in blocks["aggressive"].lower()


def test_stance_block_carries_immutable_boundary():
    for lvl in ("conservative", "balanced", "aggressive"):
        block = BuildCvConfig(experience_positioning=lvl).to_stance_block()
        assert "never becomes a direct claim" in block or "never becomes a direct claim." in block
        assert "framing only" in block.lower()


def test_additional_instructions_wrapped_with_non_override_guard():
    block = BuildCvConfig(additional_instructions="Emphasize roadmap ownership.").to_stance_block()
    assert "Emphasize roadmap ownership." in block
    assert "remain fully in effect" in block


def test_no_instructions_block_when_empty():
    block = BuildCvConfig(additional_instructions="").to_stance_block()
    assert "User emphasis guidance" not in block
