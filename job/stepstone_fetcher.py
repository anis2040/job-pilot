import re
import time
import httpx
from bs4 import BeautifulSoup

from .config import SearchConfig
from .fetcher_utils import FULL_DESC_LIMIT, infer_remote, clip_description, jsonld_job_description, strip_tags
from .models import RawJob, RemoteType
from .utils import parse_experience, location_matches

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_DESCRIPTION_SELECTORS = (
    "[data-at='job-ad-content']",
    "[data-at='job-ad-description']",
    "[data-at='job-description']",
    "[data-at='job-item-description']",
    "[data-testid='job-description']",
    "[data-testid='jobDescription']",
    "#job-description",
    "#jobDescription",
    "section[class*='job-description']",
    "div[class*='job-description']",
    "section[class*='JobDescription']",
    "div[class*='JobDescription']",
)


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

            description_el = card.select_one(
                "[data-at='jobcard-content'], [data-at='job-item-snippet'], p"
            )
            description = description_el.get_text(" ", strip=True) if description_el else ""

            experience = parse_experience(title + " " + description)
            # A named StepStone location is an On-site signal; remote/hybrid keywords win.
            remote = infer_remote(title, raw_location, description,
                                  default=RemoteType.ONSITE if (raw_location or "").strip() else RemoteType.UNKNOWN)

            results.append(RawJob(
                job_id=job_id,
                url=job_url,
                title=title,
                company=company,
                location=raw_location,
                remote=remote,
                experience=experience,
                description=clip_description(description),
                posted_at=None,
            ))

        if page < search.max_pages:
            time.sleep(2)

    return results


def fetch_description(job_url: str, *, job_id: str | None = None) -> str:
    """Fetch the full description from a StepStone detail page.

    StepStone often embeds the full posting as schema.org JobPosting JSON-LD,
    which is more stable than CSS selectors and works for German descriptions.
    Selector fallbacks cover pages where the structured block is absent.
    """
    if not job_url:
        return ""
    try:
        resp = httpx.get(job_url, headers=_HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError:
        return ""

    soup = BeautifulSoup(resp.text, "lxml")
    description = jsonld_job_description(soup)
    if description:
        return description
    return _description_from_detail_markup(soup)


def _description_from_detail_markup(soup: BeautifulSoup) -> str:
    candidates: list[str] = []
    for selector in _DESCRIPTION_SELECTORS:
        for el in soup.select(selector):
            for noisy in el.select("script, style, noscript, svg, form, button, nav, header, footer, aside"):
                noisy.decompose()
            text = clip_description(strip_tags(str(el)), FULL_DESC_LIMIT)
            if len(text) >= 80:
                candidates.append(text)
    return max(candidates, key=len) if candidates else ""
