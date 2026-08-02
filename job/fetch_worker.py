from __future__ import annotations

from .db import already_seen, is_duplicate, insert_job, insert_filter_log, log_fetch, init_db
from .config import load_config
from .fetcher import fetch_search
from . import task_state


def _blacklisted(text: str, blacklist: list[str]) -> str | None:
    combined = text.lower()
    for kw in blacklist:
        if kw in combined:
            return kw
    return None


def _should_include_job(job, config) -> tuple[bool, str | None]:
    """Return (True, None) if job passes all filters, else (False, matched_keyword_or_reason).
    Pure — no I/O, no DB access."""
    if job.company and job.company.lower() in config.company_blacklist:
        return False, None
    if config.title_filter and not any(kw in job.title.lower() for kw in config.title_filter):
        return False, None
    kw = _blacklisted(job.title + " " + job.description, config.blacklist)
    if kw:
        return False, kw
    return True, None


def _run_fetch() -> None:
    try:
        init_db()
        config = load_config()
        total_new = 0

        for search in config.searches:
            with task_state._lock:
                task_state._fetch_status["message"] = f"Fetching {search.name}…"

            jobs = fetch_search(search)
            new_count = 0

            for job in jobs:
                if already_seen(job.job_id):
                    continue
                include, kw = _should_include_job(job, config)
                if not include:
                    if kw:
                        insert_filter_log(job.job_id, job.title, kw)
                    continue
                if is_duplicate(job.title, job.company):
                    continue
                insert_job(
                    job_id=job.job_id, url=job.url, title=job.title,
                    company=job.company, location=job.location, remote=job.remote,
                    experience=job.experience, description=job.description,
                    posted_at=job.posted_at, search_name=search.name,
                    employment_type=job.employment_type,
                    salary_range=job.salary_range,
                )
                new_count += 1

            log_fetch(search.source, new_count)
            total_new += new_count

        with task_state._lock:
            task_state._fetch_status["status"] = "done"
            task_state._fetch_status["message"] = f"Done — {total_new} new job(s) found"

    except Exception as e:
        with task_state._lock:
            task_state._fetch_status["status"] = "error"
            task_state._fetch_status["message"] = str(e)
