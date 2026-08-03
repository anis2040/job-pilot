import re
import time
import httpx
from bs4 import BeautifulSoup

from .config import SearchConfig
from .fetcher_utils import infer_remote
from .models import RawJob, RemoteType
from .utils import parse_experience

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# f_WT=2 = Remote, f_WT=3 = Hybrid, omit for all
_REMOTE_FILTER = "&f_WT=2"


def fetch_linkedin(search: SearchConfig) -> list[RawJob]:
    results: list[RawJob] = []
    query = search.query.replace(" ", "%20")
    location = search.location.replace(" ", "%20")
    remote_param = _REMOTE_FILTER if search.remote else ""

    for page in range(search.max_pages):
        start = page * 25
        url = (
            f"https://www.linkedin.com/jobs/search/?keywords={query}"
            f"&location={location}{remote_param}&start={start}"
        )

        try:
            resp = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  [LinkedIn] HTTP error on page {page + 1}: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div.base-card, li.jobs-search-results__list-item")

        if not cards:
            if "authwall" in resp.url.path.lower() or "login" in resp.text[:300].lower():
                print("  [LinkedIn] Auth wall hit — skipping remaining pages")
                break
            # No cards but no auth wall either — end of results
            break

        for card in cards:
            # LinkedIn uses data-entity-urn or a unique href slug as ID
            urn = card.get("data-entity-urn", "")
            job_id_raw = urn.split(":")[-1] if urn else ""
            if not job_id_raw:
                link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
                href = link_el.get("href", "") if link_el else ""
                m = re.search(r"/jobs/view/(\d+)", href)
                job_id_raw = m.group(1) if m else ""
            if not job_id_raw:
                continue

            job_id = f"li_{job_id_raw}"
            title_el = card.select_one("h3.base-search-card__title, span.sr-only")
            title = title_el.get_text(strip=True) if title_el else ""
            company_el = card.select_one("h4.base-search-card__subtitle a, a.hidden-nested-link")
            company = company_el.get_text(strip=True) if company_el else ""
            location_el = card.select_one("span.job-search-card__location")
            raw_location = location_el.get_text(strip=True) if location_el else ""
            remote = _infer_remote_linkedin(raw_location, card, search.remote)
            experience = parse_experience(title)

            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
            job_url = link_el.get("href", "").split("?")[0] if link_el else f"https://www.linkedin.com/jobs/view/{job_id_raw}"

            # posted_at — LinkedIn embeds a <time datetime="..."> in each card
            time_el = card.select_one("time")
            posted_at = time_el.get("datetime") if time_el else None

            results.append(RawJob(
                job_id=job_id,
                url=job_url,
                title=title,
                company=company,
                location=raw_location,
                remote=remote,
                experience=experience,
                description="",   # fetched lazily on detail page view
                posted_at=posted_at,
            ))

        if page < search.max_pages - 1:
            time.sleep(2)

    return results


def fetch_description(job_url: str) -> str:
    """Fetch the full job description from a LinkedIn job page."""
    try:
        resp = httpx.get(job_url, headers=_HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError:
        return ""

    soup = BeautifulSoup(resp.text, "lxml")
    # Prefer the inner markup container (content only). The outer
    # section.show-more-less-html also contains the "Show more"/"Show less"
    # toggle buttons, whose text would otherwise leak into the description.
    el = soup.select_one("div.show-more-less-html__markup, div.description__text, section.show-more-less-html")
    if not el:
        return ""
    # Drop any toggle buttons that live inside the container.
    for btn in el.select("button, .show-more-less-html__button"):
        btn.decompose()
    text = el.get_text("\n", strip=True)
    return _strip_show_toggle(text)[:4000]


def _strip_show_toggle(text: str) -> str:
    """Remove LinkedIn's 'Show more'/'Show less' toggle labels that leak into
    scraped text as standalone lines."""
    lines = [ln for ln in text.split("\n")
             if ln.strip().lower() not in ("show more", "show less")]
    return "\n".join(lines).strip()


def _infer_remote_linkedin(location: str, card, search_is_remote: bool) -> str:
    """Determine workplace type for a LinkedIn search-result card.

    LinkedIn's public search cards usually omit the workplace type, so a plain
    keyword check would mislabel everything 'On-site'. Instead:
      - if the card/location does state Remote/Hybrid, trust it;
      - else if the search itself applied the remote filter (f_WT=2), it's Remote;
      - else Unknown (we genuinely don't know — the detail page backfills it
        from the full description when opened)."""
    badge = card.select_one("span.job-search-card__benefits-item, span[class*='remote']")
    badge_text = badge.get_text(strip=True) if badge else ""
    explicit = infer_remote(location, badge_text, default=RemoteType.UNKNOWN)
    if explicit != RemoteType.UNKNOWN:
        return explicit
    return RemoteType.REMOTE if search_is_remote else RemoteType.UNKNOWN
