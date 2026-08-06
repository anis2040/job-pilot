"""Flask route tests via app.test_client().

Fully offline: the AI SDK clients and live model-listing are stubbed, and
web.BASE is redirected to a temp dir so tests never touch the real .env.
"""
import concurrent.futures as futures
import io
import json
import pytest

import web
import job.web_api as wapi
import job.paths


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with an isolated temp .env and stubbed AI backends."""
    import job.profiles as profs
    from job.user_context import LOCAL_USER_ID

    # Redirect all .env writes/reads to a temp file. The web.py routes write via
    # web.BASE; ai_providers._load_env reads via job.paths.BASE. Patch both so
    # _load_env() never re-reads the real project .env and repopulates keys.
    monkeypatch.setattr(web, "BASE", tmp_path)
    monkeypatch.setattr(job.paths, "BASE", tmp_path)
    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    pdir = tmp_path / "profiles"
    pdir.mkdir()
    monkeypatch.setattr(profs, "PROFILES_DIR", pdir)
    monkeypatch.setattr(profs, "get_current_user_id", lambda: LOCAL_USER_ID)
    monkeypatch.setattr(profs, "_update_symlinks", lambda d: None)
    (pdir / LOCAL_USER_ID).mkdir()

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


def _user_env(tmp_path):
    from job.user_context import LOCAL_USER_ID
    return tmp_path / "profiles" / LOCAL_USER_ID / ".env"


class TestAiSettingsGet:
    def test_shape(self, client):
        r = client.get("/api/ai-settings")
        assert r.status_code == 200
        data = r.get_json()
        assert set(data) >= {"active_provider", "preferred_provider", "providers"}
        # claude (Pro CLI) was added after the initial test; ensure the three
        # API-key providers are present and claude is allowed but not required.
        assert {"groq", "anthropic", "gemini"} <= set(data["providers"])
        for p in data["providers"].values():
            assert set(p) >= {"configured", "model", "key_set", "models"}

    def test_usage_block_present(self, client):
        data = client.get("/api/ai-settings").get_json()
        # claude (Pro CLI) has no usage block — it doesn't use an API key.
        api_key_providers = {n: p for n, p in data["providers"].items() if n != "claude"}
        for name, p in api_key_providers.items():
            assert "usage" in p, f"{name} missing usage block"
            u = p["usage"]
            assert set(u) >= {"last_24h_tokens", "today_tokens", "limit_tpd", "approx", "resets"}
            assert isinstance(u["last_24h_tokens"], int)
        # Groq limits are exact; Gemini/Anthropic are approximate.
        assert data["providers"]["groq"]["usage"]["approx"] is False
        assert data["providers"]["gemini"]["usage"]["approx"] is True

    def test_no_keys_means_no_active(self, client):
        data = client.get("/api/ai-settings").get_json()
        assert data["active_provider"] is None
        assert all(not p["key_set"] for p in data["providers"].values())

    def test_current_model_always_in_list(self, client, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-not-listed")
        data = client.get("/api/ai-settings").get_json()
        assert "gemini-custom-not-listed" in data["providers"]["gemini"]["models"]

    def test_semantic_match_fields_present(self, client):
        data = client.get("/api/ai-settings").get_json()
        assert "semantic_match" in data
        assert "embeddings_available" in data
        assert isinstance(data["semantic_match"], bool)


class TestAiSettingsSave:
    def test_saves_models_and_preferred(self, client, tmp_path):
        r = client.post("/api/ai-settings", json={
            "groq_model": "llama-3.1-8b-instant",
            "preferred_provider": "groq",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        env_text = _user_env(tmp_path).read_text()
        assert "GROQ_MODEL=llama-3.1-8b-instant" in env_text
        assert "PREFERRED_PROVIDER=groq" in env_text

    def test_saving_gemini_model_does_not_write_groq_model(self, client, tmp_path):
        r = client.post("/api/ai-settings", json={
            "gemini_model": "gemini-3.5-flash",
            "preferred_provider": "gemini",
        })

        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "GEMINI_MODEL" in data["updated"]
        assert "GROQ_MODEL" not in data["updated"]
        env_text = _user_env(tmp_path).read_text()
        assert "GEMINI_MODEL=gemini-3.5-flash" in env_text
        assert "PREFERRED_PROVIDER=gemini" in env_text
        assert "GROQ_MODEL=" not in env_text

    def test_selecting_claude_api_defaults_to_cheapest_model(self, client, tmp_path):
        r = client.post("/api/ai-settings", json={
            "preferred_provider": "anthropic",
        })

        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "ANTHROPIC_MODEL" in data["updated"]
        env_text = _user_env(tmp_path).read_text()
        assert "ANTHROPIC_MODEL=claude-haiku-4-5" in env_text
        assert "PREFERRED_PROVIDER=anthropic" in env_text

    def test_clearing_preferred_removes_it(self, client, tmp_path):
        client.post("/api/ai-settings", json={"preferred_provider": "gemini"})
        assert "PREFERRED_PROVIDER=gemini" in _user_env(tmp_path).read_text()
        client.post("/api/ai-settings", json={"preferred_provider": ""})
        assert "PREFERRED_PROVIDER=" not in _user_env(tmp_path).read_text()

    def test_semantic_match_persists(self, client, tmp_path):
        client.post("/api/ai-settings", json={"semantic_match": False})
        assert "SEMANTIC_MATCH=off" in _user_env(tmp_path).read_text()
        assert client.get("/api/ai-settings").get_json()["semantic_match"] is False
        client.post("/api/ai-settings", json={"semantic_match": True})
        assert "SEMANTIC_MATCH=on" in _user_env(tmp_path).read_text()

    def test_invalid_preferred_ignored(self, client, tmp_path):
        r = client.post("/api/ai-settings", json={"preferred_provider": "bogus"})
        assert r.status_code == 200
        # bogus value must not be written
        env_path = _user_env(tmp_path)
        env_text = env_path.read_text() if env_path.exists() else ""
        assert "bogus" not in env_text

    def test_does_not_duplicate_keys(self, client, tmp_path):
        client.post("/api/ai-settings", json={"groq_model": "a"})
        client.post("/api/ai-settings", json={"groq_model": "b"})
        env_text = _user_env(tmp_path).read_text()
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
        assert f"{env_key}=test-secret-123" in _user_env(tmp_path).read_text()

    def test_empty_key_rejected(self, client):
        r = client.post("/api/setup/save-groq-key", json={"key": ""})
        assert r.status_code == 400


class TestAiSettingsTest:
    def test_unknown_provider(self, client):
        r = client.post("/api/ai-settings/test", json={"provider": "bogus"})
        assert r.status_code == 400

    def test_provider_error_returns_ok_false(self, client, monkeypatch):
        # Key present (passes the precheck) but the call itself raises
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        def boom(*a, **k):
            raise RuntimeError("no key configured")
        monkeypatch.setattr(web, "_build_with_groq", boom)
        r = client.post("/api/ai-settings/test", json={"provider": "groq"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is False
        assert "no key configured" in data["error"]

    def test_success_reports_latency(self, client, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        monkeypatch.setattr(web, "_build_with_groq", lambda s, u: "OK")
        monkeypatch.setattr(web, "_get_model", lambda p: "llama-3.3-70b-versatile")
        r = client.post("/api/ai-settings/test", json={"provider": "groq"})
        data = r.get_json()
        assert data["ok"] is True
        assert data["model"] == "llama-3.3-70b-versatile"
        assert isinstance(data["latency_ms"], int)


class TestSetupParseResume:
    def test_timeout_returns_504(self, client, monkeypatch):
        monkeypatch.setattr(web, "call_ai", lambda prompt: (_ for _ in ()).throw(futures.TimeoutError()))

        data = {
            "file": (io.BytesIO(b"Example resume text"), "resume.txt"),
        }
        r = client.post("/api/setup/parse-resume", data=data, content_type="multipart/form-data")

        assert r.status_code == 504
        assert r.get_json()["error"] == "AI extraction timed out. Try again."
