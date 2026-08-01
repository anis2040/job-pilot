import re
import httpx

from .config import SearchConfig
from .models import RawJob
from .utils import parse_experience

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-scraper/1.0)",
    "Accept": "application/json",
}


def fetch_jobicy(search: SearchConfig) -> list[RawJob]:
    """Fetch from Jobicy's free public API — no key required."""
    query = search.query.lower().strip()
    params = {
        "count": 50,
        "tag": query,
    }
    if search.location and search.location.lower() not in ("anywhere", "worldwide", ""):
        # Jobicy uses short geo codes: usa, uk, canada, etc.
        params["geo"] = _geo(search.location)

    try:
        resp = httpx.get(
            "https://jobicy.com/api/v2/remote-jobs",
            params=params,
            headers=_HEADERS,
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  [Jobicy] HTTP error: {e}")
        return []

    jobs = resp.json().get("jobs", [])
    results: list[RawJob] = []

    for item in jobs:
        geo = item.get("jobGeo", "") or ""
        if not _is_us_location(geo):
            continue

        job_id = f"jc_{item['id']}"
        title = item.get("jobTitle", "")
        company = item.get("companyName", "")
        job_types = item.get("jobType", [])
        description = _strip_tags(item.get("jobDescription") or item.get("jobExcerpt") or "")
        experience = parse_experience(title + " " + item.get("jobLevel", "") + " " + description)
        remote = _infer_remote(title, job_types, geo)

        results.append(RawJob(
            job_id=job_id,
            url=item.get("url", ""),
            title=title,
            company=company,
            location=geo,
            remote=remote,
            experience=experience,
            description=description[:2000],
            posted_at=item.get("pubDate"),
            salary_min=None,
            salary_max=None,
        ))

    return results


def _is_us_location(geo: str) -> bool:
    if not geo:
        return False
    g = geo.lower()
    return "usa" in g or "united states" in g


def _geo(location: str) -> str:
    loc = location.lower()
    if "united states" in loc or "usa" in loc or "us" == loc:
        return "usa"
    if "united kingdom" in loc or "uk" in loc:
        return "uk"
    if "canada" in loc:
        return "canada"
    if "australia" in loc:
        return "australia"
    return "usa"


def _infer_remote(title: str, job_types: list, geo: str) -> str:
    combined = (title + " " + " ".join(job_types) + " " + geo).lower()
    if "hybrid" in combined:
        return "Hybrid"
    if "remote" in combined or "worldwide" in combined or "anywhere" in combined:
        return "Remote"
    return "On-site"


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()
