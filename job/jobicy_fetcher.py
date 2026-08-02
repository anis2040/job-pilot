import httpx

from .config import SearchConfig
from .fetcher_utils import http_get, strip_tags, infer_remote
from .models import RawJob
from .utils import parse_experience, location_matches


def fetch_jobicy(search: SearchConfig) -> list[RawJob]:
    """Fetch from Jobicy's free public API — no key required."""
    query = search.query.lower().strip()
    params = {
        "count": 50,
        "tag": query,
    }
    geo_code = _geo(search.location)
    if geo_code:
        params["geo"] = geo_code

    try:
        resp = http_get(
            "https://jobicy.com/api/v2/remote-jobs",
            params=params,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  [Jobicy] HTTP error: {e}")
        return []

    jobs = resp.json().get("jobs", [])
    results: list[RawJob] = []

    for item in jobs:
        geo = item.get("jobGeo", "") or ""
        if not location_matches(geo, search.location):
            continue

        job_id = f"jc_{item['id']}"
        title = item.get("jobTitle", "")
        company = item.get("companyName", "")
        job_types = item.get("jobType", [])
        description = strip_tags(item.get("jobDescription") or item.get("jobExcerpt") or "")
        experience = parse_experience(title + " " + item.get("jobLevel", "") + " " + description)
        remote = infer_remote(title, " ".join(job_types), geo)
        employment_type = _parse_employment_type(job_types)
        salary = _parse_salary(item)

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
            employment_type=employment_type,
            salary_range=salary,
        ))

    return results


def _geo(location: str) -> str:
    """Map search.location to Jobicy's geo code, or empty string for worldwide."""
    if not location:
        return ""
    loc = location.lower()
    if "united states" in loc or "usa" in loc or loc == "us":
        return "usa"
    if "united kingdom" in loc or "uk" in loc:
        return "uk"
    if "canada" in loc:
        return "canada"
    if "australia" in loc:
        return "australia"
    if "germany" in loc:
        return "germany"
    if "france" in loc:
        return "france"
    if "netherlands" in loc:
        return "netherlands"
    if "spain" in loc:
        return "spain"
    if "india" in loc:
        return "india"
    if "singapore" in loc:
        return "singapore"
    # For unrecognised locations, don't pass a geo filter — let location_matches handle it
    return ""


def _parse_employment_type(job_types: list) -> str:
    mapping = {"full-time": "Full-time", "fulltime": "Full-time",
               "part-time": "Part-time", "parttime": "Part-time",
               "contract": "Contract", "freelance": "Freelance",
               "internship": "Internship"}
    for jt in job_types:
        key = jt.lower().replace(" ", "")
        if key in mapping:
            return mapping[key]
    return ""


def _parse_salary(item: dict) -> str:
    low = item.get("salaryMin") or item.get("salary_min") or 0
    high = item.get("salaryMax") or item.get("salary_max") or 0
    currency = item.get("salaryCurrency") or "$"
    if low and high:
        return f"{currency}{int(low):,}–{currency}{int(high):,}"
    if low:
        return f"{currency}{int(low):,}+"
    return ""
