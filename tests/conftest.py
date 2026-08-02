"""Shared pytest fixtures.

Tests run fully offline — no API keys, no network, no pdflatex required.
The temp_db fixture redirects job.db to an isolated SQLite file so DB tests
never touch a real profile.
"""
import sqlite3
import pytest

import job.db as db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point job.db at a fresh temp SQLite file and create the schema.

    Yields the db module so tests can call its functions directly.
    """
    db_file = tmp_path / "state.db"

    def _connect():
        con = sqlite3.connect(db_file)
        con.row_factory = sqlite3.Row
        return con

    monkeypatch.setattr(db, "_connect", _connect)
    db.init_db()
    yield db
