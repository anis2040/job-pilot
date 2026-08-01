import re
import httpx

from .config import SearchConfig
from .models import RawJob
from .utils import parse_experience, location_matches

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-scraper/1.0)",
    "Accept": "application/json",
}


def fetch_himalayas(search: SearchConfig) -> list[RawJob]:
    """Fetch from Himalayas free public API — no key required."""
    results: list[RawJob] = []
    limit = 50
    offset = 0
    pages = search.max_pages if hasattr(search, "max_pages") else 3

    for _ in range(pages):
        try:
            resp = httpx.get(
                "https://himalayas.app/jobs/api",
                params={"q": search.query, "limit": limit, "offset": offset},
                headers=_HEADERS,
                timeout=15,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  [Himalayas] HTTP error: {e}")
            break

        jobs = resp.json().get("jobs", [])
        if not jobs:
            break

        for item in jobs:
            restrictions = item.get("locationRestrictions") or []
            loc_str = ", ".join(restrictions) if restrictions else ""

            # Filter by configured location
            if restrictions and not location_matches(loc_str, search.location):
                continue

            slug = item.get("guid") or item.get("applicationLink") or ""
            job_id_raw = slug.rstrip("/").split("/")[-1]
            job_id = f"hi_{job_id_raw}"

            title = item.get("title", "")
            company = item.get("companyName", "")
            location = loc_str if loc_str else "Remote"
            description = _strip_tags(item.get("description") or item.get("excerpt") or "")
            seniority = " ".join(item.get("seniority") or [])
            experience = parse_experience(title + " " + seniority + " " + description)
            remote = _infer_remote(item)
            url = item.get("applicationLink") or slug

            results.append(RawJob(
                job_id=job_id,
                url=url,
                title=title,
                company=company,
                location=location,
                remote=remote,
                experience=experience,
                description=description[:2000],
                posted_at=str(item["pubDate"]) if item.get("pubDate") else None,
                salary_min=item.get("minSalary"),
                salary_max=item.get("maxSalary"),
            ))

        offset += limit
        if len(jobs) < limit:
            break

    return results


def _infer_remote(item: dict) -> str:
    restrictions = item.get("locationRestrictions") or []
    emp = (item.get("employmentType") or "").lower()
    loc_text = " ".join(restrictions).lower()
    if "hybrid" in emp or "hybrid" in loc_text:
        return "Hybrid"
    # Himalayas is a remote job board — all listed jobs are remote
    return "Remote"


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()
