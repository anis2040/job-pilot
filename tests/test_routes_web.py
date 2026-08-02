"""Smoke tests for Flask routes not covered by test_routes_ai.py.

Covers: /api/jobs, /api/job-status, /api/profiles, /api/fetch-status,
        /api/setup/status, and /api/config.

All tests run fully offline — no network, no AI keys, no pdflatex.
The web_client fixture creates an isolated profile + SQLite database and stubs
every AI client and external tool the same way test_routes_ai.py does.
"""
import sqlite3
import pytest

import web
import job.paths
import job.profiles as profs
import job.db as db
import job.web_api as wapi


def _sqlite_row_conn(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


@pytest.fixture
def web_client(tmp_path, monkeypatch):
    # Isolate .env / BASE paths
    monkeypatch.setattr(web, "BASE", tmp_path)
    monkeypatch.setattr(job.paths, "BASE", tmp_path)

    # Isolate profile filesystem
    pdir = tmp_path / "profiles"
    pdir.mkdir()
    monkeypatch.setattr(profs, "PROFILES_DIR", pdir)
    monkeypatch.setattr(profs, "ACTIVE_FILE", pdir / ".active")
    monkeypatch.setattr(profs, "_update_symlinks", lambda d: None)
    # web.py imports PROFILES_DIR directly into its own namespace
    monkeypatch.setattr(web, "PROFILES_DIR", pdir)

    # Create a test profile and activate it
    profile_dir = pdir / "test-user"
    profile_dir.mkdir()
    (profile_dir / "profile.md").write_text("# Test User\nSoftware Engineer")
    (profile_dir / "config.yaml").write_text(
        "searches:\n"
        "  - name: t\n"
        "    source: greenhouse\n"
        "    query: engineer\n"
        "    location: United States\n"
    )
    (pdir / ".active").write_text("test-user")

    # Isolate SQLite to the temp profile dir
    db_file = profile_dir / "state.db"
    monkeypatch.setattr(db, "_connect", lambda: _sqlite_row_conn(db_file))
    db.init_db()

    # Stub AI clients and external tools
    monkeypatch.setattr(web, "_get_groq_client", lambda: None)
    monkeypatch.setattr(web, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(web, "_get_gemini_client", lambda: None)
    monkeypatch.setattr(web.shutil, "which", lambda _: None)
    monkeypatch.setattr(web, "_list_models", lambda p: {
        "groq": wapi._GROQ_MODELS,
        "anthropic": wapi._ANTHROPIC_MODELS,
        "gemini": wapi._GEMINI_MODELS,
    }[p])

    for k in ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "GEMINI_API_KEY", "GOOGLE_API_KEY", "PREFERRED_PROVIDER"):
        monkeypatch.delenv(k, raising=False)

    web.app.config["TESTING"] = True
    return web.app.test_client()


def _insert_job(job_id="job_001", title="Software Engineer", company="Acme", status="pending"):
    db.insert_job(
        job_id=job_id,
        url="https://example.com/job/1",
        title=title,
        company=company,
        location="Remote",
        remote="Remote",
        experience="",
        description="",
        posted_at=None,
        search_name="t",
    )
    if status != "pending":
        db.update_status(job_id, status)


# ── /api/jobs ─────────────────────────────────────────────────────────────────

class TestApiJobs:
    def test_returns_list_when_empty(self, web_client):
        r = web_client.get("/api/jobs")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_returns_pending_jobs(self, web_client):
        _insert_job("j1", title="ML Engineer")
        r = web_client.get("/api/jobs")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "ML Engineer"

    def test_filters_by_status(self, web_client):
        _insert_job("j1", status="applied")
        _insert_job("j2", status="pending")
        r = web_client.get("/api/jobs?status=applied")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["job_id"] == "j1"


# ── /api/job-status ───────────────────────────────────────────────────────────

class TestApiJobStatus:
    def test_update_to_applied(self, web_client):
        _insert_job("j1")
        r = web_client.post("/api/job-status/j1/applied")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        assert db.get_job("j1")["status"] == "applied"

    def test_update_to_skipped(self, web_client):
        _insert_job("j2")
        r = web_client.post("/api/job-status/j2/skipped")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_invalid_status_returns_400(self, web_client):
        _insert_job("j3")
        r = web_client.post("/api/job-status/j3/bogus")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_missing_job_returns_ok_false(self, web_client):
        r = web_client.post("/api/job-status/no_such_id/applied")
        assert r.status_code == 200
        assert r.get_json()["ok"] is False


# ── /api/profiles ─────────────────────────────────────────────────────────────

class TestApiProfiles:
    def test_list_includes_test_profile(self, web_client):
        r = web_client.get("/api/profiles")
        assert r.status_code == 200
        slugs = [p["slug"] for p in r.get_json()["profiles"]]
        assert "test-user" in slugs

    def test_active_returns_current_profile(self, web_client):
        r = web_client.get("/api/profiles/active")
        assert r.status_code == 200
        data = r.get_json()
        assert data["active"]["slug"] == "test-user"


# ── /api/fetch-status ─────────────────────────────────────────────────────────

def test_fetch_status_shape(web_client):
    r = web_client.get("/api/fetch-status")
    assert r.status_code == 200
    data = r.get_json()
    assert "status" in data


# ── /api/setup/status ─────────────────────────────────────────────────────────

def test_setup_status_booleans(web_client):
    r = web_client.get("/api/setup/status")
    assert r.status_code == 200
    data = r.get_json()
    for key in ("has_claude", "has_gemini", "has_pdflatex", "has_node",
                "has_profile", "gemini_key_set", "groq_key_set"):
        assert isinstance(data[key], bool), f"{key} should be bool"


# ── /api/config ───────────────────────────────────────────────────────────────

class TestApiConfig:
    def test_get_returns_searches(self, web_client):
        r = web_client.get("/api/config")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data["searches"], list)
        assert len(data["searches"]) >= 1

    def test_post_empty_body_returns_400(self, web_client):
        r = web_client.post("/api/config", json={})
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_post_saves_config(self, web_client):
        payload = {
            "searches": [
                {"name": "gh-eng", "source": "greenhouse",
                 "query": "engineer", "location": "United States"}
            ],
            "title_filter": [],
            "blacklist": [],
            "company_blacklist": [],
        }
        r = web_client.post("/api/config", json=payload)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


# ── /api/sources ──────────────────────────────────────────────────────────────

def test_api_sources_returns_list(web_client):
    from job.fetcher import SOURCES
    r = web_client.get("/api/sources")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert data == [src for src, _ in SOURCES]


# ── /api/constants ────────────────────────────────────────────────────────────

class TestApiConstants:
    def test_returns_200(self, web_client):
        r = web_client.get("/api/constants")
        assert r.status_code == 200

    def test_sources_matches_registry(self, web_client):
        from job.fetcher import SOURCES
        data = web_client.get("/api/constants").get_json()
        assert data["sources"] == [src for src, _ in SOURCES]

    def test_remote_types_complete(self, web_client):
        from job.models import RemoteType
        data = web_client.get("/api/constants").get_json()
        assert set(data["remote_types"]) == set(RemoteType.ALL)

    def test_job_statuses_present(self, web_client):
        from job.models import JOB_STATUSES
        data = web_client.get("/api/constants").get_json()
        assert set(data["job_statuses"]) == set(JOB_STATUSES)

    def test_default_blacklist_matches(self, web_client):
        from job.models import DEFAULT_BLACKLIST
        data = web_client.get("/api/constants").get_json()
        assert set(data["default_blacklist"]) == set(DEFAULT_BLACKLIST)

