"""Tests for AI provider/model configuration logic in job.ai_providers.

All offline — no API keys, no network. Env vars are patched per-test.
"""
import pytest

import job.ai_providers as w


@pytest.fixture(autouse=True)
def _isolate_user_env(monkeypatch):
    """Neutralize the per-user .env read so only monkeypatched os.environ counts.

    _env_get() resolves task overrides → per-user profiles/<user>/.env → os.environ.
    On a dev machine the real user .env (e.g. PREFERRED_PROVIDER=gemini) would shadow
    monkeypatch.setenv/delenv on os.environ, making these offline tests non-deterministic.
    """
    import job.user_env as ue
    monkeypatch.setattr(ue, "read_user_env", lambda *a, **k: {})


class TestModelDefaults:
    def test_every_default_is_in_its_model_list(self):
        """Regression: the default model for each provider must be a member of that
        provider's model list. A stale default (e.g. a retired Gemini model) is
        exactly what silently broke Gemini builds."""
        lists = {
            "groq": w._GROQ_MODELS,
            "anthropic": w._ANTHROPIC_MODELS,
            "gemini": w._GEMINI_MODELS,
            "openrouter": w._OPENROUTER_MODELS,
        }
        for provider, default in w._MODEL_DEFAULTS.items():
            assert default in lists[provider], (
                f"{provider} default '{default}' is not in its model list {lists[provider]}"
            )

    def test_all_three_providers_have_defaults(self):
        assert set(w._MODEL_DEFAULTS) == {"groq", "anthropic", "gemini", "openrouter"}

    def test_model_lists_nonempty(self):
        assert w._GROQ_MODELS and w._ANTHROPIC_MODELS and w._GEMINI_MODELS and w._OPENROUTER_MODELS


class TestGetModel:
    @pytest.fixture(autouse=True)
    def _no_env_reload(self, monkeypatch):
        # _get_model calls _load_env(), which re-reads the real .env and would
        # clobber per-test env patches. Neutralize it for isolation.
        monkeypatch.setattr(w, "_load_env", lambda: None)

    def test_falls_back_to_default(self, monkeypatch):
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        assert w._get_model("groq") == w._MODEL_DEFAULTS["groq"]

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-xyz")
        assert w._get_model("gemini") == "gemini-custom-xyz"

    def test_blank_env_uses_default(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "   ")
        assert w._get_model("anthropic") == w._MODEL_DEFAULTS["anthropic"]


class TestOpenRouterFreeFilter:
    """Free models come from families outside the flagship allowlist (nvidia/,
    inclusionai/, cohere/, …), so _is_openrouter_free_model must NOT prune by
    family — otherwise most of OpenRouter's ~17 free models never surface."""

    def _model(self, mid, prompt="0", completion="0", in_mods=None, out_mods=None):
        return {
            "id": mid,
            "pricing": {"prompt": prompt, "completion": completion},
            "architecture": {
                "input_modalities": in_mods or ["text"],
                "output_modalities": out_mods or ["text"],
            },
        }

    def test_keeps_free_model_from_non_flagship_family(self):
        m = self._model("nvidia/nemotron-3-super-120b-a12b:free")
        # It would be rejected by the flagship filter (nvidia/ isn't a flagship family)...
        assert w._is_openrouter_flagship(m) is False
        # ...but the free filter keeps it.
        assert w._is_openrouter_free_model(m) is True

    def test_rejects_paid_model(self):
        m = self._model("anthropic/claude-sonnet-4.5", prompt="0.003", completion="0.015")
        assert w._is_openrouter_free_model(m) is False

    def test_rejects_free_but_junk_model(self):
        # content-safety classifier and vision/omni variants are excluded even when free
        for mid in ("nvidia/nemotron-3.5-content-safety:free",
                    "nvidia/nemotron-nano-12b-v2-vl:free",
                    "openrouter/free"):
            assert w._is_openrouter_free_model(self._model(mid)) is False, mid

    def test_default_free_model_passes(self):
        default = w._MODEL_DEFAULTS["openrouter"]
        assert default.endswith(":free")
        assert w._is_openrouter_free_model(self._model(default)) is True


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
        monkeypatch.setattr(w, "_get_openrouter_client", lambda: object() if "openrouter" in available else None)
        monkeypatch.setattr(w, "_build_with_groq", lambda s, u, stage_fn=None: "GROQ")
        monkeypatch.setattr(w, "_build_with_sdk", lambda s, u, stage_fn=None: "ANTHROPIC")
        monkeypatch.setattr(w, "_build_with_gemini", lambda s, u, cwd, stage_fn=None: "GEMINI")
        monkeypatch.setattr(w, "_build_with_openrouter", lambda s, u, stage_fn=None: "OPENROUTER")
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

    def test_preferred_openrouter_wins(self, monkeypatch):
        monkeypatch.setenv("PREFERRED_PROVIDER", "openrouter")
        self._stub_builders(monkeypatch, available={"groq", "anthropic", "gemini", "openrouter"})
        assert w._generate_content("s", "u", cwd=".") == "OPENROUTER"

    def test_openrouter_available_but_not_preferred_stays_default(self, monkeypatch):
        # openrouter is NOT in the default fallback lead — groq should still win.
        monkeypatch.delenv("PREFERRED_PROVIDER", raising=False)
        self._stub_builders(monkeypatch, available={"groq", "openrouter"})
        assert w._generate_content("s", "u", cwd=".") == "GROQ"

    def test_no_provider_raises(self, monkeypatch):
        monkeypatch.delenv("PREFERRED_PROVIDER", raising=False)
        self._stub_builders(monkeypatch, available=set())
        # shutil.which("gemini") could still find a CLI; force it off
        monkeypatch.setattr(w.shutil, "which", lambda _: None)
        with pytest.raises(RuntimeError, match="No AI provider"):
            w._generate_content("s", "u", cwd=".")
