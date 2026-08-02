from .config import SearchConfig
from .models import RawJob


def fetch_heyjobs(search: SearchConfig) -> list[RawJob]:
    """HeyJobs requires authentication for its job listing API — not scrapeable without login.

    The site's search is fully client-side; the Next.js __NEXT_DATA__ payload contains
    only user session state, not job listings. The underlying API at api.heyjobs.co
    returns 401 without a session token. This source is kept registered but always
    returns an empty list until an official public API becomes available.
    """
    print("  [HeyJobs] Skipped — requires authentication (no public API available)")
    return []
