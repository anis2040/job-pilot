from __future__ import annotations
import html as _html
import json
import re
import httpx

from .models import RemoteType

SHARED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-scraper/1.0)",
    "Accept": "application/json",
}

# Description length cap. 0 means uncapped — store the full text.
LIST_DESC_LIMIT = 0
FULL_DESC_LIMIT = 0


def clip_description(text: str, limit: int = LIST_DESC_LIMIT) -> str:
    """Cap a description to `limit` characters (0/None → ""). Centralises the
    length policy so it isn't a magic number scattered across every fetcher."""
    if not text:
        return ""
    return text[:limit] if limit else text


def http_get(url: str, *, headers: dict | None = None, timeout: int = 15, **kwargs) -> httpx.Response:
    """GET url, raising httpx.HTTPError on 4xx/5xx."""
    return httpx.get(url, headers=headers or SHARED_HEADERS, timeout=timeout,
                     follow_redirects=True, **kwargs)


def strip_tags(html: str) -> str:
    """Convert scraped HTML to clean plain text, preserving structure.

    Unescapes HTML entities (so '&amp;' -> '&'), turns block/break/list tags into
    newlines and list items into '• ' bullets BEFORE removing remaining tags, then
    normalizes whitespace. Safe on plain strings and titles (no block tags -> no
    injected newlines). Used by every provider + the match/resume consumers.
    """
    if not html:
        return ""
    s = html
    # List items -> bulleted lines (the leading newline separates them; don't
    # also break on </li> or we'd double-space bullets).
    s = re.sub(r"<li[^>]*>", "\n• ", s, flags=re.I)
    # Block/line-break tags -> newlines.
    s = re.sub(r"<(br|/p|/div|/h[1-6]|/tr)[^>]*>", "\n", s, flags=re.I)
    # Remove all remaining tags.
    s = re.sub(r"<[^>]+>", " ", s)
    # Decode entities after tag removal.
    s = _html.unescape(s)
    # Normalize non-breaking spaces, collapse runs of spaces/tabs (not newlines),
    # trim per-line, collapse 3+ newlines to a paragraph break.
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


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
                    return clip_description(strip_tags(desc), FULL_DESC_LIMIT)
    return ""


_EMPLOYMENT_MAP = {
    "full-time": "Full-time", "fulltime": "Full-time",
    "part-time": "Part-time", "parttime": "Part-time",
    "contract": "Contract", "freelance": "Freelance", "internship": "Internship",
}


def parse_employment_type(value: str | list) -> str:
    """Normalise a raw employment-type string or list of strings to a canonical
    label (e.g. "full-time" → "Full-time"). Returns "" when unrecognised."""
    if isinstance(value, list):
        for item in value:
            result = parse_employment_type(item)
            if result:
                return result
        return ""
    key = str(value or "").lower().replace(" ", "")
    return _EMPLOYMENT_MAP.get(key, "")


def parse_salary(item: dict, *,
                 min_keys: tuple = ("salaryMin", "minSalary", "salary_min"),
                 max_keys: tuple = ("salaryMax", "maxSalary", "salary_max"),
                 currency_keys: tuple = ("salaryCurrency", "currency"),
                 period_key: str = "salaryPeriod") -> str:
    """Build a human-readable salary range from a job-data dict.

    Works across providers by accepting a union of key names. Returns "" when
    no salary data is present.
    """
    def _first(keys):
        for k in keys:
            v = item.get(k)
            if v:
                return v
        return 0

    low = _first(min_keys)
    high = _first(max_keys)
    currency = _first(currency_keys) or "$"
    period = item.get(period_key) or ""
    if low and high:
        suffix = f"/{period}" if period else ""
        return f"{currency}{int(low):,}–{currency}{int(high):,}{suffix}"
    if low:
        return f"{currency}{int(low):,}+"
    return ""

