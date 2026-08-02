from __future__ import annotations
import re
import httpx

from .models import RemoteType

SHARED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-scraper/1.0)",
    "Accept": "application/json",
}


def http_get(url: str, *, headers: dict | None = None, timeout: int = 15, **kwargs) -> httpx.Response:
    """GET url, raising httpx.HTTPError on 4xx/5xx."""
    return httpx.get(url, headers=headers or SHARED_HEADERS, timeout=timeout,
                     follow_redirects=True, **kwargs)


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def infer_remote(*text_fields: str) -> str:
    """Infer remote type from any number of text fields (title, location, description, etc.)."""
    combined = " ".join(t.lower() for t in text_fields if t)
    if "hybrid" in combined:
        return RemoteType.HYBRID
    if "remote" in combined or "homeoffice" in combined or "home office" in combined or "worldwide" in combined or "anywhere" in combined:
        return RemoteType.REMOTE
    return RemoteType.ONSITE
