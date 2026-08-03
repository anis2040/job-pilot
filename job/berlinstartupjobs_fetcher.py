import httpx

from .config import SearchConfig
from .fetcher_utils import http_get, strip_tags, infer_remote
from .models import RawJob, RemoteType
from .utils import parse_experience, location_matches

_API_BASE = "https://berlinstartupjobs.com/wp-json/wp/v2/posts"


def fetch_berlinstartupjobs(search: SearchConfig) -> list[RawJob]:
    """Fetch from Berlin Startup Jobs via WordPress REST API — no key required."""
    query_terms = [t.lower() for t in search.query.split()]
    results: list[RawJob] = []
    page = 1
    max_pages = search.max_pages if hasattr(search, "max_pages") else 3

    while page <= max_pages:
        try:
            resp = http_get(
                _API_BASE,
                params={"per_page": 100, "page": page, "search": search.query},
            )
            if resp.status_code == 400:
                break
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  [BerlinStartupJobs] HTTP error on page {page}: {e}")
            break

        posts = resp.json()
        if not posts:
            break

        for post in posts:
            title = strip_tags(post.get("title", {}).get("rendered", ""))
            content_html = post.get("content", {}).get("rendered", "")
            description = strip_tags(content_html)
            url = post.get("link", "")
            pub_date = post.get("date", "")
            job_id = f"bsj_{post['id']}"

            if query_terms and not any(t in title.lower() or t in description.lower() for t in query_terms):
                continue

            # BSJ is Berlin-only — skip if search explicitly excludes Germany
            location = "Berlin, Germany"
            if not location_matches(location, search.location):
                continue

            company = _extract_company(title, description)
            experience = parse_experience(title + " " + description)
            remote = infer_remote(title, description, default=RemoteType.UNKNOWN)

            results.append(RawJob(
                job_id=job_id,
                url=url,
                title=title,
                company=company,
                location=location,
                remote=remote,
                experience=experience,
                description=description[:2000],
                posted_at=pub_date or None,
            ))

        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break
        page += 1

    return results


def _extract_company(title: str, description: str) -> str:
    """Best-effort: look for 'at CompanyName' in title or first line of description."""
    import re
    m = re.search(r"\bat\s+([A-Z][^\n,–\-]{2,40})", title)
    if m:
        return m.group(1).strip()
    first_line = description.split("\n")[0][:120]
    m = re.search(r"\bat\s+([A-Z][^\n,–\-]{2,40})", first_line)
    if m:
        return m.group(1).strip()
    return ""
