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


# ── remote-backfill migration ───────────────────────────────────────────────

def _run_backfill(db):
    """Reset the one-shot flag and re-run the remote backfill migration."""
    with db._connect() as con:
        con.execute("DELETE FROM db_meta WHERE key = 'remote_backfill_v1'")
        con.commit()
    db._backfill_remote()


def test_remote_backfill_fixes_stale_labels(temp_db):
    # Jobicy is remote-only: an On-site row with no keyword is a stale false default.
    temp_db.insert_job(job_id="jc_1", url="http://x/1", title="Backend Engineer",
                       company="X", location="", remote="On-site", experience="",
                       description="Build things", posted_at=None, search_name="t")
    # LinkedIn card with no workplace signal was falsely defaulted On-site → Unknown.
    temp_db.insert_job(job_id="li_1", url="http://x/2", title="Software Engineer",
                       company="Y", location="Berlin", remote="On-site", experience="",
                       description="Write code", posted_at=None, search_name="t")

    _run_backfill(temp_db)

    assert temp_db.get_job("jc_1")["remote"] == "Remote"
    assert temp_db.get_job("li_1")["remote"] == "Unknown"


def test_remote_backfill_keeps_keyword_signals(temp_db):
    # A row whose text carries a real remote keyword must be preserved/derived,
    # not clobbered — even for a location-signal source.
    temp_db.insert_job(job_id="gh_acme_1", url="http://x/3", title="Product Manager",
                       company="Acme", location="Remote - US", remote="Remote", experience="",
                       description="", posted_at=None, search_name="t")
    # Greenhouse row with a named office location and no keyword stays On-site.
    temp_db.insert_job(job_id="gh_acme_2", url="http://x/4", title="Designer",
                       company="Acme", location="Berlin, Germany", remote="On-site", experience="",
                       description="", posted_at=None, search_name="t")

    _run_backfill(temp_db)

    assert temp_db.get_job("gh_acme_1")["remote"] == "Remote"
    assert temp_db.get_job("gh_acme_2")["remote"] == "On-site"


def test_remote_backfill_is_idempotent(temp_db):
    temp_db.insert_job(job_id="jc_9", url="http://x/9", title="Engineer",
                       company="X", location="", remote="On-site", experience="",
                       description="Build", posted_at=None, search_name="t")
    _run_backfill(temp_db)
    assert temp_db.get_job("jc_9")["remote"] == "Remote"
    # A second run (without resetting the flag) changes nothing and doesn't error.
    temp_db._backfill_remote()
    assert temp_db.get_job("jc_9")["remote"] == "Remote"



# ── token usage tracking ──────────────────────────────────────────────────────

def test_log_and_sum_token_usage(temp_db):
    temp_db.log_token_usage("groq", "llama", input=100, output=50, total=150)
    temp_db.log_token_usage("groq", "llama", input=10, output=5, total=15)
    temp_db.log_token_usage("gemini", "flash", input=0, output=0, total=200)
    since = temp_db.usage_last_24h()
    assert since["groq"] == 165
    assert since["gemini"] == 200


def test_usage_last_24h_excludes_old(temp_db):
    import sqlite3
    # Insert a row 48h old directly, plus a fresh one.
    from datetime import datetime, timezone, timedelta
    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    with temp_db._connect() as con:
        con.execute("INSERT INTO token_usage (ts, provider, model, input, output, total) VALUES (?,?,?,?,?,?)",
                    (old, "groq", "llama", 0, 0, 999))
        con.commit()
    temp_db.log_token_usage("groq", "llama", total=10)
    assert temp_db.usage_last_24h().get("groq") == 10  # old 999 excluded


def test_usage_empty_is_empty_dict(temp_db):
    assert temp_db.usage_last_24h() == {}
    assert temp_db.usage_today() == {}


def test_usage_scoped_to_current_key(temp_db):
    # Old account's usage
    temp_db.log_token_usage("groq", "llama", total=90000, key_id="oldkeyaaaa11")
    # After switching keys, new account starts fresh
    temp_db.log_token_usage("groq", "llama", total=1200, key_id="newkeybbbb22")
    # Counter scoped to the CURRENT key shows only the new account
    scoped = temp_db.usage_last_24h({"groq": "newkeybbbb22"})
    assert scoped.get("groq") == 1200
    # Unscoped (no key map) still sums everything (back-compat)
    assert temp_db.usage_last_24h().get("groq") == 91200


def test_usage_unknown_current_key_counts_nothing(temp_db):
    temp_db.log_token_usage("groq", "llama", total=500, key_id="somekey00001")
    # No active key (empty fingerprint) -> nothing attributed
    assert temp_db.usage_last_24h({"groq": ""}).get("groq", 0) == 0


# ── job / profile embeddings ──────────────────────────────────────────────────

def test_job_embedding_roundtrip(temp_db):
    temp_db.insert_job(job_id="e1", url="http://x", title="Eng", company="Acme",
                       location="", remote="Remote", experience="", description="d",
                       posted_at=None, search_name="t")
    assert temp_db.get_job_embedding("e1") is None
    temp_db.set_job_embedding("e1", [0.1, 0.2, 0.3])
    assert temp_db.get_job_embedding("e1") == [0.1, 0.2, 0.3]


def test_jobs_missing_embedding(temp_db):
    temp_db.insert_job(job_id="e1", url="http://x", title="A", company="C", location="",
                       remote="", experience="", description="d", posted_at=None, search_name="t")
    temp_db.insert_job(job_id="e2", url="http://x", title="B", company="C", location="",
                       remote="", experience="", description="d", posted_at=None, search_name="t")
    temp_db.set_job_embedding("e1", [1.0])
    missing = {r["job_id"] for r in temp_db.get_jobs_missing_embedding()}
    assert missing == {"e2"}


def test_profile_embedding_meta_hash(temp_db):
    assert temp_db.get_profile_embedding_meta() is None
    temp_db.set_profile_embedding_meta("hash123", [0.5, 0.6])
    got = temp_db.get_profile_embedding_meta()
    assert got == ("hash123", [0.5, 0.6])


def test_match_cache_roundtrip(temp_db):
    _insert(temp_db, job_id="m1")
    temp_db.set_job_match_cache("m1", "prof1", '{"score": 42}')
    row = temp_db.get_job("m1")
    assert row["match_cache"] == '{"score": 42}'
    assert row["match_profile_hash"] == "prof1"


def test_update_description_clears_match_cache(temp_db):
    _insert(temp_db, job_id="m1", status_desc="old")
    temp_db.set_job_match_cache("m1", "prof1", '{"score": 1}')
    temp_db.update_description("m1", "new description")
    row = temp_db.get_job("m1")
    assert row["description"] == "new description"
    assert row["match_cache"] is None
    assert row["match_profile_hash"] is None


def test_get_jobs_list_by_status_skips_descriptions(temp_db):
    _insert(temp_db, job_id="m1", status_desc="long description text")
    temp_db.set_job_match_cache("m1", "prof1", '{"score": 99}')
    rows, stale = temp_db.get_jobs_list_by_status("pending", "prof1")
    assert len(rows) == 1
    assert stale == []
    assert "description" not in rows[0].keys()


def test_get_jobs_list_by_status_marks_stale_cache(temp_db):
    _insert(temp_db, job_id="m1", status_desc="text")
    rows, stale = temp_db.get_jobs_list_by_status("pending", "prof1")
    assert stale == ["m1"]
    descs = temp_db.get_job_descriptions(stale)
    assert descs["m1"] == "text"
