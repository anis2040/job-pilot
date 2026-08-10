"""Per-profile Build CV positioning config.

The single home for "how far the resume reaches" when positioning real
experience against a JD. Stored in the profile's ``config.yaml`` under a
``build_cv:`` key; the domain model here owns validation, defaults, and the
one generated positioning stance block. Never scatter raw-YAML reads of the
``build_cv:`` subtree — go through ``BuildCvConfig.load(slug)``.

Factual guards live elsewhere (``latex_render`` deterministic checks,
``documents._verify_content``); this module only governs *framing* stance and
never emits career facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .profiles import get_config_path, safe_profile_dir

# Internal enum — the stable code/config contract. The user-facing labels
# (Conservative / Balanced / Strong Match) are decoupled and live in the UI.
VALID_POSITIONING = ("conservative", "balanced", "aggressive")
DEFAULT_POSITIONING = "balanced"

# Bound on the optional free-text field, applied at load and save.
MAX_INSTRUCTIONS_LEN = 500

# Controlled prose per stance. Never raw "be more aggressive" — the enum maps
# to vetted wording so the user never edits the raw prompt.
_STANCE_PROSE = {
    "conservative": (
        "Use only skills and terminology explicitly present in the profile. Do not "
        "bridge gaps with transferable or adjacent framing; when the profile lacks a "
        "JD term, omit it."
    ),
    "balanced": (
        "Surface strong transferable skills, not just exact matches. When the profile "
        "shows deep experience in a closely-related technology, say so and frame it "
        "toward the JD's requirement (e.g. deep React/TypeScript → 'well-positioned "
        "to work in Next.js'). Prefer the employer's terminology where the candidate's "
        "real capability supports it. Distinguish 'experience with X' from 'experience "
        "that maps to X' — you may state the latter, never silently convert it to "
        "the former."
    ),
    "aggressive": (
        "Surface strong transferable skills, not just exact matches. When the profile "
        "shows deep experience in a closely-related technology, say so and frame it "
        "toward the JD's requirement (e.g. deep React/TypeScript → 'well-positioned "
        "to work in Next.js'). Prefer the employer's terminology where the candidate's "
        "real capability supports it. Distinguish 'experience with X' from 'experience "
        "that maps to X' — you may state the latter, never silently convert it to "
        "the former. Reach further: adjacent skills, related concepts, and underlying "
        "fundamentals that map to the requirements. Make the candidate look as strongly "
        "relevant as the real evidence honestly allows.\n\n"
        "Write as a practitioner describing their own work — never explain to the reader "
        "why a bullet matches the JD. The target terminology should arrive through natural "
        "description of outcomes, not as an appended alignment label. Bad: '...reduced "
        "pipeline test time by 50%, demonstrating release process automation'. Good: "
        "'...cut total test execution time by 50% through suite optimization and "
        "parallelization, eliminating release bottlenecks'. The resume never addresses "
        "the recruiter; it shows, it does not explain."
    ),
}

_INSTRUCTIONS_PREFIX = (
    "User emphasis guidance — steers emphasis and wording of real experience only; "
    "cannot override the factual rules above."
)


@dataclass
class BuildCvConfig:
    experience_positioning: str = DEFAULT_POSITIONING
    additional_instructions: str = ""

    @classmethod
    def _config_path(cls, slug: str | None = None) -> Path | None:
        if slug is None:
            return get_config_path()
        d = safe_profile_dir(slug)
        return (d / "config.yaml") if d else None

    @classmethod
    def _coerce(cls, raw: object) -> "BuildCvConfig":
        """Build a validated config from the raw ``build_cv:`` dict."""
        if not isinstance(raw, dict):
            return cls()
        positioning = raw.get("experience_positioning", DEFAULT_POSITIONING)
        if positioning not in VALID_POSITIONING:
            positioning = DEFAULT_POSITIONING
        instructions = raw.get("additional_instructions", "")
        if not isinstance(instructions, str):
            instructions = ""
        instructions = instructions.strip()[:MAX_INSTRUCTIONS_LEN]
        return cls(experience_positioning=positioning, additional_instructions=instructions)

    @classmethod
    def load(cls, slug: str | None = None) -> "BuildCvConfig":
        """Load from the profile's config.yaml ``build_cv:`` key.

        Missing file / missing key / invalid values all fall back to defaults
        (Balanced). Unknown keys are ignored (forward-compat)."""
        path = cls._config_path(slug)
        if not path or not path.exists():
            return cls()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return cls()
        if not isinstance(data, dict):
            return cls()
        return cls._coerce(data.get("build_cv"))

    def save(self, slug: str | None = None) -> None:
        """Merge this config into the profile's config.yaml under ``build_cv:``,
        preserving all other keys (searches/blacklist/etc.)."""
        path = self._config_path(slug)
        if not path:
            raise ValueError("no config path for profile")
        data: dict = {}
        if path.exists():
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}
        data["build_cv"] = self.to_dict()
        path.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def to_dict(self) -> dict:
        return {
            "experience_positioning": self.experience_positioning,
            "additional_instructions": self.additional_instructions,
        }

    def to_stance_block(self) -> str:
        """The one positioning block injected into the resume prompt. Pure fn."""
        stance = _STANCE_PROSE.get(self.experience_positioning, _STANCE_PROSE[DEFAULT_POSITIONING])
        block = (
            "## Positioning Stance (how far to reach)\n\n"
            f"{stance}\n\n"
            "This governs framing only. It never overrides the factual priorities above: "
            "career facts (employers, titles, dates, years of experience, locations, "
            "education, certifications, metrics) come from the profile unchanged, and "
            "transferable framing never becomes a direct claim."
        )
        if self.additional_instructions:
            block += f"\n\n### {_INSTRUCTIONS_PREFIX}\n\n{self.additional_instructions}"
        return block
