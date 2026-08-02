import re
import time
import httpx
from bs4 import BeautifulSoup

from .config import SearchConfig
from .fetcher_utils import infer_remote, strip_tags, jsonld_job_description
from .models import RawJob
from .utils import parse_experience, location_matches

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_stepstone(search: SearchConfig) -> list[RawJob]:
    """Fetch from StepStone.de via HTML scraping — no key required."""
    results: list[RawJob] = []
    seen: set[str] = set()
    query_slug = search.query.replace(" ", "-").lower()
    location_slug = search.location.replace(" ", "-").lower() if search.location else ""

    for page in range(1, search.max_pages + 1):
        if location_slug and location_slug not in ("anywhere", "worldwide", "remote"):
            url = f"https://www.stepstone.de/jobs/{query_slug}/in-{location_slug}?page={page}"
        else:
            url = f"https://www.stepstone.de/jobs/{query_slug}?page={page}"

        try:
            resp = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  [StepStone] HTTP error on page {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("article[data-at='job-item']")

        if not cards:
            # Try alternate selectors
            cards = soup.select("article[data-jobid], li[data-at='job-item']")

        if not cards:
            break

        for card in cards:
            job_id_raw = card.get("data-jobid") or card.get("data-at-jobid") or ""
            if not job_id_raw:
                link_el = card.select_one("a[href*='-inline.html'], a[href*='/stellenangebote']")
                if link_el:
                    href = link_el.get("href", "")
                    m = re.search(r"-(\d+)-inline\.html", href)
                    if m:
                        job_id_raw = m.group(1)

            if not job_id_raw:
                continue
            job_id = f"ss_{job_id_raw}"
            if job_id in seen:
                continue
            seen.add(job_id)

            title_el = card.select_one("[data-at='job-item-title'], h2, h3")
            title = title_el.get_text(strip=True) if title_el else ""

            company_el = card.select_one("[data-at='job-item-company-name'], [data-at='job-item-company']")
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one("[data-at='job-item-location']")
            raw_location = location_el.get_text(strip=True) if location_el else search.location

            if not location_matches(raw_location, search.location):
                continue

            link_el = card.select_one("a[data-at='job-item-title'], a[href*='-inline.html']")
            href = link_el.get("href", "") if link_el else ""
            if href and not href.startswith("http"):
                href = "https://www.stepstone.de" + href
            job_url = href or f"https://www.stepstone.de/stellenangebote--{job_id_raw}-inline.html"

            description_el = card.select_one("[data-at='job-item-snippet'], p")
            description = description_el.get_text(strip=True) if description_el else ""

            experience = parse_experience(title + " " + description)
            remote = infer_remote(title, raw_location, description)

            results.append(RawJob(
                job_id=job_id,
                url=job_url,
                title=title,
                company=company,
                location=raw_location,
                remote=remote,
                experience=experience,
                description=description[:2000],
                posted_at=None,
            ))

        if page < search.max_pages:
            time.sleep(2)

    return results


def fetch_description(job_url: str) -> str:
    """Scrape the full description from a StepStone job detail page.

    Prefers the schema.org JobPosting JSON-LD block (stable), then falls back
    to CSS selectors against the rendered ad content.
    """
    if not job_url:
        return ""
    try:
        resp = httpx.get(job_url, headers=_HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError:
        return ""

    soup = BeautifulSoup(resp.text, "lxml")

    # 1. Structured data — most reliable
    desc = jsonld_job_description(soup)
    if desc:
        return desc

    # 2. CSS fallback
    el = soup.select_one(
        "[data-at='job-ad-content'], div.listing-content, "
        "section[class*='job-ad'], article[class*='job-ad']"
    )
    if not el:
        candidates = soup.select("section, article, div.content")
        el = max(candidates, key=lambda e: len(e.get_text()), default=None) if candidates else None
    if not el:
        return ""
    return el.get_text("\n", strip=True)[:4000]
