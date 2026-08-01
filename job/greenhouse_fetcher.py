import time
import httpx

from .config import SearchConfig
from .models import RawJob
from .utils import parse_experience

_BASE = "https://boards-api.greenhouse.io/v1/boards"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-scraper/1.0)",
    "Accept": "application/json",
}

# Well-known companies using Greenhouse that hire for product/BA roles.
# Each entry is the board token found in their careers URL:
# https://boards.greenhouse.io/<token>
DEFAULT_COMPANIES = [
    "airbnb", "stripe", "brex", "gusto", "carta", "figma",
    "lattice", "asana", "zendesk", "hubspot", "twilio",
    "coinbase", "plaid", "chime", "navan", "rippling",
    "benchling", "verkada", "amplitude", "mixpanel",
    "robinhood", "affirm", "faire", "outreach",
]


def fetch_greenhouse(search: SearchConfig) -> list[RawJob]:
    """Fetch jobs from Greenhouse public Job Board API.

    Queries each company's board token and filters by the search query terms.
    No API key required. Rate limits are undocumented but lenient in practice.
    """
    companies = getattr(search, "companies", None) or DEFAULT_COMPANIES
    query_terms = [t.lower() for t in search.query.split()]
    results: list[RawJob] = []
    seen: set[str] = set()

    for token in companies:
        url = f"{_BASE}/{token}/jobs"
        try:
            resp = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  [Greenhouse] {token}: {e}")
            continue

        jobs = resp.json().get("jobs", [])

        for job in jobs:
            title = job.get("title", "")
            if not any(t in title.lower() for t in query_terms):
                continue

            location_name = (job.get("location") or {}).get("name", "")

            # Skip non-US locations
            if location_name and not _is_us(location_name):
                continue

            remote = _infer_remote(location_name)

            # Skip on-site if search is remote-only
            if search.remote and remote == "On-site":
                continue

            job_id = f"gh_{token}_{job['id']}"
            if job_id in seen:
                continue
            seen.add(job_id)

            updated = job.get("updated_at") or job.get("first_published")

            results.append(RawJob(
                job_id=job_id,
                url=job.get("absolute_url", ""),
                title=title,
                company=token.capitalize(),
                location=location_name,
                remote=remote,
                experience=parse_experience(title),
                description="",
                posted_at=updated,
            ))

        time.sleep(0.15)

    return results


def _is_us(location: str) -> bool:
    loc = location.lower()
    us_signals = [
        "united states", ", us", " us,", "(us)", "u.s.",
        ", al", ", ak", ", az", ", ar", ", ca", ", co", ", ct",
        ", dc", ", fl", ", ga", ", hi", ", id", ", il", ", in",
        ", ia", ", ks", ", ky", ", la", ", me", ", md", ", ma",
        ", mi", ", mn", ", ms", ", mo", ", mt", ", ne", ", nv",
        ", nh", ", nj", ", nm", ", ny", ", nc", ", nd", ", oh",
        ", ok", ", or", ", pa", ", ri", ", sc", ", sd", ", tn",
        ", tx", ", ut", ", vt", ", va", ", wa", ", wv", ", wi", ", wy",
        "remote",  # remote with no country restriction — assume US given search context
    ]
    # Explicit non-US signals override
    non_us = ["canada", "brazil", "uk", "united kingdom", "india", "germany",
               "france", "australia", "mexico", "singapore", "ireland", "spain",
               "netherlands", "poland", "hong kong", "japan", "china"]
    if any(n in loc for n in non_us):
        return False
    return any(s in loc for s in us_signals)


def _infer_remote(location: str) -> str:
    loc = location.lower()
    if "hybrid" in loc:
        return "Hybrid"
    if "remote" in loc:
        return "Remote"
    return "On-site"
