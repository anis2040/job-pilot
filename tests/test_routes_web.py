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
    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    # Isolate profile filesystem (user-scoped under _local)
    from job.user_context import LOCAL_USER_ID
    pdir = tmp_path / "profiles"
    pdir.mkdir()
    monkeypatch.setattr(profs, "PROFILES_DIR", pdir)
    monkeypatch.setattr(profs, "_update_symlinks", lambda d: None)
    monkeypatch.setattr(profs, "get_current_user_id", lambda: LOCAL_USER_ID)

    # Create a test profile and activate it
    user_dir = pdir / LOCAL_USER_ID
    profile_dir = user_dir / "test-user"
    profile_dir.mkdir(parents=True)
    (profile_dir / "profile.md").write_text("# Test User\nSoftware Engineer")
    (profile_dir / "config.yaml").write_text(
        "searches:\n"
        "  - name: t\n"
        "    source: greenhouse\n"
        "    query: engineer\n"
        "    location: United States\n"
    )
    (user_dir / ".active").write_text("test-user")

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

    def test_list_shows_inferred_remote_without_db_write(self, web_client):
        db.insert_job(
            job_id="li_1",
            url="https://example.com/job/1",
            title="Engineering Manager",
            company="Acme",
            location="Berlin",
            remote="Remote",
            experience="",
            description="This is a hybrid role with two office days per week.",
            posted_at=None,
            search_name="t",
        )

        r = web_client.get("/api/jobs")

        assert r.status_code == 200
        assert r.get_json()[0]["remote"] == "Hybrid"
        assert db.get_job("li_1")["remote"] == "Remote"

    def test_description_persists_remote_correction(self, web_client):
        db.insert_job(
            job_id="li_1",
            url="https://example.com/job/1",
            title="Engineering Manager",
            company="Acme",
            location="Berlin",
            remote="Remote",
            experience="",
            description="This is a hybrid role with two office days per week.",
            posted_at=None,
            search_name="t",
        )

        r = web_client.get("/api/job/li_1/description")

        assert r.status_code == 200
        assert r.get_json()["remote"] == "Hybrid"
        assert db.get_job("li_1")["remote"] == "Hybrid"

    def test_match_cache_avoids_recompute(self, web_client, monkeypatch):
        import job.match as match_mod

        _insert_job("j1", title="Python Developer")
        db.update_description("j1", "Requires Python, Django, and PostgreSQL experience.")
        warm = web_client.get("/api/jobs")
        assert warm.status_code == 200
        assert db.get_job("j1")["match_cache"]

        def boom(*_a, **_k):
            raise AssertionError("compute_match should not run on cache hit")

        monkeypatch.setattr(match_mod, "compute_match", boom)
        r = web_client.get("/api/jobs")
        assert r.status_code == 200
        assert r.get_json()[0]["match"] is not None


class TestApiJobDescription:
    def test_fetched_description_can_correct_remote_to_hybrid(self, web_client, monkeypatch):
        import job.fetcher as fetcher
        _insert_job("li_2", title="Product Manager")
        monkeypatch.setattr(fetcher, "fetch_description", lambda *_: "Hybrid work model with team office days.")

        r = web_client.get("/api/job/li_2/description")

        assert r.status_code == 200
        assert r.get_json()["remote"] == "Hybrid"
        assert db.get_job("li_2")["remote"] == "Hybrid"

    def test_stepstone_snippet_is_refreshed_to_full_description(self, web_client, monkeypatch):
        import job.fetcher as fetcher
        full_description = (
            "Was Deinen Job ausmacht\n"
            "• Begleitung der Entwicklung und Optimierung komplexer Webprojekte\n"
            "• Gezielter Einsatz KI-gestützter Entwicklungs- und Assistenztools\n"
            "Das wünschen wir uns\n"
            "Sehr gute Deutschkenntnisse und gute Englischkenntnisse"
        )
        db.insert_job(
            job_id="ss_2",
            url="https://www.stepstone.de/stellenangebote--frontend--2-inline.html",
            title="Frontend Engineer",
            company="Cofinpro",
            location="Frankfurt",
            remote="Remote",
            experience="",
            description="Remote work possible",
            posted_at=None,
            search_name="stepstone",
        )
        monkeypatch.setattr(fetcher, "fetch_description", lambda *_: full_description)

        r = web_client.get("/api/job/ss_2/description")

        assert r.status_code == 200
        assert r.get_json()["description"] == full_description
        assert db.get_job("ss_2")["description"] == full_description


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
    for key in ("debug", "has_claude", "has_gemini", "has_pdflatex", "has_node",
                "has_profile", "gemini_key_set", "groq_key_set", "anthropic_key_set"):
        assert isinstance(data[key], bool), f"{key} should be bool"


