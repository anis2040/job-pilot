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


def _matches_work_styles(job, search) -> bool:
    styles = getattr(search, "work_styles", None) or []
    if not styles:
        return True
    return (job.remote or "") in styles


def _run_fetch() -> None:
    try:
        init_db()
        config = load_config()
        total_new = 0

        for search in config.searches:
            task_state.set_fetch_message(f"Fetching {search.name}…")

            jobs = fetch_search(search)
            new_count = 0

            for job in jobs:
                if already_seen(job.job_id):
                    continue
                if not _matches_work_styles(job, search):
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

        # Backfill semantic embeddings for the newly-fetched jobs (best-effort,
        # off the render path). Batched; a failure here must never fail the fetch.
        if total_new:
            try:
                _backfill_embeddings()
            except Exception:
                pass

        task_state.set_fetch_done(f"Done — {total_new} new job(s) found")

    except Exception as e:
        task_state.set_fetch_error(str(e))


def _backfill_embeddings(batch: int = 100) -> None:
    """Embed pending jobs that lack an embedding, in batches, and cache them.
    Only runs when a Gemini key is available (embed_texts returns None-list
    otherwise). Uses match_text (title + description) for consistency with the
    keyword signal."""
    from .db import get_jobs_missing_embedding, set_job_embedding
    from .ai_providers import embed_texts
    from .match import match_text, semantic_enabled

    if not semantic_enabled():
        return  # user turned semantic matching off (or no embedding provider)
    rows = get_jobs_missing_embedding(limit=batch)
    if not rows:
        return
    texts = [match_text(r) for r in rows]
    vecs = embed_texts(texts)
    for r, vec in zip(rows, vecs):
        if vec:
            set_job_embedding(r["job_id"], vec)
