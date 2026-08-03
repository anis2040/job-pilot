import httpx

from .config import SearchConfig
from .fetcher_utils import http_get, strip_tags, infer_remote, parse_employment_type, parse_salary
from .models import RawJob, RemoteType
from .utils import parse_experience, location_matches


def fetch_himalayas(search: SearchConfig) -> list[RawJob]:
    """Fetch from Himalayas free public API — no key required."""
    results: list[RawJob] = []
    limit = 50
    offset = 0
    pages = search.max_pages if hasattr(search, "max_pages") else 3

    for _ in range(pages):
        try:
            resp = http_get(
                "https://himalayas.app/jobs/api",
                params={"q": search.query, "limit": limit, "offset": offset},
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
            job_id_raw = slug.split("?")[0].rstrip("/").split("/")[-1]
            job_id = f"hi_{job_id_raw}"

            title = item.get("title", "")
            company = item.get("companyName", "")
            location = loc_str if loc_str else "Remote"
            description = strip_tags(item.get("description") or item.get("excerpt") or "")
            seniority = " ".join(item.get("seniority") or [])
            experience = parse_experience(title + " " + seniority + " " + description)
            # Himalayas is a remote-only board — default Remote; Hybrid upgrades on keyword.
            remote = infer_remote(" ".join(restrictions), item.get("employmentType") or "",
                                  default=RemoteType.REMOTE)
            url = item.get("applicationLink") or slug
            employment_type = parse_employment_type(item.get("employmentType") or "")
            salary = parse_salary(item)

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
                employment_type=employment_type,
                salary_range=salary,
            ))

        offset += limit
        if len(jobs) < limit:
            break

    return results


