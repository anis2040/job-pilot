from __future__ import annotations
import sqlite3
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    from .profiles import get_db_path
    db_path = get_db_path()
    if not db_path:
        raise RuntimeError("No active profile. Complete setup first.")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    _tune_connection(con)
    return con


def _tune_connection(con: sqlite3.Connection) -> None:
    """Keep SQLite responsive on local desktop filesystems, especially Windows.

    busy_timeout avoids instant failures while a fetch is committing, and the
    other settings reduce temp-file churn for local cache-style queries.
    """
    for statement in (
        "PRAGMA busy_timeout = 5000",
        "PRAGMA synchronous = NORMAL",
        "PRAGMA temp_store = MEMORY",
    ):
        try:
            con.execute(statement)
        except sqlite3.DatabaseError:
            pass


def init_db() -> None:
    with _connect() as con:
        try:
            con.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        con.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id            TEXT PRIMARY KEY,
                url               TEXT NOT NULL,
                title             TEXT,
                company           TEXT,
                location          TEXT,
                remote            TEXT,
                experience        TEXT,
                description       TEXT,
                posted_at         TEXT,
                first_seen_at     TEXT NOT NULL,
                status            TEXT NOT NULL DEFAULT 'pending',
                status_updated_at TEXT,
                search_name       TEXT,
                employment_type   TEXT DEFAULT '',
                salary_range      TEXT DEFAULT ''
            )
        """)
        # Migrate existing databases — add columns if not present
        for col, default in [("employment_type", "''"), ("salary_range", "''"), ("embedding", "NULL")]:
            try:
                con.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass  # Column already exists
        # Repair job_ids that captured a URL query string (e.g. "gtj_slug?utm_source=...").
        # The "?" makes the /job/<id> route unreachable, so strip it. Skip rows whose
        # cleaned id would collide with an existing row.
        broken = con.execute("SELECT job_id FROM jobs WHERE job_id LIKE '%?%'").fetchall()
        for r in broken:
            old = r["job_id"]
            new = old.split("?")[0]
            if new == old:
                continue
            exists = con.execute("SELECT 1 FROM jobs WHERE job_id = ?", (new,)).fetchone()
            if exists:
                con.execute("DELETE FROM jobs WHERE job_id = ?", (old,))
            else:
                con.execute("UPDATE jobs SET job_id = ? WHERE job_id = ?", (new, old))
        con.execute("""
            CREATE TABLE IF NOT EXISTS db_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS filter_log (
                job_id          TEXT PRIMARY KEY,
                title           TEXT,
                matched_keyword TEXT,
                filtered_at     TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS fetch_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at   TEXT NOT NULL,
                source       TEXT,
                new_count    INTEGER DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       TEXT NOT NULL,
                provider TEXT,
                model    TEXT,
                input    INTEGER DEFAULT 0,
                output   INTEGER DEFAULT 0,
                total    INTEGER DEFAULT 0,
                key_id   TEXT DEFAULT ''
            )
        """)
        # Migrate older DBs that predate key scoping.
        try:
            con.execute("ALTER TABLE token_usage ADD COLUMN key_id TEXT DEFAULT ''")
        except Exception:
            pass  # column already exists

        con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_first_seen ON jobs(status, first_seen_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_company_title ON jobs(status, company, title)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_fetch_log_source_fetched ON fetch_log(source, fetched_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_fetch_log_fetched ON fetch_log(fetched_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_ts ON token_usage(ts)")
        con.commit()

    # One-time backfill: repair workplace-type labels written under the old
    # "default to On-site" bug. Runs once (guarded by db_meta), re-inferring
    # remote per the corrected per-source logic. Kept out of the schema block so
    # its fetcher import stays lazy (avoids an import cycle).
    _backfill_remote()


def _get_meta(con, key: str) -> str | None:
    row = con.execute("SELECT value FROM db_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(con, key: str, value: str) -> None:
    con.execute("INSERT OR REPLACE INTO db_meta (key, value) VALUES (?, ?)", (key, value))


def _backfill_remote() -> None:
    """Re-infer `remote` for existing rows using the corrected per-source logic.
    Idempotent and one-shot (guarded by a db_meta flag)."""
    from .fetcher import reinfer_remote
    with _connect() as con:
        if _get_meta(con, "remote_backfill_v1") == "done":
            return
        rows = con.execute(
            "SELECT job_id, title, location, description, remote FROM jobs"
        ).fetchall()
        fixed = 0
        for r in rows:
            new = reinfer_remote(r["job_id"], r["title"] or "", r["location"] or "",
                                 r["description"] or "", r["remote"] or "")
            if new is not None:
                con.execute("UPDATE jobs SET remote = ? WHERE job_id = ?", (new, r["job_id"]))
                fixed += 1
        _set_meta(con, "remote_backfill_v1", "done")
        con.commit()
        if fixed:
            print(f"[migration] remote-backfill: corrected {fixed} job(s)")


def already_seen(job_id: str) -> bool:
    with _connect() as con:
        row = con.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row:
            return True
        row = con.execute("SELECT 1 FROM filter_log WHERE job_id = ?", (job_id,)).fetchone()
        return row is not None


def is_duplicate(title: str, company: str) -> bool:
    """True if a pending job with the same normalized title+company already exists."""
    with _connect() as con:
        row = con.execute("""
            SELECT 1 FROM jobs
            WHERE status = 'pending'
              AND LOWER(TRIM(company)) = LOWER(TRIM(?))
              AND LOWER(TRIM(REPLACE(REPLACE(title, '-', ' '), '/', ' ')))
                = LOWER(TRIM(REPLACE(REPLACE(?, '-', ' '), '/', ' ')))
            LIMIT 1
        """, (company, title)).fetchone()
        return row is not None


def _job_id_placeholders(count: int) -> str:
    return ",".join("?" for _ in range(count))


def existing_job_ids(job_ids: list[str]) -> set[str]:
    """Return IDs already present in jobs or filter_log.

    Used by fetch paths to avoid one SQLite round-trip per scraped listing.
    """
    ids = [j for j in dict.fromkeys(job_ids) if j]
    if not ids:
        return set()
    seen: set[str] = set()
    with _connect() as con:
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            placeholders = _job_id_placeholders(len(chunk))
            rows = con.execute(f"SELECT job_id FROM jobs WHERE job_id IN ({placeholders})", chunk).fetchall()
            seen.update(r["job_id"] for r in rows)
            rows = con.execute(f"SELECT job_id FROM filter_log WHERE job_id IN ({placeholders})", chunk).fetchall()
            seen.update(r["job_id"] for r in rows)
    return seen


def duplicate_key(title: str, company: str) -> tuple[str, str]:
    norm_title = (title or "").replace("-", " ").replace("/", " ").strip().lower()
    norm_company = (company or "").strip().lower()
    return norm_company, norm_title


def pending_duplicate_keys() -> set[tuple[str, str]]:
    """Return normalized (company, title) keys for pending rows."""
    with _connect() as con:
        rows = con.execute("SELECT title, company FROM jobs WHERE status = 'pending'").fetchall()
    return {duplicate_key(r["title"] or "", r["company"] or "") for r in rows}


def insert_job(
    job_id: str,
    url: str,
    title: str,
    company: str,
    location: str,
    remote: str,
    experience: str,
    description: str,
    posted_at: str | None,
    search_name: str,
    employment_type: str = "",
    salary_range: str = "",
) -> None:
    now = _now_iso()
    with _connect() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO jobs
                (job_id, url, title, company, location, remote, experience,
                 description, posted_at, first_seen_at, status, search_name,
                 employment_type, salary_range)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (job_id, url, title, company, location, remote, experience,
             description, posted_at, now, search_name,
             employment_type, salary_range),
        )
        con.commit()


def insert_filter_log(job_id: str, title: str, matched_keyword: str) -> None:
    now = _now_iso()
    with _connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO filter_log (job_id, title, matched_keyword, filtered_at) VALUES (?, ?, ?, ?)",
            (job_id, title, matched_keyword, now),
        )
        con.commit()


def insert_filter_logs_batch(entries: list[tuple[str, str, str]]) -> None:
    if not entries:
        return
    now = _now_iso()
    with _connect() as con:
        con.executemany(
            "INSERT OR IGNORE INTO filter_log (job_id, title, matched_keyword, filtered_at) VALUES (?, ?, ?, ?)",
            [(job_id, title, kw, now) for job_id, title, kw in entries],
        )
        con.commit()


def insert_jobs_batch(rows: list[dict]) -> int:
    if not rows:
        return 0
    now = _now_iso()
    with _connect() as con:
        cur = con.executemany(
            """
            INSERT OR IGNORE INTO jobs
                (job_id, url, title, company, location, remote, experience,
                 description, posted_at, first_seen_at, status, search_name,
                 employment_type, salary_range)
            VALUES (:job_id, :url, :title, :company, :location, :remote,
                    :experience, :description, :posted_at, :first_seen_at,
                    'pending', :search_name, :employment_type, :salary_range)
            """,
            [{**row, "first_seen_at": now} for row in rows],
        )
        con.commit()
        return cur.rowcount if cur.rowcount != -1 else len(rows)


def log_fetch(source: str, new_count: int) -> None:
    now = _now_iso()
    with _connect() as con:
        con.execute(
            "INSERT INTO fetch_log (fetched_at, source, new_count) VALUES (?, ?, ?)",
            (now, source, new_count),
        )
        con.commit()


def last_fetch_at(source: str | None = None) -> str | None:
    with _connect() as con:
        if source:
            row = con.execute(
                "SELECT fetched_at FROM fetch_log WHERE source = ? ORDER BY fetched_at DESC LIMIT 1",
                (source,),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT fetched_at FROM fetch_log ORDER BY fetched_at DESC LIMIT 1"
            ).fetchone()
        return row["fetched_at"] if row else None


def log_token_usage(provider: str, model: str, input: int = 0,
                    output: int = 0, total: int = 0, key_id: str = "") -> None:
    """Record one AI call's token usage. Best-effort telemetry. `key_id` is a
    non-secret fingerprint of the active API key, so usage can be scoped to the
    current account (limits are per-key/org)."""
    with _connect() as con:
        con.execute(
            "INSERT INTO token_usage (ts, provider, model, input, output, total, key_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now_iso(), provider, model, int(input or 0), int(output or 0),
             int(total or 0), key_id or ""),
        )
        con.commit()


def token_usage_since(since_iso: str, key_ids: dict[str, str] | None = None) -> dict[str, int]:
    """Total tokens per provider since an ISO-8601 UTC timestamp.

    When `key_ids` maps provider -> current key fingerprint, only rows written
    by that key are counted for that provider — so switching API keys starts a
    fresh count and old-account rows drop out.
    """
    with _connect() as con:
        rows = con.execute(
            "SELECT provider, key_id, SUM(total) AS t FROM token_usage "
            "WHERE ts >= ? GROUP BY provider, key_id",
            (since_iso,),
        ).fetchall()
    out: dict[str, int] = {}
    for r in rows:
        provider, key_id, t = r["provider"], (r["key_id"] or ""), (r["t"] or 0)
        if key_ids is not None:
            want = key_ids.get(provider)
            # Only count rows written by the current key. No current key -> skip.
            if not want or key_id != want:
                continue
        out[provider] = out.get(provider, 0) + t
    return out


def usage_last_24h(key_ids: dict[str, str] | None = None) -> dict[str, int]:
    """Tokens per provider over a rolling 24h window (matches Groq's daily limit)."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    return token_usage_since(cutoff, key_ids)


def usage_today(key_ids: dict[str, str] | None = None) -> dict[str, int]:
    """Tokens per provider since local calendar midnight (intuitive 'today')."""
    now_local = datetime.now().astimezone()
    midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_utc = midnight_local.astimezone(timezone.utc).isoformat()
    return token_usage_since(cutoff_utc, key_ids)



def update_status(job_id: str, status: str) -> bool:
    now = _now_iso()
    with _connect() as con:
        cur = con.execute(
            "UPDATE jobs SET status = ?, status_updated_at = ? WHERE job_id = ?",
            (status, now, job_id),
        )
        con.commit()
        return cur.rowcount > 0


def get_jobs_by_status(status: str) -> list[sqlite3.Row]:
    with _connect() as con:
        return con.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY first_seen_at DESC",
            (status,),
        ).fetchall()


