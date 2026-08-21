"""Smoke tests for the four job-source fetchers and the fetch router.

All tests run fully offline — no network calls. Each fetcher's HTTP layer is
monkeypatched with a minimal FakeResponse carrying a realistic fixture payload.
"""
from types import SimpleNamespace

import pytest

from job.config import SearchConfig
from job.fetch_worker import _matches_work_styles, _should_include_job
from job.fetcher import fetch_search, SOURCES
from job.models import RemoteType, DEFAULT_BLACKLIST, JOB_STATUSES
from job.fetcher_utils import infer_remote


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


# ── RemoteType constants ──────────────────────────────────────────────────────

def test_remote_type_values():
    assert RemoteType.REMOTE == "Remote"
    assert RemoteType.HYBRID == "Hybrid"
    assert RemoteType.ONSITE == "On-site"
    assert set(RemoteType.ALL) == {"Remote", "Hybrid", "On-site"}


def test_default_blacklist_not_empty():
    assert len(DEFAULT_BLACKLIST) > 0
    assert all(isinstance(w, str) for w in DEFAULT_BLACKLIST)


def test_job_statuses():
    assert "pending" in JOB_STATUSES
    assert "applied" in JOB_STATUSES
    assert "skipped" in JOB_STATUSES


def test_work_style_filter_allows_selected_styles():
    search = SimpleNamespace(work_styles=[RemoteType.HYBRID])
    assert _matches_work_styles(SimpleNamespace(remote=RemoteType.HYBRID), search) is True
    assert _matches_work_styles(SimpleNamespace(remote=RemoteType.REMOTE), search) is False


def test_work_style_filter_is_disabled_for_old_configs():
    assert _matches_work_styles(SimpleNamespace(remote=RemoteType.ONSITE), SimpleNamespace()) is True


def test_linkedin_remote_filter_allows_unknown_cards_without_mislabeling():
    search = SimpleNamespace(source="linkedin", remote=True, work_styles=[RemoteType.REMOTE])
    assert _matches_work_styles(SimpleNamespace(remote=RemoteType.UNKNOWN), search) is True


def test_title_filter_does_not_exclude_provider_results():
    config = SimpleNamespace(company_blacklist=[], title_filter=["senior frontend engineer"], blacklist=[])

    assert _should_include_job(SimpleNamespace(
        title="Backend Engineer", company="Acme", description=""
    ), config) == (True, None)


# ── infer_remote ──────────────────────────────────────────────────────────────

def test_infer_remote_remote():
    assert infer_remote("Remote Developer", "Berlin") == RemoteType.REMOTE

def test_infer_remote_hybrid():
    assert infer_remote("Hybrid Role", "Munich") == RemoteType.HYBRID

def test_infer_remote_onsite():
    assert infer_remote("Office Based", "Frankfurt") == RemoteType.ONSITE

def test_infer_remote_homeoffice():
    assert infer_remote("HomeOffice möglich", "Hamburg") == RemoteType.REMOTE

def test_infer_remote_hybrid_takes_priority_over_remote():
    assert infer_remote("Hybrid Remote role", "Berlin") == RemoteType.HYBRID

def test_infer_remote_worldwide():
    assert infer_remote("Available worldwide", "") == RemoteType.REMOTE

def test_infer_remote_no_signal_defaults_onsite():
    assert infer_remote("Software Engineer", "Berlin") == RemoteType.ONSITE

def test_infer_remote_no_signal_unknown_when_requested():
    # LinkedIn cards carry no workplace signal — caller opts into Unknown
    assert infer_remote("Software Engineer", "Berlin", default=RemoteType.UNKNOWN) == RemoteType.UNKNOWN

def test_infer_remote_explicit_onsite_beats_unknown_default():
    assert infer_remote("On-site role", default=RemoteType.UNKNOWN) == RemoteType.ONSITE

def test_linkedin_remote_search_without_card_signal_stays_unknown(monkeypatch, search):
    # LinkedIn's remote filter narrows search results, but public cards often
    # omit workplace type. Store Unknown unless the card itself has a signal.
    import job.linkedin_fetcher as lf
    card = lf.BeautifulSoup('<div class="base-card"></div>', "lxml").select_one("div")
    assert lf._infer_remote_linkedin("Berlin, Germany", card, True) == RemoteType.UNKNOWN
    assert lf._infer_remote_linkedin("Berlin, Germany", card, False) == RemoteType.UNKNOWN


