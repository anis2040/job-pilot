"""Tests for AI provider/model configuration logic in job.ai_providers.

All offline — no API keys, no network. Env vars are patched per-test.
"""
import pytest

import job.ai_providers as w


class TestModelDefaults:
    def test_every_default_is_in_its_model_list(self):
        """Regression: the default model for each provider must be a member of that
        provider's model list. A stale default (e.g. a retired Gemini model) is
        exactly what silently broke Gemini builds."""
        lists = {
            "groq": w._GROQ_MODELS,
            "anthropic": w._ANTHROPIC_MODELS,
            "gemini": w._GEMINI_MODELS,
        }
        for provider, default in w._MODEL_DEFAULTS.items():
            assert default in lists[provider], (
                f"{provider} default '{default}' is not in its model list {lists[provider]}"
            )

    def test_all_three_providers_have_defaults(self):
        assert set(w._MODEL_DEFAULTS) == {"groq", "anthropic", "gemini"}

    def test_model_lists_nonempty(self):
        assert w._GROQ_MODELS and w._ANTHROPIC_MODELS and w._GEMINI_MODELS


class TestGetModel:
    def test_falls_back_to_default(self, monkeypatch):
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        assert w._get_model("groq") == w._MODEL_DEFAULTS["groq"]

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-xyz")
        assert w._get_model("gemini") == "gemini-custom-xyz"

    def test_blank_env_uses_default(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "   ")
        assert w._get_model("anthropic") == w._MODEL_DEFAULTS["anthropic"]


class TestGeminiTextModelFilter:
    @pytest.mark.parametrize("name", [
        "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.0-flash",
        "gemini-flash-latest", "gemma-4-31b-it",
    ])
    def test_keeps_text_models(self, name):
        assert w._is_gemini_text_model(name) is True

    @pytest.mark.parametrize("name", [
        "gemini-3.5-flash-image", "gemini-2.5-flash-preview-tts",
        "gemini-robotics-er-1.5-preview", "gemini-embedding-001",
        "gemini-2.5-computer-use-preview", "lyria-3-pro-preview",
        "nano-banana-pro-preview", "gemini-omni-flash-preview",
        "deep-research-max-preview", "some-other-model",
    ])
    def test_drops_non_text_models(self, name):
        assert w._is_gemini_text_model(name) is False


class TestProviderFallbackOrder:
    """_generate_content should honor PREFERRED_PROVIDER, then fall back."""

    def _stub_builders(self, monkeypatch, available):
        """Make each provider's client available/unavailable and stub its builder
        to return a marker string, so we can assert which one ran.

        Note: gemini is considered available if its client exists OR the `gemini`
        CLI is on PATH, so we also force shutil.which off unless gemini is wanted.
        """
        monkeypatch.setattr(w, "_get_groq_client", lambda: object() if "groq" in available else None)
        monkeypatch.setattr(w, "_get_anthropic_client", lambda: object() if "anthropic" in available else None)
        monkeypatch.setattr(w, "_get_gemini_client", lambda: object() if "gemini" in available else None)
        monkeypatch.setattr(w, "_build_with_groq", lambda s, u, stage_fn=None: "GROQ")
        monkeypatch.setattr(w, "_build_with_sdk", lambda s, u, stage_fn=None: "ANTHROPIC")
        monkeypatch.setattr(w, "_build_with_gemini", lambda s, u, cwd, stage_fn=None: "GEMINI")
        # The gemini branch also treats a `gemini` CLI on PATH as available.
        # Only let which() find it when gemini is meant to be available.
        monkeypatch.setattr(w.shutil, "which",
                            lambda name: "/usr/bin/gemini" if (name == "gemini" and "gemini" in available) else None)

    def test_default_order_prefers_groq(self, monkeypatch):
        monkeypatch.delenv("PREFERRED_PROVIDER", raising=False)
        self._stub_builders(monkeypatch, available={"groq", "anthropic", "gemini"})
        assert w._generate_content("s", "u", cwd=".") == "GROQ"

    def test_preferred_provider_wins(self, monkeypatch):
        monkeypatch.setenv("PREFERRED_PROVIDER", "gemini")
        self._stub_builders(monkeypatch, available={"groq", "anthropic", "gemini"})
        assert w._generate_content("s", "u", cwd=".") == "GEMINI"

    def test_preferred_unavailable_falls_back(self, monkeypatch):
        monkeypatch.setenv("PREFERRED_PROVIDER", "gemini")
        self._stub_builders(monkeypatch, available={"groq"})  # gemini has no key
        assert w._generate_content("s", "u", cwd=".") == "GROQ"

    def test_no_provider_raises(self, monkeypatch):
        monkeypatch.delenv("PREFERRED_PROVIDER", raising=False)
        self._stub_builders(monkeypatch, available=set())
        # shutil.which("gemini") could still find a CLI; force it off
        monkeypatch.setattr(w.shutil, "which", lambda _: None)
        with pytest.raises(RuntimeError, match="No AI provider"):
            w._generate_content("s", "u", cwd=".")
