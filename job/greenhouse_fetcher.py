import re
import time
import httpx

from .config import SearchConfig
from .fetcher_utils import SHARED_HEADERS, http_get, infer_remote, strip_tags, clip_description, FULL_DESC_LIMIT
from .models import RawJob, RemoteType
from .utils import parse_experience, location_matches

_BASE = "https://boards-api.greenhouse.io/v1/boards"

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
            resp = http_get(url, headers=SHARED_HEADERS, timeout=10)
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

            # Skip locations that don't match the configured search location
            if location_name and not location_matches(location_name, search.location):
                continue

            # Greenhouse location is a real signal: "Remote"/"Hybrid" keywords win,
            # a named office location means On-site, and only a blank location is Unknown.
            remote = infer_remote(location_name,
                                  default=RemoteType.ONSITE if location_name.strip() else RemoteType.UNKNOWN)

            # Skip on-site if search is remote-only
            if search.remote and remote == RemoteType.ONSITE:
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


def fetch_description(job_url: str, *, job_id: str | None = None) -> str:
    """Fetch a Greenhouse job's full description on demand via its JSON API.

    The board API returns clean structured content, so we derive the board token
    and job id from the public URL (boards.greenhouse.io/<token>/jobs/<id>) and
    hit boards-api.greenhouse.io — more reliable than scraping HTML. Returns ""
    on any error (matches the other providers' describe fns).
    """
    if not job_url:
        return ""
    m = re.match(r"^gh_(.+)_(\d+)$", job_id or "")
    if m:
        token, job_id = m.group(1), m.group(2)
    else:
        token = None

    m = None if token else re.search(r"greenhouse\.io/(?:embed/job_app\?for=|)?([\w-]+)/jobs/(\d+)", job_url)
    if not m:
        m = None if token else re.search(r"greenhouse\.io/([\w-]+).*?[?&]gh_jid=(\d+)", job_url)
    if not m:
        if not token:
            return ""
    if m:
        token, job_id = m.group(1), m.group(2)
    try:
        resp = http_get(f"{_BASE}/{token}/jobs/{job_id}", headers=SHARED_HEADERS, timeout=10)
        resp.raise_for_status()
        content = resp.json().get("content") or ""
    except (httpx.HTTPError, ValueError):
        return ""
    # Greenhouse `content` is HTML-escaped HTML; unescape then strip tags.
    import html
    return clip_description(strip_tags(html.unescape(content)), FULL_DESC_LIMIT)