# ── JSON-LD description extraction ──────────────────────────────────────────────

def _soup(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml")

def test_jsonld_description_single_object():
    from job.fetcher_utils import jsonld_job_description
    html = '<html><head><script type="application/ld+json">{"@type":"JobPosting","description":"<p>Build <b>great</b> things</p>"}</script></head></html>'
    out = jsonld_job_description(_soup(html))
    assert "Build" in out and "great" in out and "<p>" not in out

def test_jsonld_description_in_graph():
    from job.fetcher_utils import jsonld_job_description
    html = '<script type="application/ld+json">{"@graph":[{"@type":"WebPage"},{"@type":"JobPosting","description":"Senior role details"}]}</script>'
    assert "Senior role details" in jsonld_job_description(_soup(html))

def test_jsonld_description_list():
    from job.fetcher_utils import jsonld_job_description
    html = '<script type="application/ld+json">[{"@type":"Organization"},{"@type":"JobPosting","description":"Listed desc"}]</script>'
    assert "Listed desc" in jsonld_job_description(_soup(html))

def test_jsonld_description_type_list_and_schema_url():
    from job.fetcher_utils import jsonld_job_description
    html = '<script type="application/ld+json">{"@graph":[{"@type":["https://schema.org/JobPosting"],"description":"Schema URL desc"}]}</script>'
    assert "Schema URL desc" in jsonld_job_description(_soup(html))

def test_jsonld_description_absent_returns_empty():
    from job.fetcher_utils import jsonld_job_description
    assert jsonld_job_description(_soup("<html><body>no ld json</body></html>")) == ""

def test_jsonld_description_malformed_json_safe():
    from job.fetcher_utils import jsonld_job_description
    html = '<script type="application/ld+json">{not valid json,,,}</script>'
    assert jsonld_job_description(_soup(html)) == ""


# ── SOURCES registry ──────────────────────────────────────────────────────────

def test_sources_is_list_of_tuples():
    assert isinstance(SOURCES, list)
    for src, mp in SOURCES:
        assert isinstance(src, str)
        assert isinstance(mp, int)
        assert mp > 0

def test_sources_contains_expected_entries():
    ids = [src for src, _ in SOURCES]
    for expected in ("linkedin", "jobicy", "himalayas", "greenhouse",
                     "germantechjobs", "berlinstartupjobs", "stepstone"):
        assert expected in ids, f"{expected} missing from SOURCES"

def test_sources_no_duplicates():
    ids = [src for src, _ in SOURCES]
    assert len(ids) == len(set(ids))


# ── SOURCE_REGISTRY + capability dispatch ──────────────────────────────────────

def test_registry_prefixes_unique_and_match_fetchers():
    from job.fetcher import SOURCE_REGISTRY
    prefixes = [s.prefix for s in SOURCE_REGISTRY]
    assert len(prefixes) == len(set(prefixes)), "job_id prefixes must be unique"
    for s in SOURCE_REGISTRY:
        assert s.prefix.endswith("_"), f"{s.id} prefix should end with _"
        assert s.fetch_fn.startswith("fetch_")

def test_registry_matches_sources_view():
    from job.fetcher import SOURCE_REGISTRY, SOURCES, _SOURCE_TO_FN
    assert SOURCES == [(s.id, s.default_pages) for s in SOURCE_REGISTRY]
    assert _SOURCE_TO_FN == {s.id: s.fetch_fn for s in SOURCE_REGISTRY}

def test_source_can_describe():
    from job.fetcher import source_can_describe
    assert source_can_describe("li_123") is True       # linkedin declares describe
    assert source_can_describe("ss_456") is True        # stepstone declares describe
    assert source_can_describe("jc_789") is False       # jobicy has no describe
    assert source_can_describe("bogus_1") is False      # unknown prefix

def test_fetch_description_dispatches_by_prefix(monkeypatch):
    import job.fetcher as ft
    ss = ft._source_for_job_id("ss_1")
    original = ss.describe
    try:
        object.__setattr__(ss, "describe", lambda url, **kw: f"SS:{url}:{kw['job_id']}")
        assert ft.fetch_description("ss_1", "http://job") == "SS:http://job:ss_1"
    finally:
        object.__setattr__(ss, "describe", original)

def test_fetch_description_empty_for_no_url():
    from job.fetcher import fetch_description
    assert fetch_description("li_1", "") == ""

def test_fetch_description_empty_for_unsupported_source():
    from job.fetcher import fetch_description
    assert fetch_description("jc_1", "http://x") == ""       # jobicy has no describe
    assert fetch_description("zzz_1", "http://x") == ""       # unknown prefix

def test_fetch_description_swallows_errors():
    import job.fetcher as ft
    def boom(url, **kw): raise RuntimeError("scrape failed")
    ss = ft._source_for_job_id("ss_1")
    original = ss.describe
    try:
        object.__setattr__(ss, "describe", boom)
        assert ft.fetch_description("ss_1", "http://x") == ""     # error -> "" not raised
    finally:
        object.__setattr__(ss, "describe", original)


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
    assert job.remote == RemoteType.REMOTE


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


def test_jobicy_defaults_remote_without_keyword(monkeypatch, search):
    """Jobicy is a remote-only board — a job with no 'remote' keyword must still
    be Remote, not a false On-site."""
    import job.jobicy_fetcher as jf
    data = {"jobs": [{"id": 1, "jobTitle": "Backend Engineer", "companyName": "X",
                      "jobGeo": "USA", "jobType": ["full-time"],
                      "jobDescription": "Build things", "url": "http://x", "pubDate": "2024"}]}
    search.source = "jobicy"
    monkeypatch.setattr(jf, "http_get", lambda *a, **kw: FakeResponse(data=data))
    out = jf.fetch_jobicy(search)
    assert out[0].remote == RemoteType.REMOTE


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
    assert job.remote == RemoteType.REMOTE


def test_greenhouse_title_filter_excludes_non_matching(monkeypatch, search):
    """Jobs whose title doesn't match the query terms are dropped."""
    import job.greenhouse_fetcher as gf

    search.source = "greenhouse"
    search.query = "engineer"  # won't match "Product Manager"
    search.companies = ["acme"]
    monkeypatch.setattr(gf, "http_get", lambda *a, **kw: FakeResponse(data=_GREENHOUSE_JSON))

    results = gf.fetch_greenhouse(search)
    assert results == []


def test_greenhouse_named_location_is_onsite(monkeypatch, search):
    """A Greenhouse job with a named office location (no remote keyword) is
    On-site, not Unknown — the location itself is the signal."""
    import job.greenhouse_fetcher as gf
    data = {"jobs": [{"id": 9, "title": "Product Manager", "location": {"name": "Berlin, Germany"},
                      "absolute_url": "http://x", "updated_at": "2024"}]}
    search.source = "greenhouse"; search.query = "product"; search.companies = ["acme"]
    search.location = "Germany"
    search.remote = False  # don't skip on-site
    monkeypatch.setattr(gf, "http_get", lambda *a, **kw: FakeResponse(data=data))
    out = gf.fetch_greenhouse(search)
    assert out[0].remote == RemoteType.ONSITE


# ── GermanTechJobs ────────────────────────────────────────────────────────────

_GTJ_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>GermanTechJobs</title>
    <item>
      <title>Senior Engineer at TechGmbH (Berlin)</title>
      <link>https://germantechjobs.de/jobs/techgmbh-senior-engineer</link>
      <description>Great engineering role</description>
      <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


def test_germantechjobs_fetcher_parses_rss(monkeypatch, search):
    import job.germantechjobs_fetcher as gtj

    search.source = "germantechjobs"
    search.location = "Germany"
    monkeypatch.setattr(gtj, "http_get", lambda *a, **kw: FakeResponse(text=_GTJ_RSS))

    results = gtj.fetch_germantechjobs(search)

    assert len(results) == 1
    job = results[0]
    assert job.job_id == "gtj_techgmbh-senior-engineer"
    assert job.company == "TechGmbH"
    assert job.location == "Berlin"
    assert "Senior Engineer" in job.title
    # No remote/hybrid keyword in the listing → Unknown, not a false On-site
    assert job.remote == RemoteType.UNKNOWN


def test_germantechjobs_location_filter(monkeypatch, search):
    """Jobs outside the search location are dropped."""
    import job.germantechjobs_fetcher as gtj

    search.source = "germantechjobs"
    search.location = "United States"  # won't match Berlin
    monkeypatch.setattr(gtj, "http_get", lambda *a, **kw: FakeResponse(text=_GTJ_RSS))

    results = gtj.fetch_germantechjobs(search)
    assert results == []


# ── Berlin Startup Jobs ───────────────────────────────────────────────────────

_BSJ_JSON = [
    {
        "id": 101,
        "date": "2024-01-15T10:00:00",
        "link": "https://berlinstartupjobs.com/listings/techco-backend-engineer",
        "title": {"rendered": "Backend Engineer at TechCo"},
        "content": {"rendered": "<p>Build scalable systems. Remote friendly.</p>"},
    }
]

_BSJ_HEADERS = {"X-WP-TotalPages": "1"}


class FakeResponseWithHeaders(FakeResponse):
    def __init__(self, data, headers):
        super().__init__(data=data)
        self.headers = headers


def test_berlinstartupjobs_fetcher_parses_json(monkeypatch, search):
    import job.berlinstartupjobs_fetcher as bsj

    search.source = "berlinstartupjobs"
    search.location = "Germany"
    monkeypatch.setattr(
        bsj, "http_get",
        lambda *a, **kw: FakeResponseWithHeaders(_BSJ_JSON, _BSJ_HEADERS),
    )

    results = bsj.fetch_berlinstartupjobs(search)

    assert len(results) == 1
    job = results[0]
    assert job.job_id == "bsj_101"
    assert job.location == "Berlin, Germany"
    assert job.remote == RemoteType.REMOTE
    assert "scalable" in job.description


def test_berlinstartupjobs_location_filter(monkeypatch, search):
    """Non-Germany searches should be skipped."""
    import job.berlinstartupjobs_fetcher as bsj

    search.source = "berlinstartupjobs"
    search.location = "United States"
    monkeypatch.setattr(
        bsj, "http_get",
        lambda *a, **kw: FakeResponseWithHeaders(_BSJ_JSON, _BSJ_HEADERS),
    )

    results = bsj.fetch_berlinstartupjobs(search)
    assert results == []


# ── StepStone ─────────────────────────────────────────────────────────────────

_STEPSTONE_HTML = """
<html><body>
<article data-at="job-item" data-jobid="987654">
  <h2 data-at="job-item-title"><a href="/stellenangebote--software-engineer--987654-inline.html">Software Engineer</a></h2>
  <span data-at="job-item-company-name">MegaCorp GmbH</span>
  <span data-at="job-item-location">Berlin, Deutschland</span>
  <p data-at="job-item-snippet">Remote work possible</p>
</article>
</body></html>
"""

_STEPSTONE_DETAIL_JSONLD = """
<html><head>
<script type="application/ld+json">
{
  "@type": ["JobPosting"],
  "description": "<h2>Was Deinen Job ausmacht</h2><ul><li>Begleitung der Entwicklung und Optimierung komplexer Webprojekte</li><li>Gezielter Einsatz KI-gestützter Entwicklungs- und Assistenztools</li></ul><h2>Das wünschen wir uns</h2><p>Sehr gute Deutschkenntnisse und gute Englischkenntnisse</p>"
}
</script>
</head></html>
"""

_STEPSTONE_DETAIL_MARKUP = """
<html><body>
<section data-at="job-ad-content">
  <h2>Was wir Dir bieten</h2>
  <ul>
    <li>50 % remote arbeiten, 30+ Urlaubstage und Workation-Möglichkeiten</li>
    <li>Unbefristeter Arbeitsvertrag und attraktive Weiterbildungsmöglichkeiten</li>
  </ul>
</section>
</body></html>
"""


def test_stepstone_fetcher_parses_html(monkeypatch, search):
    import job.stepstone_fetcher as ss
    import httpx as _httpx

    search.source = "stepstone"
    search.location = "Germany"
    monkeypatch.setattr(ss.httpx, "get", lambda *a, **kw: FakeResponse(text=_STEPSTONE_HTML))

    results = ss.fetch_stepstone(search)

    assert len(results) == 1
    job = results[0]
    assert job.job_id == "ss_987654"
    assert job.company == "MegaCorp GmbH"
    assert job.location == "Berlin, Deutschland"
    assert job.remote == RemoteType.REMOTE


def test_stepstone_describe_parses_german_jsonld(monkeypatch):
    import job.stepstone_fetcher as ss

    monkeypatch.setattr(ss.httpx, "get", lambda *a, **kw: FakeResponse(text=_STEPSTONE_DETAIL_JSONLD))

    out = ss.fetch_description("https://www.stepstone.de/stellenangebote--frontend--123-inline.html")

    assert "Was Deinen Job ausmacht" in out
    assert "KI-gestützter Entwicklungs- und Assistenztools" in out
    assert "Sehr gute Deutschkenntnisse" in out
    assert "• Begleitung der Entwicklung" in out
    assert "<h2>" not in out


def test_stepstone_describe_falls_back_to_detail_markup(monkeypatch):
    import job.stepstone_fetcher as ss

    monkeypatch.setattr(ss.httpx, "get", lambda *a, **kw: FakeResponse(text=_STEPSTONE_DETAIL_MARKUP))

    out = ss.fetch_description("https://www.stepstone.de/stellenangebote--frontend--123-inline.html")

    assert "Was wir Dir bieten" in out
    assert "50 % remote arbeiten" in out
    assert "Unbefristeter Arbeitsvertrag" in out
    assert "<li>" not in out


# ── Router ────────────────────────────────────────────────────────────────────

def test_router_dispatches_to_linkedin(monkeypatch, search):
    from job import fetcher as ft

    sentinel = [RemoteType]  # any non-empty unique object
    monkeypatch.setattr(ft, "fetch_linkedin", lambda s: sentinel)

    search.source = "linkedin"
    assert fetch_search(search) is sentinel


@pytest.mark.parametrize("source", [src for src, _ in SOURCES])
def test_router_dispatches_all_sources(monkeypatch, search, source):
    """Every source in SOURCES must be routable (not fall through to unknown)."""
    from job import fetcher as ft

    sentinel = []
    fn_name = ft._SOURCE_TO_FN[source]
    monkeypatch.setattr(ft, fn_name, lambda s: sentinel)

    search.source = source
    assert fetch_search(search) is sentinel


def test_router_unknown_source_returns_empty(search):
    search.source = "bogus_source"
    assert fetch_search(search) == []



def test_greenhouse_describe_parses_api_content(monkeypatch):
    """Greenhouse describe() hits the board JSON API and strips the content HTML."""
    import job.greenhouse_fetcher as gf
    monkeypatch.setattr(gf, "http_get",
                        lambda *a, **kw: FakeResponse(data={"content": "&lt;p&gt;Build &lt;b&gt;great&lt;/b&gt; APIs with Python&lt;/p&gt;"}))
    out = gf.fetch_description("https://boards.greenhouse.io/stripe/jobs/456")
    assert "Build" in out and "great" in out and "Python" in out
    assert "<p>" not in out and "&lt;" not in out  # unescaped + stripped


def test_greenhouse_describe_uses_job_id_for_custom_career_urls(monkeypatch):
    """Company careers URLs often hide the board token; stored gh_* ids keep it."""
    import job.greenhouse_fetcher as gf
    called = {}

    def fake_get(url, **kwargs):
        called["url"] = url
        return FakeResponse(data={"content": "&lt;p&gt;Airbnb role details&lt;/p&gt;"})

    monkeypatch.setattr(gf, "http_get", fake_get)

    out = gf.fetch_description(
        "https://careers.airbnb.com/positions/7662244?gh_jid=7662244",
        job_id="gh_airbnb_7662244",
    )

    assert called["url"] == "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs/7662244"
    assert out == "Airbnb role details"


def test_greenhouse_describe_bad_url_returns_empty():
    from job.greenhouse_fetcher import fetch_description
    assert fetch_description("") == ""
    assert fetch_description("https://example.com/not-greenhouse") == ""
