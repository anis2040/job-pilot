import sys

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

# Single source of truth for all supported job sources.
# Each entry: (source_id, default_max_pages)
SOURCES: list[tuple[str, int]] = [
    ("linkedin",          3),
    ("jobicy",            3),
    ("himalayas",         2),
    ("greenhouse",        3),
    ("germantechjobs",    3),
    ("berlinstartupjobs", 3),
    ("stepstone",         3),
]

# Flat imports so callers and tests can monkeypatch via `ft.fetch_linkedin` etc.
from .linkedin_fetcher import fetch_linkedin                    # noqa: E402
from .jobicy_fetcher import fetch_jobicy                        # noqa: E402
from .himalayas_fetcher import fetch_himalayas                  # noqa: E402
from .greenhouse_fetcher import fetch_greenhouse                # noqa: E402
from .germantechjobs_fetcher import fetch_germantechjobs        # noqa: E402
from .berlinstartupjobs_fetcher import fetch_berlinstartupjobs  # noqa: E402
from .stepstone_fetcher import fetch_stepstone                  # noqa: E402
from .heyjobs_fetcher import fetch_heyjobs                      # noqa: E402

_SOURCE_TO_FN = {
    "linkedin":          "fetch_linkedin",
    "jobicy":            "fetch_jobicy",
    "himalayas":         "fetch_himalayas",
    "greenhouse":        "fetch_greenhouse",
    "germantechjobs":    "fetch_germantechjobs",
    "berlinstartupjobs": "fetch_berlinstartupjobs",
    "stepstone":         "fetch_stepstone",
    "heyjobs":           "fetch_heyjobs",
}


def fetch_search(search: SearchConfig) -> list[RawJob]:
    fn_name = _SOURCE_TO_FN.get(search.source)
    if fn_name:
        # Look up via this module's namespace so monkeypatching works in tests.
        return getattr(sys.modules[__name__], fn_name)(search)
    print(f"  Unknown source '{search.source}' — skipping")
    return []

