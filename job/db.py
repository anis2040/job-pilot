from __future__ import annotations
import sqlite3
from datetime import datetime, timezone


def _connect() -> sqlite3.Connection:
    from .profiles import get_db_path
    db_path = get_db_path()
    if not db_path:
        raise RuntimeError("No active profile. Complete setup first.")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _connect() as con:
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
                search_name       TEXT
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
        con.commit()


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
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO jobs
                (job_id, url, title, company, location, remote, experience,
                 description, posted_at, first_seen_at, status, search_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (job_id, url, title, company, location, remote, experience,
             description, posted_at, now, search_name),
        )
        con.commit()


def insert_filter_log(job_id: str, title: str, matched_keyword: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO filter_log (job_id, title, matched_keyword, filtered_at) VALUES (?, ?, ?, ?)",
            (job_id, title, matched_keyword, now),
        )
        con.commit()


def log_fetch(source: str, new_count: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
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


def update_status(job_id: str, status: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
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
