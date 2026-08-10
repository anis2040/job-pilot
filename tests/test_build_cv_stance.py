"""Prompt-composition and verifier-mode tests for the Build CV positioning stance.

Per the proposal §12 Option A: the offline stub returns fixed output regardless
of mode, so we cannot assert mode-dependent GENERATION. What we CAN assert
offline and deterministically:
  1. the assembled resume prompt carries the selected stance block, and
  2. the verifier's system prompt is mode-aware while its factual gate stays
     constant across modes.
"""
import json

import pytest

import job.documents as documents
from job.build_cv_config import BuildCvConfig


_PROFILE = "# Jane\n\n## Contact\n- Email: jane@x.com\n"


@pytest.fixture
def profile(tmp_path, monkeypatch):
    p = tmp_path / "profile.md"
    p.write_text(_PROFILE)
    monkeypatch.setattr(documents, "get_profile_path", lambda: p)
    return p


@pytest.mark.parametrize("level,needle", [
    ("conservative", "only skills and terminology"),
    ("balanced", "transferable"),
    ("aggressive", "Reach further"),
])
def test_resume_prompt_carries_stance_block(profile, monkeypatch, level, needle):
    monkeypatch.setattr(documents.BuildCvConfig, "load",
                        classmethod(lambda cls, slug=None: BuildCvConfig(experience_positioning=level)))
    skill_text, _ = documents._build_resume_prompt(
        {"description": "x" * 100, "location": "Berlin", "url": "http://x"},
        "Acme", "Engineer", "Jane_Doe", documents._skill_path())
    assert "Positioning Stance" in skill_text
    assert needle in skill_text


def test_resume_prompt_carries_additional_instructions(profile, monkeypatch):
    monkeypatch.setattr(documents.BuildCvConfig, "load",
                        classmethod(lambda cls, slug=None: BuildCvConfig(
                            experience_positioning="balanced",
                            additional_instructions="Emphasize roadmap ownership.")))
    skill_text, _ = documents._build_resume_prompt(
        {"description": "x" * 100}, "Acme", "Engineer", "Jane_Doe", documents._skill_path())
    assert "Emphasize roadmap ownership." in skill_text
    assert "cannot override the factual rules" in skill_text


# ── verifier is mode-aware but factually constant ────────────────────────────

def _capture_verifier_system(monkeypatch):
    captured = {}

    def fake_run(system, prompt):
        captured["system"] = system
        return None  # None → verifier applies no changes; keeps the build offline

    monkeypatch.setattr(documents, "_run_verifier", fake_run)
    return captured


@pytest.mark.parametrize("mode,tag", [
    ("conservative", "CONSERVATIVE"),
    ("balanced", "BALANCED"),
    ("aggressive", "STRONG-MATCH"),
])
def test_verifier_system_prompt_is_mode_aware(monkeypatch, mode, tag):
    captured = _capture_verifier_system(monkeypatch)
    content = {"summary": "React foundation applicable to Next.js.",
               "experiences": [{"bullets": ["Built things."]}]}
    documents._verify_content(content, _PROFILE, positioning=mode)
    assert tag in captured["system"]


def test_verifier_factual_gate_is_constant_across_modes(monkeypatch):
    """The FACTS gate (fabrication rejection + SCOPE PRECISION) must be byte-identical
    regardless of mode. Only the positioning LATITUDE (how far to reframe) and the
    SUMMARY rule are allowed to vary — those carry the stance; the gate is the floor."""
    systems = {}
    for mode in ("conservative", "balanced", "aggressive"):
        captured = _capture_verifier_system(monkeypatch)
        documents._verify_content(
            {"summary": "s", "experiences": [{"bullets": ["b"]}]}, _PROFILE, positioning=mode)
        systems[mode] = captured["system"]

    # The gate spans from "1) FACTS:" up to the (mode-variable) summary rule "2) SUMMARY".
    def gate(s):
        start = s.index("1) FACTS:")
        end = s.index("2) SUMMARY", start)
        return s[start:end]

    assert gate(systems["conservative"]) == gate(systems["balanced"]) == gate(systems["aggressive"])
    # And the SCOPE PRECISION expertise boundary lives inside that constant gate.
    assert "SCOPE PRECISION" in gate(systems["conservative"])

    # Conversely, the latitude MUST differ: conservative forbids reframing, the others invite it.
    assert "Do NOT reframe terminology" in systems["conservative"]
    assert "Do NOT reframe terminology" not in systems["balanced"]
    assert "Do NOT reframe terminology" not in systems["aggressive"]
    # And the summary rule diverges: conservative preserves the opening, the others rewrite for impact.
    assert "do not rewrite it for impact" in systems["conservative"]
    assert "SUMMARY IMPACT" in systems["balanced"]
    assert "SUMMARY IMPACT" not in systems["conservative"]
