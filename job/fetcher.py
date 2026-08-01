from .config import SearchConfig
from .models import RawJob
from .linkedin_fetcher import fetch_linkedin
from .jobicy_fetcher import fetch_jobicy
from .himalayas_fetcher import fetch_himalayas
from .greenhouse_fetcher import fetch_greenhouse


def fetch_search(search: SearchConfig) -> list[RawJob]:
    if search.source == "linkedin":
        return fetch_linkedin(search)
    if search.source == "jobicy":
        return fetch_jobicy(search)
    if search.source == "himalayas":
        return fetch_himalayas(search)
    if search.source == "greenhouse":
        return fetch_greenhouse(search)
    print(f"  Unknown source '{search.source}' — skipping")
    return []
