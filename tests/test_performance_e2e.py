"""E2E tests for single-VM performance optimizations.

Exercises the full Flask stack (same isolation as test_smoke.py) for behaviours
introduced to reduce load on a small shared VM: match caching, PDF indexing,
pdflatex concurrency cap, and deferred embedding backfill.
"""
from __future__ import annotations

import sqlite3
import threading
import time

import pytest

import web
import job.paths
import job.profiles as profs
import job.db as db
import job.fetch_worker as fetch_worker
from job.models import RawJob


def _row_conn(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


@pytest.fixture
def client(tmp_path, monkeypatch):
    from job.user_context import LOCAL_USER_ID

    monkeypatch.setattr(web, "BASE", tmp_path)
    monkeypatch.setattr(job.paths, "BASE", tmp_path)
    dist = tmp_path / "frontend-dist"
    dist.mkdir()
    (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    monkeypatch.setattr(web, "_FRONTEND_DIST", dist)
    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    pdir = tmp_path / "profiles"
    pdir.mkdir()
    monkeypatch.setattr(profs, "PROFILES_DIR", pdir)
    monkeypatch.setattr(profs, "_update_symlinks", lambda d: None)
    monkeypatch.setattr(profs, "get_current_user_id", lambda: LOCAL_USER_ID)

    user_dir = pdir / LOCAL_USER_ID
    prof = user_dir / "perf-user"
    prof.mkdir(parents=True)
    (prof / "profile.md").write_text("# Perf User\nSoftware Engineer with Python experience")
    (prof / "config.yaml").write_text(
        "searches:\n  - name: t\n    source: greenhouse\n    query: engineer\n    location: Germany\n"
    )
    (user_dir / ".active").write_text("perf-user")

    db_file = prof / "state.db"
    monkeypatch.setattr(db, "_connect", lambda: _row_conn(db_file))
    db.init_db()

    monkeypatch.setattr(web, "_get_groq_client", lambda: None)
    monkeypatch.setattr(web, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(web, "_get_gemini_client", lambda: None)
    monkeypatch.setattr(web.shutil, "which", lambda _: None)

    web.app.config["TESTING"] = True
    yield web.app.test_client()

    from job.concurrency import reset_for_tests
    reset_for_tests()


def _insert(job_id="j1", **kwargs):
    db.insert_job(
        job_id=job_id,
        url=kwargs.get("url", f"https://example.com/{job_id}"),
        title=kwargs.get("title", "Python Engineer"),
        company=kwargs.get("company", "Acme"),
        location=kwargs.get("location", "Berlin"),
        remote=kwargs.get("remote", "Remote"),
        experience=kwargs.get("experience", ""),
        description=kwargs.get("description", "Requires Python, Django, and PostgreSQL."),
        posted_at=kwargs.get("posted_at"),
        search_name=kwargs.get("search_name", "t"),
    )


def _wait_fetch_done(client, *, timeout_s: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        st = client.get("/api/fetch-status").get_json()
        if st.get("status") in ("done", "error", "idle"):
            return st
        time.sleep(0.02)
    return client.get("/api/fetch-status").get_json()


class TestMatchCacheE2E:
    def test_second_list_load_uses_cached_match(self, client, monkeypatch):
        import job.match as match_mod

        _insert("gh_cache")
        warm = client.get("/api/jobs")
        assert warm.status_code == 200
        assert db.get_job("gh_cache")["match_cache"]

        def boom(*_a, **_k):
            raise AssertionError("compute_match should not run when match_cache is warm")

        monkeypatch.setattr(match_mod, "compute_match", boom)
        cached = client.get("/api/jobs")
        assert cached.status_code == 200
        assert cached.get_json()[0]["match"] is not None

    def test_list_shows_inferred_remote_without_db_write(self, client):
        _insert(
            "li_remote",
            remote="Remote",
            description="This is a hybrid role with two office days per week.",
        )
        listed = client.get("/api/jobs").get_json()
        assert listed[0]["remote"] == "Hybrid"
        assert db.get_job("li_remote")["remote"] == "Remote"


class TestPdfIndexE2E:
    def test_api_jobs_builds_pdf_index_once(self, client, monkeypatch):
        calls = {"index": 0}
        orig = web._build_pdf_index

        def spy(profile_dir):
            calls["index"] += 1
            return orig(profile_dir)

        monkeypatch.setattr(web, "_build_pdf_index", spy)
        for i in range(3):
            _insert(job_id=f"gh_pdf_{i}", company=f"Co{i}")

        assert client.get("/api/jobs").status_code == 200
        assert calls["index"] == 1


class TestConcurrencyE2E:
    def test_fetch_returns_429_when_same_user_already_fetching(self, client, monkeypatch):
        import job.fetch_worker as fw
        from job import task_state

        gate = threading.Event()

        def blocked_fetch():
            gate.wait(timeout=2)
            task_state.set_fetch_done("done")

        monkeypatch.setattr(fw, "_run_fetch", blocked_fetch)

        assert client.post("/api/fetch").get_json()["started"] is True
        resp = client.post("/api/fetch")
        assert resp.status_code == 429
        assert resp.get_json()["started"] is False

        gate.set()
        _wait_fetch_done(client)

    def test_fetch_marks_done_before_slow_embedding_backfill(self, client, monkeypatch):
        events: list[str] = []
        gate = threading.Event()

        def slow_backfill():
            events.append("backfill_start")
            gate.wait(timeout=2)
            events.append("backfill_end")

        sample = RawJob(
            job_id="gh_embed",
            url="https://example.com/gh_embed",
            title="Backend Engineer",
            company="Acme",
            location="Berlin",
            remote="Remote",
            experience="",
            description="Python and Django required.",
        )
        monkeypatch.setattr(fetch_worker, "_backfill_embeddings", slow_backfill)
        monkeypatch.setattr(fetch_worker, "fetch_search", lambda _search: [sample])

        assert client.post("/api/fetch").get_json()["started"] is True
        st = _wait_fetch_done(client)
        assert st["status"] == "done"
        events.append("done")

        deadline = time.monotonic() + 2.0
        while "backfill_start" not in events and time.monotonic() < deadline:
            time.sleep(0.02)

        gate.set()
        time.sleep(0.05)

        assert "backfill_start" in events
        assert "backfill_end" in events
        assert events.index("done") < events.index("backfill_end")
