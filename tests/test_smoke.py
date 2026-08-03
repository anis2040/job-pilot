"""End-to-end smoke test for JobPilot AI's main features.

One test that walks the critical user path: every page renders, the core APIs
respond, and a job flows through the status lifecycle. Fully offline — isolated
profile + in-memory DB, all AI/external tools stubbed. If this fails, something
user-visible is broken.
"""
import sqlite3
import pytest

import web
import job.paths
import job.profiles as profs
import job.db as db


def _row_conn(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "BASE", tmp_path)
    monkeypatch.setattr(job.paths, "BASE", tmp_path)
    pdir = tmp_path / "profiles"; pdir.mkdir()
    monkeypatch.setattr(profs, "PROFILES_DIR", pdir)
    monkeypatch.setattr(profs, "ACTIVE_FILE", pdir / ".active")
    monkeypatch.setattr(profs, "_update_symlinks", lambda d: None)
    monkeypatch.setattr(web, "PROFILES_DIR", pdir)

    prof = pdir / "smoke-user"; prof.mkdir()
    (prof / "profile.md").write_text("# Smoke User\nSoftware Engineer")
    (prof / "config.yaml").write_text(
        "searches:\n  - name: t\n    source: linkedin\n    query: engineer\n    location: Germany\n")
    (pdir / ".active").write_text("smoke-user")

    db_file = prof / "state.db"
    monkeypatch.setattr(db, "_connect", lambda: _row_conn(db_file))
    db.init_db()

    # Stub AI clients / external tools so nothing reaches the network.
    monkeypatch.setattr(web, "_get_groq_client", lambda: None)
    monkeypatch.setattr(web, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(web, "_get_gemini_client", lambda: None)
    monkeypatch.setattr(web.shutil, "which", lambda _: None)

    web.app.config["TESTING"] = True
    return web.app.test_client()


def test_smoke_all_pages_render(client):
    """Every user-facing page returns 200."""
    for path in ["/", "/setup", "/manage-profiles", "/profiles",
                 "/profile-settings/smoke-user", "/ai-settings"]:
        assert client.get(path).status_code == 200, f"{path} did not render"


def test_smoke_core_apis(client):
    """The APIs the UI depends on respond with sane shapes."""
    assert client.get("/api/sources").status_code == 200
    assert isinstance(client.get("/api/sources").get_json(), list)

    consts = client.get("/api/constants").get_json()
    for key in ("sources", "remote_types", "job_statuses", "default_blacklist"):
        assert key in consts

    assert client.get("/api/jobs?status=pending").status_code == 200
    assert client.get("/api/profiles").status_code == 200
    assert client.get("/api/setup/status").status_code == 200


def test_smoke_job_lifecycle(client):
    """A job can be listed, opened, and moved through the status lifecycle."""
    db.insert_job(job_id="li_smoke", url="https://x.co/1", title="Backend Engineer",
                  company="Acme", location="Berlin", remote="Remote", experience="3+",
                  description="Build things", posted_at=None, search_name="t")

    # appears in pending
    pending = client.get("/api/jobs?status=pending").get_json()
    assert any(j["job_id"] == "li_smoke" for j in pending)
    # every serialized job carries a `match` key (None when unscoreable — never a fake 0%)
    assert all("match" in j for j in pending)

    # detail page + detail API both work
    assert client.get("/job/li_smoke").status_code == 200
    detail = client.get("/api/job/li_smoke").get_json()
    assert detail["title"] == "Backend Engineer" and detail["description"] == "Build things"

    # apply → moves out of pending into applied
    assert client.post("/api/job-status/li_smoke/applied").get_json()["ok"] is True
    assert not any(j["job_id"] == "li_smoke" for j in client.get("/api/jobs?status=pending").get_json())
    assert any(j["job_id"] == "li_smoke" for j in client.get("/api/jobs?status=applied").get_json())

    # restore → back to pending
    client.post("/api/job-status/li_smoke/pending")
    assert any(j["job_id"] == "li_smoke" for j in client.get("/api/jobs?status=pending").get_json())


def test_smoke_search_settings_roundtrip(client):
    """Saving and reading back search settings works end to end."""
    payload = {
        "searches": [{"name": "li-eng", "source": "linkedin", "query": "engineer", "location": "Germany"}],
        "title_filter": ["engineer"], "blacklist": ["junior"], "company_blacklist": [],
    }
    assert client.post("/api/config", json=payload).get_json()["ok"] is True
    cfg = client.get("/api/config").get_json()
    assert any(s["source"] == "linkedin" for s in cfg["searches"])
    assert "junior" in cfg["blacklist"]
