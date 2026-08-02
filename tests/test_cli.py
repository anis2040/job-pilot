"""Smoke tests for the Typer CLI commands.

All tests run fully offline. The temp_db fixture from conftest.py patches
job.db._connect to a fresh SQLite file, so every CLI command that calls
init_db() / DB functions hits the isolated database. load_config is also
stubbed so commands that need a config don't require a real profile on disk.
"""
import pytest
from typer.testing import CliRunner

from job.cli import app
from job.config import Config, SearchConfig

runner = CliRunner()


@pytest.fixture
def cli_db(temp_db, monkeypatch):
    """Isolated DB + stubbed config, reusing temp_db from conftest.py."""
    from job import config as cfg

    monkeypatch.setattr(
        cfg,
        "load_config",
        lambda path=None: Config(
            searches=[
                SearchConfig(name="t", source="greenhouse", query="eng", location="US")
            ]
        ),
    )
    return temp_db


def _insert(db, job_id="test_001", title="Software Engineer", company="Acme"):
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


# ── stats ─────────────────────────────────────────────────────────────────────

def test_stats_empty_db(cli_db):
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "No listings" in result.output


def test_stats_shows_counts(cli_db):
    _insert(cli_db, "job_001")
    _insert(cli_db, "job_002")
    cli_db.update_status("job_001", "applied")

    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    # Both statuses should appear in some form
    assert "applied" in result.output
    assert "pending" in result.output


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_empty(cli_db):
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No pending" in result.output


def test_list_shows_jobs(cli_db):
    _insert(cli_db, title="ML Engineer")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "ML Engineer" in result.output


# ── done / skip ───────────────────────────────────────────────────────────────

def test_done_marks_applied(cli_db):
    _insert(cli_db, "j_001")
    result = runner.invoke(app, ["done", "j_001"])
    assert result.exit_code == 0
    row = cli_db.get_job("j_001")
    assert row["status"] == "applied"


def test_skip_marks_skipped(cli_db):
    _insert(cli_db, "j_002")
    result = runner.invoke(app, ["skip", "j_002"])
    assert result.exit_code == 0
    row = cli_db.get_job("j_002")
    assert row["status"] == "skipped"


def test_done_missing_job_prints_error(cli_db):
    result = runner.invoke(app, ["done", "no_such_id"])
    assert result.exit_code == 0
    assert "not found" in result.output.lower()


def test_skip_missing_job_prints_error(cli_db):
    result = runner.invoke(app, ["skip", "no_such_id"])
    assert result.exit_code == 0
    assert "not found" in result.output.lower()
