import xml.etree.ElementTree as ET
import httpx

from .config import SearchConfig
from .fetcher_utils import http_get, strip_tags, infer_remote
from .models import RawJob
from .utils import parse_experience, location_matches

_RSS_URL = "https://germantechjobs.de/rss"
_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}


def fetch_germantechjobs(search: SearchConfig) -> list[RawJob]:
    """Fetch from GermanTechJobs RSS feed — no key required."""
    try:
        resp = http_get(_RSS_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; job-scraper/1.0)", "Accept": "application/rss+xml,application/xml,*/*"})
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  [GermanTechJobs] HTTP error: {e}")
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        print(f"  [GermanTechJobs] XML parse error: {e}")
        return []

    query_terms = [t.lower() for t in search.query.split()]
    results: list[RawJob] = []

    for item in root.iter("item"):
        title = _text(item, "title")
        link = _text(item, "link")
        pub_date = _text(item, "pubDate")
        description_raw = _text(item, "description")
        content_raw = item.find("content:encoded", _NS)
        full_text = strip_tags(content_raw.text if content_raw is not None and content_raw.text else description_raw)

        # Extract company and location from title — format is usually "Title at Company (City)"
        company, location = _parse_title_meta(title)

        if not location_matches(location, search.location):
            continue

        if query_terms and not any(t in title.lower() or t in full_text.lower() for t in query_terms):
            continue

        job_id_raw = link.rstrip("/").split("/")[-1]
        job_id = f"gtj_{job_id_raw}"
        experience = parse_experience(title + " " + full_text)
        remote = infer_remote(title, full_text, location)

        results.append(RawJob(
            job_id=job_id,
            url=link,
            title=title,
            company=company,
            location=location or "Germany",
            remote=remote,
            experience=experience,
            description=full_text[:2000],
            posted_at=pub_date or None,
        ))

    return results


def _text(element, tag: str) -> str:
    el = element.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _parse_title_meta(title: str) -> tuple[str, str]:
    """Extract (company, location) from RSS title like 'Senior Dev at Acme (Berlin)'."""
    import re
    location = ""
    company = ""

    loc_m = re.search(r"\(([^)]+)\)\s*$", title)
    if loc_m:
        location = loc_m.group(1).strip()

    at_m = re.search(r"\bat\s+(.+?)(?:\s*\(|$)", title)
    if at_m:
        company = at_m.group(1).strip()

    return company, location
