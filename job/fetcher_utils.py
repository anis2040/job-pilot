from __future__ import annotations
import json
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


def infer_remote(*text_fields: str, default: str = RemoteType.ONSITE) -> str:
    """Infer remote type from any number of text fields (title, location, description…).

    Returns Hybrid/Remote when those keywords appear. When there is NO signal,
    returns `default` — pass default=RemoteType.UNKNOWN when the absence of a
    keyword doesn't reliably mean on-site (e.g. LinkedIn search cards omit the
    workplace type entirely, so guessing 'On-site' would be wrong)."""
    combined = " ".join(t.lower() for t in text_fields if t)
    if "hybrid" in combined:
        return RemoteType.HYBRID
    if "remote" in combined or "homeoffice" in combined or "home office" in combined or "worldwide" in combined or "anywhere" in combined:
        return RemoteType.REMOTE
    if "on-site" in combined or "on site" in combined or "onsite" in combined:
        return RemoteType.ONSITE
    return default


def jsonld_job_description(soup) -> str:
    """Extract description from a schema.org JobPosting JSON-LD block, if present.

    Most modern job boards (StepStone, LinkedIn, many ATS) embed a
    <script type="application/ld+json"> JobPosting object whose `description`
    field holds the full listing — far more stable than CSS selectors.
    Returns cleaned plain text, or "" if not found.
    """
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        # JSON-LD may be a single object, a list, or a @graph container
        candidates = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                desc = item.get("description") or ""
                if desc:
                    return strip_tags(desc)[:4000]
    return ""

