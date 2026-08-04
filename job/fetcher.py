from __future__ import annotations
import sys
from dataclasses import dataclass, field
from typing import Callable

from .config import SearchConfig
from .models import RawJob, RemoteType
from .fetcher_utils import infer_remote
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
    # Fallback workplace type when no remote/hybrid keyword is found. Remote-only
    # boards default Remote; general boards default Unknown (don't guess On-site);
    # location-signal boards default On-site only when a location is present
    # (handled in the fetcher itself, so Unknown here).
    remote_default: str = RemoteType.UNKNOWN


# ── Single source of truth for every supported job source ──────────────────────
SOURCE_REGISTRY: list[Source] = [
    Source("linkedin",          "li_",  "fetch_linkedin",          3, describe=linkedin_fetcher.fetch_description),
    Source("jobicy",            "jc_",  "fetch_jobicy",            3, remote_default=RemoteType.REMOTE),
    Source("himalayas",         "hi_",  "fetch_himalayas",         2, remote_default=RemoteType.REMOTE),
    Source("greenhouse",        "gh_",  "fetch_greenhouse",        3, describe=greenhouse_fetcher.fetch_description),
    Source("germantechjobs",    "gtj_", "fetch_germantechjobs",    3),
    Source("berlinstartupjobs", "bsj_", "fetch_berlinstartupjobs", 3),
    Source("stepstone",         "ss_",  "fetch_stepstone",         3, describe=stepstone_fetcher.fetch_description),
    Source("heyjobs",           "hj_",  "fetch_heyjobs",           3),
]

_BY_ID = {s.id: s for s in SOURCE_REGISTRY}
_STEPSTONE_SNIPPET_LIMIT = 500

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


def should_fetch_description(job_id: str, description: str | None) -> bool:
    """True when a stored description is missing or likely only a search-card snippet."""
    text = (description or "").strip()
    if not text:
        return True
    s = _source_for_job_id(job_id)
    return bool(s and s.id == "stepstone" and len(text) < _STEPSTONE_SNIPPET_LIMIT)


def reinfer_remote(job_id: str, title: str, location: str, description: str,
                   current: str) -> str | None:
    """Re-derive the workplace type for a stored job using the corrected,
    per-source logic. Returns the new value if it should change, else None.

    Used by the one-time DB backfill (job.db.init_db) to repair rows that were
    labelled with the old 'default to On-site' bug. Only touches rows whose
    current value looks like that stale default; never overrides a value that a
    real Remote/Hybrid keyword produced.
    """
    s = _source_for_job_id(job_id)
    if s is None:
        return None
    # Keyword evidence in the stored text always wins (this is what the fetchers do).
    kw = infer_remote(title or "", location or "", description or "",
                      default=RemoteType.UNKNOWN)
    if kw != RemoteType.UNKNOWN:
        new = kw
    else:
        # No keyword: apply the source's corrected default. Location-signal
        # boards (greenhouse/stepstone) treat a named location as On-site.
        if s.remote_default == RemoteType.REMOTE:
            new = RemoteType.REMOTE
        elif s.id in ("greenhouse", "stepstone") and (location or "").strip():
            new = RemoteType.ONSITE
        else:
            new = RemoteType.UNKNOWN
    return new if new != current else None


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


# ── Provider registry (Phase 1) ────────────────────────────────────────────────
# Populate the object-based ProviderRegistry from SOURCE_REGISTRY so new code can
# use the JobProvider interface (registry.by_prefix, .with_capability, enable/
# disable) while the legacy exports above keep working unchanged. Each source is
# wrapped in a FunctionProvider that delegates to this module's namespace, so
# test monkeypatching of `fetch_<x>` still flows through.
from .providers import registry, FunctionProvider, ProviderMeta, Capability  # noqa: E402

# Declared capabilities per source. FULL_DESCRIPTION is derived from `describe`;
# the rest reflect what each fetcher actually populates (see docs/PROVIDER_ARCHITECTURE.md).
_CAPS: dict[str, set] = {
    "linkedin":          {Capability.SEARCH_REMOTE_FILTER, Capability.FULL_DESCRIPTION, Capability.POSTED_DATE},
    "jobicy":            {Capability.SALARY_DATA, Capability.POSTED_DATE},
    "himalayas":         {Capability.SALARY_DATA, Capability.POSTED_DATE},
    "greenhouse":        {Capability.POSTED_DATE},
    "germantechjobs":    {Capability.POSTED_DATE},
    "berlinstartupjobs": {Capability.POSTED_DATE},
    "stepstone":         {Capability.FULL_DESCRIPTION},
    "heyjobs":           set(),
}


def _register_sources() -> None:
    for s in SOURCE_REGISTRY:
        if registry.get(s.id):        # idempotent — tolerate module reload
            continue
        caps = set(_CAPS.get(s.id, set()))
        if s.describe:
            caps.add(Capability.FULL_DESCRIPTION)
        meta = ProviderMeta(id=s.id, prefix=s.prefix,
                            default_pages=s.default_pages,
                            capabilities=frozenset(caps))
        # search_fn resolves through this module's namespace at call time, so a
        # test that monkeypatches ft.fetch_linkedin is still honored.
        fn_name = s.fetch_fn
        search_fn = (lambda name: (lambda search: getattr(sys.modules[__name__], name)(search)))(fn_name)
        registry.register(FunctionProvider(meta, search_fn, describe_fn=s.describe))


_register_sources()
