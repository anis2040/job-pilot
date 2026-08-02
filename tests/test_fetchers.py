"""Smoke tests for the four job-source fetchers and the fetch router.

All tests run fully offline — no network calls. Each fetcher's HTTP layer is
monkeypatched with a minimal FakeResponse carrying a realistic fixture payload.
"""
import pytest

from job.config import SearchConfig
from job.fetcher import fetch_search


class FakeResponse:
    def __init__(self, data=None, text="", status_code=200):
        self._data = data
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


@pytest.fixture
def search():
    return SearchConfig(
        name="test",
        source="test",
        query="engineer",
        location="United States",
        remote=True,
        max_pages=1,
    )


# ── LinkedIn ──────────────────────────────────────────────────────────────────

_LINKEDIN_HTML = """
<html><body>
<div class="base-card" data-entity-urn="urn:li:jobPosting:123456">
  <h3 class="base-search-card__title">Senior Engineer</h3>
  <h4 class="base-search-card__subtitle">
    <a class="hidden-nested-link">Acme Corp</a>
  </h4>
  <span class="job-search-card__location">Remote</span>
  <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123456"></a>
</div>
</body></html>
"""


def test_linkedin_fetcher_parses_html(monkeypatch, search):
    import job.linkedin_fetcher as lf

    search.source = "linkedin"
    monkeypatch.setattr(lf.httpx, "get", lambda *a, **kw: FakeResponse(text=_LINKEDIN_HTML))

    results = lf.fetch_linkedin(search)

    assert len(results) == 1
    job = results[0]
    assert job.job_id == "li_123456"
    assert job.company == "Acme Corp"
    assert job.title == "Senior Engineer"
    assert job.remote == "Remote"


# ── Jobicy ────────────────────────────────────────────────────────────────────

_JOBICY_JSON = {
    "jobs": [
        {
            "id": 789,
            "jobTitle": "Product Manager",
            "companyName": "StartupX",
            "jobGeo": "USA",
            "jobType": ["remote"],
            "jobDescription": "<p>Great job opportunity</p>",
            "url": "https://jobicy.com/jobs/789",
            "pubDate": "2024-01-15",
        }
    ]
}


def test_jobicy_fetcher_parses_json(monkeypatch, search):
    import job.jobicy_fetcher as jf

    search.source = "jobicy"
    monkeypatch.setattr(jf, "http_get", lambda *a, **kw: FakeResponse(data=_JOBICY_JSON))

    results = jf.fetch_jobicy(search)

    assert len(results) == 1
    job = results[0]
    assert job.job_id == "jc_789"
    assert job.company == "StartupX"
    assert "Great job opportunity" in job.description
    assert "<p>" not in job.description  # HTML stripped


# ── Himalayas ─────────────────────────────────────────────────────────────────

_HIMALAYAS_JSON = {
    "jobs": [
        {
            "guid": "https://himalayas.app/companies/acme/jobs/backend-engineer",
            "title": "Backend Engineer",
            "companyName": "Acme",
            "locationRestrictions": ["United States"],
            "description": "<b>Build great things</b>",
            "applicationLink": "https://apply.acme.com/backend-engineer",
            "seniority": ["Mid"],
            "pubDate": 1705276800,
        }
    ]
}


def test_himalayas_fetcher_parses_json(monkeypatch, search):
    import job.himalayas_fetcher as hf

    search.source = "himalayas"
    monkeypatch.setattr(hf, "http_get", lambda *a, **kw: FakeResponse(data=_HIMALAYAS_JSON))

    results = hf.fetch_himalayas(search)

    assert len(results) == 1
    job = results[0]
    assert job.job_id == "hi_backend-engineer"
    assert job.company == "Acme"
    assert job.location == "United States"
    assert "Build great things" in job.description
    assert "<b>" not in job.description  # HTML stripped


# ── Greenhouse ────────────────────────────────────────────────────────────────

_GREENHOUSE_JSON = {
    "jobs": [
        {
            "id": 456,
            "title": "Product Manager",
            "location": {"name": "Remote - US"},
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/456",
            "updated_at": "2024-01-10T12:00:00Z",
        }
    ]
}


def test_greenhouse_fetcher_parses_json(monkeypatch, search):
    import job.greenhouse_fetcher as gf

    search.source = "greenhouse"
    search.query = "product"
    search.companies = ["acme"]
    monkeypatch.setattr(gf, "http_get", lambda *a, **kw: FakeResponse(data=_GREENHOUSE_JSON))

    results = gf.fetch_greenhouse(search)

    assert len(results) == 1
    job = results[0]
    assert job.job_id == "gh_acme_456"
    assert job.company == "Acme"
    assert job.remote == "Remote"


def test_greenhouse_title_filter_excludes_non_matching(monkeypatch, search):
    """Jobs whose title doesn't match the query terms are dropped."""
    import job.greenhouse_fetcher as gf

    search.source = "greenhouse"
    search.query = "engineer"  # won't match "Product Manager"
    search.companies = ["acme"]
    monkeypatch.setattr(gf, "http_get", lambda *a, **kw: FakeResponse(data=_GREENHOUSE_JSON))

    results = gf.fetch_greenhouse(search)
    assert results == []


# ── Router ────────────────────────────────────────────────────────────────────

def test_router_dispatches_to_linkedin(monkeypatch, search):
    from job import fetcher as ft
    from job.models import RawJob

    sentinel = [RawJob("li_1", "http://x", "T", "C", "US", "Remote", "", "", None)]
    monkeypatch.setattr(ft, "fetch_linkedin", lambda s: sentinel)

    search.source = "linkedin"
    assert fetch_search(search) is sentinel


def test_router_unknown_source_returns_empty(search):
    search.source = "bogus_source"
    assert fetch_search(search) == []