def test_setup_installs_blocked_when_not_debug(web_client, monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "false")
    r = web_client.post("/api/setup/install-node")
    assert r.status_code == 403
    assert "development" in r.get_json()["error"].lower()


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

    def test_narrowing_work_styles_is_local_only_and_keeps_jobs(self, web_client):
        _insert_job("j-config", title="Engineer")
        payload = {
            "searches": [
                {"name": "gh-eng", "source": "greenhouse", "query": "engineer",
                 "location": "United States", "max_pages": 3, "work_styles": ["Remote"]}
            ],
            "title_filter": ["engineer"],
            "blacklist": [],
            "company_blacklist": [],
        }

        r = web_client.post("/api/config", json=payload)

        assert r.status_code == 200
        assert r.get_json()["fetch_required"] is False
        assert db.get_job("j-config") is not None

    def test_expanding_work_styles_requires_fetch(self, web_client):
        remote_only = {
            "searches": [
                {"name": "gh-eng", "source": "greenhouse", "query": "engineer",
                 "location": "United States", "max_pages": 3, "work_styles": ["Remote"]}
            ],
            "title_filter": ["engineer"],
            "blacklist": [],
            "company_blacklist": [],
        }
        remote_and_hybrid = {
            **remote_only,
            "searches": [{**remote_only["searches"][0], "work_styles": ["Remote", "Hybrid"]}],
        }
        assert web_client.post("/api/config", json=remote_only).status_code == 200

        r = web_client.post("/api/config", json=remote_and_hybrid)

        assert r.status_code == 200
        assert r.get_json()["fetch_required"] is True

    def test_all_work_styles_can_be_narrowed_locally(self, web_client):
        all_styles = {
            "searches": [
                {"name": "gh-eng", "source": "greenhouse", "query": "engineer",
                 "location": "United States", "max_pages": 3, "remote": False, "work_styles": []}
            ],
            "title_filter": ["engineer"],
            "blacklist": [],
            "company_blacklist": [],
        }
        remote_only = {
            **all_styles,
            "searches": [{**all_styles["searches"][0], "remote": True, "work_styles": ["Remote"]}],
        }
        assert web_client.post("/api/config", json=all_styles).status_code == 200

        r = web_client.post("/api/config", json=remote_only)

        assert r.status_code == 200
        assert r.get_json()["fetch_required"] is False

    def test_changing_location_requires_fetch(self, web_client):
        us_search = {
            "searches": [
                {"name": "gh-eng", "source": "greenhouse", "query": "engineer",
                 "location": "United States", "max_pages": 3, "work_styles": ["Remote"]}
            ],
            "title_filter": ["engineer"],
            "blacklist": [],
            "company_blacklist": [],
        }
        germany_search = {
            **us_search,
            "searches": [{**us_search["searches"][0], "location": "Germany"}],
        }
        assert web_client.post("/api/config", json=us_search).status_code == 200

        r = web_client.post("/api/config", json=germany_search)

        assert r.status_code == 200
        assert r.get_json()["fetch_required"] is True


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



# ── PDF discovery (_find_pdf_path) ──────────────────────────────────────────────

class TestFindPdfPath:
    """Regression tests: built PDFs must be found by document-type suffix even
    when the filename's name-prefix differs from the current profile name, and
    across the current/sibling/legacy directory layouts."""

    def _make(self, tmp_path, rel):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF-1.4 test")
        return p

    def test_matches_different_name_prefix(self, tmp_path):
        # Built under "Anis" but we search generically for a resume
        self._make(tmp_path, "CGI/resumes/Anis_Helaoui_Resume.pdf")
        found = web._find_pdf_path(tmp_path, "CGI", "resumes", "_Resume.pdf")
        assert found and found.endswith("Anis_Helaoui_Resume.pdf")

    def test_cover_letter_suffix(self, tmp_path):
        self._make(tmp_path, "CGI/cover-letters/Yassine_Helaoui_Cover_Letter.pdf")
        found = web._find_pdf_path(tmp_path, "CGI", "cover-letters", "_Cover_Letter.pdf")
        assert found and found.endswith("_Cover_Letter.pdf")

    def test_resume_search_ignores_cover_letter(self, tmp_path):
        # A resumes/ dir containing only a cover letter must NOT match a resume search
        self._make(tmp_path, "CGI/resumes/X_Cover_Letter.pdf")
        assert web._find_pdf_path(tmp_path, "CGI", "resumes", "_Resume.pdf") is None

    def test_company_name_variants(self, tmp_path):
        # Spaces stripped in the stored dir name
        self._make(tmp_path, "TheScionGroup/resumes/N_Resume.pdf")
        found = web._find_pdf_path(tmp_path, "The Scion Group", "resumes", "_Resume.pdf")
        assert found is not None

    def test_missing_returns_none(self, tmp_path):
        assert web._find_pdf_path(tmp_path, "Nope", "resumes", "_Resume.pdf") is None
