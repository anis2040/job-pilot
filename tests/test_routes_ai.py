"""Flask route tests via app.test_client().

Fully offline: the AI SDK clients and live model-listing are stubbed, and
web.BASE is redirected to a temp dir so tests never touch the real .env.
"""
import json
import pytest

import web
import job.web_api as wapi


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with an isolated temp .env and stubbed AI backends."""
    # Redirect all .env writes/reads to a temp file — both the web.py routes
    # (web.BASE) and web_api._load_env (web_api._BASE) must point at tmp_path,
    # otherwise _load_env() re-reads the real project .env and repopulates keys.
    monkeypatch.setattr(web, "BASE", tmp_path)
    monkeypatch.setattr(wapi, "_BASE", tmp_path)

    # No real provider clients / no network model listing
    monkeypatch.setattr(web, "_get_groq_client", lambda: None)
    monkeypatch.setattr(web, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(web, "_get_gemini_client", lambda: None)
    monkeypatch.setattr(web, "shutil", web.shutil)  # keep shutil, but which() below
    monkeypatch.setattr(web.shutil, "which", lambda name: None)
    # _list_models falls back to static lists when clients are None; force that path
    monkeypatch.setattr(web, "_list_models", lambda provider: {
        "groq": wapi._GROQ_MODELS,
        "anthropic": wapi._ANTHROPIC_MODELS,
        "gemini": wapi._GEMINI_MODELS,
    }[provider])

    # Clean provider-related env so tests are deterministic
    for k in ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "GEMINI_API_KEY", "GOOGLE_API_KEY", "PREFERRED_PROVIDER",
              "GROQ_MODEL", "ANTHROPIC_MODEL", "GEMINI_MODEL"):
        monkeypatch.delenv(k, raising=False)

    web.app.config["TESTING"] = True
    return web.app.test_client()


class TestAiSettingsGet:
    def test_shape(self, client):
        r = client.get("/api/ai-settings")
        assert r.status_code == 200
        data = r.get_json()
        assert set(data) >= {"active_provider", "preferred_provider", "providers"}
        assert set(data["providers"]) == {"groq", "anthropic", "gemini"}
        for p in data["providers"].values():
            assert set(p) >= {"configured", "model", "key_set", "models"}

    def test_no_keys_means_no_active(self, client):
        data = client.get("/api/ai-settings").get_json()
        assert data["active_provider"] is None
        assert all(not p["key_set"] for p in data["providers"].values())

    def test_current_model_always_in_list(self, client, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-not-listed")
        data = client.get("/api/ai-settings").get_json()
        assert "gemini-custom-not-listed" in data["providers"]["gemini"]["models"]


class TestAiSettingsSave:
    def test_saves_models_and_preferred(self, client, tmp_path):
        r = client.post("/api/ai-settings", json={
            "groq_model": "llama-3.1-8b-instant",
            "preferred_provider": "groq",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        env_text = (tmp_path / ".env").read_text()
        assert "GROQ_MODEL=llama-3.1-8b-instant" in env_text
        assert "PREFERRED_PROVIDER=groq" in env_text

    def test_clearing_preferred_removes_it(self, client, tmp_path):
        client.post("/api/ai-settings", json={"preferred_provider": "gemini"})
        assert "PREFERRED_PROVIDER=gemini" in (tmp_path / ".env").read_text()
        client.post("/api/ai-settings", json={"preferred_provider": ""})
        assert "PREFERRED_PROVIDER=" not in (tmp_path / ".env").read_text()

    def test_invalid_preferred_ignored(self, client, tmp_path):
        r = client.post("/api/ai-settings", json={"preferred_provider": "bogus"})
        assert r.status_code == 200
        # bogus value must not be written
        env_text = (tmp_path / ".env").read_text() if (tmp_path / ".env").exists() else ""
        assert "bogus" not in env_text

    def test_does_not_duplicate_keys(self, client, tmp_path):
        client.post("/api/ai-settings", json={"groq_model": "a"})
        client.post("/api/ai-settings", json={"groq_model": "b"})
        env_text = (tmp_path / ".env").read_text()
        assert env_text.count("GROQ_MODEL=") == 1
        assert "GROQ_MODEL=b" in env_text


class TestSaveKeys:
    @pytest.mark.parametrize("endpoint,env_key", [
        ("/api/setup/save-groq-key", "GROQ_API_KEY"),
        ("/api/setup/save-gemini-key", "GEMINI_API_KEY"),
        ("/api/setup/save-anthropic-key", "ANTHROPIC_API_KEY"),
    ])
    def test_save_key_writes_env(self, client, tmp_path, endpoint, env_key):
        r = client.post(endpoint, json={"key": "test-secret-123"})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        assert f"{env_key}=test-secret-123" in (tmp_path / ".env").read_text()

    def test_empty_key_rejected(self, client):
        r = client.post("/api/setup/save-groq-key", json={"key": ""})
        assert r.status_code == 400


class TestAiSettingsTest:
    def test_unknown_provider(self, client):
        r = client.post("/api/ai-settings/test", json={"provider": "bogus"})
        assert r.status_code == 400

    def test_provider_error_returns_ok_false(self, client, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("no key configured")
        monkeypatch.setattr(web, "_build_with_groq", boom)
        r = client.post("/api/ai-settings/test", json={"provider": "groq"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is False
        assert "no key configured" in data["error"]

    def test_success_reports_latency(self, client, monkeypatch):
        monkeypatch.setattr(web, "_build_with_groq", lambda s, u: "OK")
        monkeypatch.setattr(web, "_get_model", lambda p: "llama-3.3-70b-versatile")
        r = client.post("/api/ai-settings/test", json={"provider": "groq"})
        data = r.get_json()
        assert data["ok"] is True
        assert data["model"] == "llama-3.3-70b-versatile"
        assert isinstance(data["latency_ms"], int)
