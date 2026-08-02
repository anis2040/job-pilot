"""Integration tests for job.db against a temporary SQLite database.

Uses the temp_db fixture (see conftest.py) so nothing touches a real profile.
"""


def _insert(db, job_id="j1", title="Software Engineer", company="Acme",
            status_desc="", location="Remote", search_name="test"):
    db.insert_job(
        job_id=job_id, url=f"http://example.com/{job_id}", title=title,
        company=company, location=location, remote="remote", experience="",
        description=status_desc, posted_at=None, search_name=search_name,
    )


def test_insert_and_get(temp_db):
    _insert(temp_db, job_id="j1", title="Backend Engineer", company="Acme")
    row = temp_db.get_job("j1")
    assert row is not None
    assert row["title"] == "Backend Engineer"
    assert row["status"] == "pending"


def test_insert_or_ignore_duplicate_id(temp_db):
    _insert(temp_db, job_id="j1", title="First")
    _insert(temp_db, job_id="j1", title="Second")  # same id, ignored
    row = temp_db.get_job("j1")
    assert row["title"] == "First"


def test_already_seen(temp_db):
    assert temp_db.already_seen("j1") is False
    _insert(temp_db, job_id="j1")
    assert temp_db.already_seen("j1") is True


def test_already_seen_via_filter_log(temp_db):
    temp_db.insert_filter_log("jx", "Junior Intern", "intern")
    assert temp_db.already_seen("jx") is True


def test_is_duplicate_normalizes_title(temp_db):
    _insert(temp_db, job_id="j1", title="Senior/Staff Engineer", company="Acme")
    # Same company, title differing only by punctuation -> duplicate
    assert temp_db.is_duplicate("Senior-Staff Engineer", "Acme") is True
    # Different company -> not a duplicate
    assert temp_db.is_duplicate("Senior/Staff Engineer", "Other Co") is False


def test_is_duplicate_only_pending(temp_db):
    _insert(temp_db, job_id="j1", title="Engineer", company="Acme")
    temp_db.update_status("j1", "applied")
    # Now that it's applied, an incoming pending job with same title is not a dupe
    assert temp_db.is_duplicate("Engineer", "Acme") is False


def test_update_status(temp_db):
    _insert(temp_db, job_id="j1")
    assert temp_db.update_status("j1", "applied") is True
    assert temp_db.get_job("j1")["status"] == "applied"


def test_update_status_missing_job(temp_db):
    assert temp_db.update_status("nonexistent", "applied") is False


def test_get_pending(temp_db):
    _insert(temp_db, job_id="j1")
    _insert(temp_db, job_id="j2")
    temp_db.update_status("j2", "skipped")
    pending = temp_db.get_pending()
    ids = {r["job_id"] for r in pending}
    assert ids == {"j1"}


def test_update_description(temp_db):
    _insert(temp_db, job_id="j1", status_desc="")
    temp_db.update_description("j1", "A long job description here")
    assert temp_db.get_job("j1")["description"] == "A long job description here"


def test_stats(temp_db):
    _insert(temp_db, job_id="j1")
    _insert(temp_db, job_id="j2")
    _insert(temp_db, job_id="j3")
    temp_db.update_status("j2", "applied")
    temp_db.update_status("j3", "applied")
    s = temp_db.stats()
    assert s == {"pending": 1, "applied": 2}


def test_fetch_log_roundtrip(temp_db):
    assert temp_db.last_fetch_at() is None
    temp_db.log_fetch("greenhouse", 5)
    assert temp_db.last_fetch_at() is not None
    assert temp_db.last_fetch_at("greenhouse") is not None
    assert temp_db.last_fetch_at("nonexistent-source") is None


def test_clear_all_jobs(temp_db):
    _insert(temp_db, job_id="j1")
    temp_db.insert_filter_log("jx", "t", "kw")
    temp_db.log_fetch("src", 1)
    temp_db.clear_all_jobs()
    assert temp_db.get_pending() == []
    assert temp_db.already_seen("jx") is False
    assert temp_db.last_fetch_at() is None


def test_get_pending_deduped_runs(temp_db):
    """Regression: this query referenced a non-existent `score` column and threw
    'no such column: score'. It must execute cleanly."""
    _insert(temp_db, job_id="j1", title="Engineer", company="Acme")
    rows = temp_db.get_pending_deduped()
    assert len(rows) == 1


def test_get_pending_deduped_collapses_duplicates(temp_db):
    """Same company + title differing only by punctuation collapse to one row;
    the row with a description is preferred."""
    _insert(temp_db, job_id="j1", title="Senior/Staff Engineer", company="Acme", status_desc="")
    _insert(temp_db, job_id="j2", title="Senior-Staff Engineer", company="Acme",
            status_desc="Full description here")
    rows = temp_db.get_pending_deduped()
    assert len(rows) == 1
    assert rows[0]["job_id"] == "j2"  # the one with a description wins


def test_get_pending_deduped_keeps_distinct(temp_db):
    _insert(temp_db, job_id="j1", title="Engineer", company="Acme")
    _insert(temp_db, job_id="j2", title="Engineer", company="Globex")
    _insert(temp_db, job_id="j3", title="Designer", company="Acme")
    rows = temp_db.get_pending_deduped()
    assert len(rows) == 3
