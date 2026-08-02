import sys
from dataclasses import dataclass
from typing import Callable

from .config import SearchConfig
from .models import RawJob
from . import linkedin_fetcher
from . import jobicy_fetcher
from . import himalayas_fetcher
from . import greenhouse_fetcher
from . import germantechjobs_fetcher
from . import berlinstartupjobs_fetcher
from . import stepstone_fetcher
from . import heyjobs_fetcher

# Flat imports so callers and tests can monkeypatch via `ft.fetch_linkedin` etc.
from .linkedin_fetcher import fetch_linkedin                    # noqa: E402
from .jobicy_fetcher import fetch_jobicy                        # noqa: E402
from .himalayas_fetcher import fetch_himalayas                  # noqa: E402
from .greenhouse_fetcher import fetch_greenhouse                # noqa: E402
from .germantechjobs_fetcher import fetch_germantechjobs        # noqa: E402
from .berlinstartupjobs_fetcher import fetch_berlinstartupjobs  # noqa: E402
from .stepstone_fetcher import fetch_stepstone                  # noqa: E402
from .heyjobs_fetcher import fetch_heyjobs                      # noqa: E402


@dataclass(frozen=True)
class Source:
    """One job source and everything the app needs to know about it.

    Adding a source (or giving an existing one a new capability) means editing
    THIS list only — dispatch, config generation, the UI source list, and the
    on-demand description fetch all read from here.
    """
    id: str                       # source key used in SearchConfig.source
    prefix: str                   # job_id prefix, e.g. "li_" — used to resolve a job's source
    fetch_fn: str                 # name of the list-fetch function in this module's namespace
    default_pages: int = 3
    # Optional: scrape a single job's full description on demand from its URL.
    # None means the source already stores full descriptions at fetch time.
    describe: Callable[[str], str] | None = None


# ── Single source of truth for every supported job source ──────────────────────
SOURCE_REGISTRY: list[Source] = [
    Source("linkedin",          "li_",  "fetch_linkedin",          3, describe=linkedin_fetcher.fetch_description),
    Source("jobicy",            "jc_",  "fetch_jobicy",            3),
    Source("himalayas",         "hi_",  "fetch_himalayas",         2),
    Source("greenhouse",        "gh_",  "fetch_greenhouse",        3),
    Source("germantechjobs",    "gtj_", "fetch_germantechjobs",    3),
    Source("berlinstartupjobs", "bsj_", "fetch_berlinstartupjobs", 3),
    Source("stepstone",         "ss_",  "fetch_stepstone",         3, describe=stepstone_fetcher.fetch_description),
    Source("heyjobs",           "hj_",  "fetch_heyjobs",           3),
]

_BY_ID = {s.id: s for s in SOURCE_REGISTRY}

# ── Backwards-compatible derived views ─────────────────────────────────────────
# (id, default_pages) tuples — consumed by web.py and the config generator.
SOURCES: list[tuple[str, int]] = [(s.id, s.default_pages) for s in SOURCE_REGISTRY]
# id -> fetch-function-name — kept for tests that patch via this map.
_SOURCE_TO_FN: dict[str, str] = {s.id: s.fetch_fn for s in SOURCE_REGISTRY}


def _source_for_job_id(job_id: str) -> Source | None:
    """Resolve which source a stored job belongs to, by its id prefix."""
    for s in SOURCE_REGISTRY:
        if job_id.startswith(s.prefix):
            return s
    return None


def fetch_search(search: SearchConfig) -> list[RawJob]:
    fn_name = _SOURCE_TO_FN.get(search.source)
    if fn_name:
        # Look up via this module's namespace so monkeypatching works in tests.
        return getattr(sys.modules[__name__], fn_name)(search)
    print(f"  Unknown source '{search.source}' — skipping")
    return []


def source_can_describe(job_id: str) -> bool:
    """True if this job's source supports on-demand full-description scraping."""
    s = _source_for_job_id(job_id)
    return bool(s and s.describe)


def fetch_description(job_id: str, job_url: str) -> str:
    """Scrape a job's full description on demand, dispatching to its source.

    Returns "" if the source is unknown, has no describe capability, the URL is
    empty, or the scrape fails. Works for every source that declares `describe`
    in SOURCE_REGISTRY — no per-source branching at the call site.
    """
    if not job_url:
        return ""
    s = _source_for_job_id(job_id)
    if not s or not s.describe:
        return ""
    try:
        return s.describe(job_url) or ""
    except Exception:
        return ""