def get_pending() -> list[sqlite3.Row]:
    return get_jobs_by_status("pending")


def update_description(job_id: str, description: str) -> None:
    with _connect() as con:
        con.execute(
            "UPDATE jobs SET description = ? WHERE job_id = ?",
            (description, job_id),
        )
        con.commit()


def update_remote(job_id: str, remote: str) -> None:
    with _connect() as con:
        con.execute(
            "UPDATE jobs SET remote = ? WHERE job_id = ?",
            (remote, job_id),
        )
        con.commit()


def set_job_embedding(job_id: str, vec: list[float] | None) -> None:
    """Store a job's embedding vector as JSON (semantic-match cache)."""
    if not vec:
        return
    import json as _json
    with _connect() as con:
        con.execute("UPDATE jobs SET embedding = ? WHERE job_id = ?",
                    (_json.dumps(vec), job_id))
        con.commit()


def get_job_embedding(job_id: str) -> list[float] | None:
    import json as _json
    with _connect() as con:
        row = con.execute("SELECT embedding FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row or not row["embedding"]:
        return None
    try:
        return _json.loads(row["embedding"])
    except Exception:
        return None


def get_jobs_missing_embedding(limit: int = 100) -> list[sqlite3.Row]:
    """Pending jobs that don't yet have a cached embedding — for the backfill."""
    with _connect() as con:
        return con.execute(
            "SELECT job_id, title, description FROM jobs "
            "WHERE status = 'pending' AND (embedding IS NULL OR embedding = '') "
            "ORDER BY first_seen_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def get_profile_embedding_meta() -> tuple[str, list[float]] | None:
    """Return (profile_hash, vec) cached in db_meta, or None."""
    import json as _json
    with _connect() as con:
        h = _get_meta(con, "profile_embedding_hash")
        v = _get_meta(con, "profile_embedding")
    if not h or not v:
        return None
    try:
        return h, _json.loads(v)
    except Exception:
        return None


def set_profile_embedding_meta(profile_hash: str, vec: list[float]) -> None:
    import json as _json
    with _connect() as con:
        _set_meta(con, "profile_embedding_hash", profile_hash)
        _set_meta(con, "profile_embedding", _json.dumps(vec))
        con.commit()


def get_pending_no_description() -> list[sqlite3.Row]:
    with _connect() as con:
        return con.execute(
            "SELECT * FROM jobs WHERE status = 'pending' AND (description IS NULL OR description = '') ORDER BY first_seen_at DESC"
        ).fetchall()


def get_pending_deduped() -> list[sqlite3.Row]:
    """Return one row per unique (company, normalized title), preferring rows with
    descriptions, newest first."""
    with _connect() as con:
        return con.execute("""
            SELECT * FROM jobs
            WHERE status = 'pending'
              AND job_id IN (
                SELECT job_id FROM (
                    SELECT
                        job_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY
                                LOWER(TRIM(company)),
                                LOWER(TRIM(REPLACE(REPLACE(REPLACE(title, '-', ' '), '/', ' '), '  ', ' ')))
                            ORDER BY
                                CASE WHEN description IS NOT NULL AND description != '' THEN 0 ELSE 1 END,
                                first_seen_at DESC
                        ) AS rn
                    FROM jobs
                    WHERE status = 'pending'
                ) WHERE rn = 1
              )
            ORDER BY first_seen_at DESC
        """).fetchall()


def get_job(job_id: str) -> sqlite3.Row | None:
    with _connect() as con:
        return con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()


def get_similar_jobs(job_id: str, limit: int = 5) -> list[sqlite3.Row]:
    """Return jobs with the same company OR overlapping title keywords, excluding job_id itself."""
    row = get_job(job_id)
    if not row:
        return []
    company = (dict(row).get("company") or "").strip()
    # Extract first two meaningful words from title for keyword matching
    title_words = [w for w in (dict(row).get("title") or "").lower().split()
                   if len(w) > 3 and w not in ("senior", "junior", "lead", "staff", "principal", "with", "and", "the", "for")]
    kw1 = title_words[0] if len(title_words) > 0 else ""
    kw2 = title_words[1] if len(title_words) > 1 else ""
    with _connect() as con:
        rows = con.execute("""
            SELECT * FROM jobs
            WHERE job_id != ?
              AND (
                (? != '' AND LOWER(TRIM(company)) = LOWER(TRIM(?)))
                OR (? != '' AND LOWER(title) LIKE ?)
                OR (? != '' AND LOWER(title) LIKE ?)
              )
            ORDER BY first_seen_at DESC
            LIMIT ?
        """, (
            job_id,
            company, company,
            kw1, f"%{kw1}%",
            kw2, f"%{kw2}%",
            limit,
        )).fetchall()
    return rows


def stats() -> dict[str, int]:
    with _connect() as con:
        rows = con.execute(
            "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}


def clear_all_jobs() -> None:
    with _connect() as con:
        con.execute("DELETE FROM jobs")
        con.execute("DELETE FROM filter_log")
        con.execute("DELETE FROM fetch_log")
        con.commit()
