# Provider Architecture — Design Spec

> Target: aggregate dozens of job providers and serve millions of searches.
> Principle: **adding a provider = one new file, zero edits to business logic.**

This is a design document. It is grounded in the current code
(`job/fetcher.py`, `job/fetch_worker.py`, `job/models.py`,
`job/*_fetcher.py`) and lays out the target architecture plus a phased,
non-breaking migration. No implementation is included yet — see the Migration
Plan for the build order.

---

## 1. Where we are today

The current design is already better than most: `SOURCE_REGISTRY` in
`fetcher.py` is a genuine registry, `RawJob` is a canonical model, and
`fetch_search()` dispatches by source id. What it lacks for scale:

| Today | Gap at scale |
|-------|--------------|
| `fetch_<x>(search) -> list[RawJob]` free functions | No per-provider details/company/health/auth; capabilities are ad-hoc (`describe` only) |
| `_run_fetch` loops providers **sequentially** | N providers = N× latency; one slow provider blocks all |
| Filtering/dedup live in `fetch_worker` | Coupled to the DB-ingest path; not reusable for a live multi-provider search |
| `RawJob` is a flat dataclass | No provenance, no capability flags, no raw payload for AI, weak typing |
| Errors bubble to a single try/except | One provider failing kills the whole run |
| No caching | Every search re-hits every provider |

The redesign keeps what works (registry, canonical model, prefix-based
resolution) and formalizes the rest into interfaces.

---

## 2. High-level architecture

```
                          ┌─────────────────────────────────────────────┐
                          │                 API / Web layer               │
                          │   /api/search   /api/job/<id>   /api/fetch     │
                          └───────────────────────┬───────────────────────┘
                                                  │ SearchRequest
                          ┌───────────────────────▼───────────────────────┐
                          │              SearchOrchestrator                 │
                          │  select → fan-out → normalize → dedup →         │
                          │  rank → filter → paginate → SearchResponse      │
                          └───────┬─────────────────────────────┬──────────┘
                                  │                             │
                    ┌─────────────▼──────────┐      ┌───────────▼───────────┐
                    │    ProviderRegistry     │      │       CacheLayer       │
                    │  discover / enable /    │      │ search / details /     │
                    │  lookup / capabilities  │      │ company / metadata     │
                    └─────────────┬──────────┘      └────────────────────────┘
                                  │ resolves
        ┌──────────────┬──────────┼──────────┬──────────────┬─────────────┐
        ▼              ▼          ▼          ▼              ▼             ▼
  LinkedInProvider Greenhouse  Lever    Workday   Ashby   CareerPage … (each a JobProvider)
        │  each implements the JobProvider interface + declares Capabilities  │
        └──────────────────────────── normalize() → CanonicalJob ────────────┘
```

Everything above the providers speaks only **`JobProvider`** + **`CanonicalJob`**.
Nothing above a provider imports a provider module directly.

---

## 3. Folder structure

```
job/
  providers/
    __init__.py            # exposes the registry singleton
    base.py                # JobProvider ABC, Capability enum, ProviderMeta
    registry.py            # ProviderRegistry: discover / register / lookup
    errors.py              # ProviderError hierarchy
    ratelimit.py           # token-bucket limiter, shared
    http.py                # shared httpx client, retries, UA, timeouts
    linkedin.py            # class LinkedInProvider(JobProvider)
    greenhouse.py
    lever.py
    workday.py
    ashby.py
    smartrecruiters.py
    career_page.py
    ...                    # one file per provider — the ONLY thing you add
  search/
    orchestrator.py        # the pipeline (§6)
    dedup.py               # canonical dedup key + merge
    ranking.py             # scoring strategies
    pipeline_models.py     # SearchRequest / SearchResponse (Pydantic)
  models/
    canonical.py           # CanonicalJob, Company, Salary, Location (Pydantic)
  cache/
    __init__.py            # Cache protocol (get/set/invalidate)
    memory.py              # in-proc default
    redis.py               # prod backend (swap-in)
```

Business logic (`search/`, `models/`, `cache/`) has **zero imports** from any
concrete provider. Providers are discovered, never referenced.

---

## 4. Provider interface (`providers/base.py`)

A single ABC every provider implements. Each method earns its place:

```
class JobProvider(ABC):
    meta: ProviderMeta                     # id, display name, prefix, capabilities

    # ── discovery / lifecycle ──
    def capabilities() -> set[Capability]  # what this provider can do (§7)
    def health_check() -> HealthStatus     # is it up / authed / rate-ok right now?
    def authenticate() -> None             # acquire/refresh creds; no-op for keyless

    # ── core data ──
    def search(query: ProviderQuery) -> Iterator[CanonicalJob]   # yields normalized jobs
    def get_details(external_id, url) -> JobDetails | None        # full description on demand
    def get_company(company_ref) -> Company | None                # company enrichment

    # ── internal contract ──
    def normalize(raw: dict) -> CanonicalJob   # provider JSON → canonical (the ONLY mapping site)
```

**Why each belongs:**

- **`capabilities()`** — the whole system adapts to what a provider *can* do
  (§7); business logic never hardcodes "LinkedIn has salary." It's on the
  interface so the orchestrator/UI can query it uniformly.
- **`health_check()`** — at N providers, some are always degraded. The registry
  needs a uniform way to skip/deprioritize sick providers and power a status
  page. Cheap, cached, side-effect-free.
- **`authenticate()`** — auth differs wildly (none, API key, OAuth refresh,
  session cookie). Putting it on the interface means the orchestrator calls it
  identically and each provider hides its own scheme. Keyless providers no-op.
- **`search()`** returns an **iterator**, not a list — lets a provider stream
  pages lazily and lets the orchestrator apply a global result cap without a
  provider fetching all pages. Takes a **`ProviderQuery`** (already translated
  from the canonical `SearchRequest`), so providers never see app-level config.
- **`get_details()`** — generalizes today's `describe`; on-demand full
  description / structured fields, gated by capability.
- **`get_company()`** — company enrichment (ratings, size, logo) is a first-class
  future need (Company Intelligence AI Skill); separate call because it's a
  different cache lifetime and not every search needs it.
- **`normalize()`** — the **single mapping site** per provider. This is the
  heart of DRY/OCP: all provider-specific JSON weirdness is quarantined in one
  method; everything downstream sees only `CanonicalJob`.

`ProviderMeta` (dataclass): `id`, `display_name`, `prefix` (job-id namespace,
e.g. `li_`), `default_pages`, `capabilities`, `auth_kind`, `rate_limit`.

---

## 5. Provider registry (`providers/registry.py`)

Formalizes today's `SOURCE_REGISTRY` into an object with lifecycle:

```
class ProviderRegistry:
    def discover() -> None                 # import providers/*.py, auto-register subclasses
    def register(provider: JobProvider)    # explicit (tests, plugins)
    def get(provider_id) -> JobProvider
    def by_prefix(job_id) -> JobProvider    # resolve a stored job to its provider
    def enabled() -> list[JobProvider]      # honors config + health + kill-switch
    def set_enabled(provider_id, bool)      # runtime enable/disable, no deploy
    def with_capability(cap) -> list[...]   # "who supports salary filtering?"
```

- **Discovery** — on startup, import every module in `providers/` and register
  any `JobProvider` subclass (via `__init_subclass__` or an explicit scan).
  Adding a provider file makes it appear automatically — no registry edit.
- **Enable/disable** — reads a config table/flag so ops can kill a
  misbehaving provider instantly (no redeploy). Health failures auto-disable
  with backoff.
- **Plugin support (future)** — same mechanism can load providers from an
  entry-point group (`jobpilot.providers`) so third-party providers ship as
  separate pip packages without touching core.

---

## 6. Canonical job model (`models/canonical.py`, Pydantic v2)

Strongly typed, provider-agnostic, AI-ready. Sketch:

```
class Location(BaseModel):
    raw: str
    city: str | None; region: str | None; country: str | None
    remote: RemoteType                      # Remote | Hybrid | On-site | Unknown

class Salary(BaseModel):
    min: int | None; max: int | None
    currency: str | None; period: Literal["year","month","hour"] | None
    raw: str | None

class Company(BaseModel):
    name: str
    domain: str | None; logo_url: str | None
    size: str | None; rating: float | None   # populated by get_company / enrichment

class CanonicalJob(BaseModel):
    # identity / provenance
    id: str                                  # "{prefix}{external_id}" — globally unique
    provider_id: str
    external_id: str
    url: HttpUrl

    # core
    title: str
    company: Company
    location: Location
    employment_type: str | None
    experience: str | None
    salary: Salary | None
    description: str | None                  # may be None until get_details()
    posted_at: datetime | None
    first_seen_at: datetime

    # capability-driven optionals (None if provider can't supply)
    easy_apply: bool | None
    tags: list[str] = []                     # skills/tech extracted or provider-supplied

    # AI substrate — never provider-specific
    raw: dict = {}                           # original payload, for re-normalization/debug
    ai: dict = {}                            # AI Skill outputs keyed by skill (§11)
```

**How each provider transforms:** every provider's `normalize(raw)` maps its
own JSON into this — Greenhouse's `content`, Lever's `descriptionPlain`,
LinkedIn's scraped card, Workday's facet payload — all collapse to
`CanonicalJob`. Pydantic validates at the boundary, so a malformed provider
response fails **there** (caught as a normalization error) rather than
poisoning downstream code. The `raw` field preserves the original for
re-normalization when the mapping improves, without re-fetching.

Migration note: this is `RawJob` (current flat dataclass) promoted to a
nested, validated model. The DB row stays flat; a thin adapter maps
`CanonicalJob` ↔ the `jobs` table so the storage layer is untouched initially.

---

## 7. Capability system (`providers/base.py`)

```
class Capability(str, Enum):
    SEARCH_REMOTE_FILTER  = "remote_filter"
    SEARCH_SALARY_FILTER  = "salary_filter"
    FULL_DESCRIPTION      = "full_description"    # get_details supported
    COMPANY_INFO          = "company_info"        # get_company supported
    SALARY_DATA           = "salary_data"
    EASY_APPLY            = "easy_apply"
    COMPANY_RATING        = "company_rating"
    POSTED_DATE           = "posted_date"
    AI_METADATA           = "ai_metadata"
```

Each provider declares a `set[Capability]`. Business logic **queries**, never
assumes:

- Orchestrator only sends a salary filter to providers with `SALARY_FILTER`;
  others get an unfiltered query and results are salary-filtered post-hoc (or
  skipped if the filter is strict).
- UI shows the "Posted" filter only if ≥1 enabled provider has `POSTED_DATE`
  (this is why StepStone — no posted date — currently looks broken; capability
  makes it explicit).
- `get_details()`/`get_company()` are only called on providers that advertise
  them; the current `source_can_describe()` becomes `has_capability(FULL_DESCRIPTION)`.

This is the mechanism that lets features "adapt automatically" — the app reasons
about capabilities, not provider identities.

---

## 8. Search pipeline (`search/orchestrator.py`)

```
SearchRequest (canonical, validated)
   │
   ▼ (1) Provider selection      registry.enabled() ∩ capability match ∩ user's chosen sources
   ▼ (2) Query translation       SearchRequest → per-provider ProviderQuery (each provider's dialect)
   ▼ (3) Parallel execution      async fan-out with per-provider timeout + rate limit (§10)
   ▼ (4) Normalization           each provider.normalize() → CanonicalJob (validated)
   ▼ (5) Deduplication           canonical key = (norm_title, norm_company, location); merge best fields
   ▼ (6) Ranking                 score by relevance × freshness × provider trust × capability richness
   ▼ (7) Filtering               apply filters providers couldn't (salary, remote, blacklist)
   ▼ (8) Pagination              cursor over the merged, ranked set
   ▼
SearchResponse { jobs, per_provider_status, facets, cursor }
```

- **(1) Selection** — intersect enabled+healthy providers with the user's
  source choice and the query's required capabilities. A strict salary filter
  drops providers that can neither filter nor supply salary.
- **(2) Translation** — the canonical request becomes each provider's native
  query (keywords → LinkedIn's `keywords=`, Greenhouse's board tokens, etc.).
  Keeps provider dialects out of the orchestrator.
- **(3) Parallel** — see §10. Each provider runs isolated; a failure/timeout
  yields a partial `ProviderResult`, never aborts the batch.
- **(4) Normalize** — at the boundary; validation errors are logged per-job and
  skipped, not fatal.
- **(5) Dedup** — the same role appears on LinkedIn + the company's Greenhouse
  board. Dedup by normalized (title, company, location); when merging, keep the
  richest record (prefer one with salary/description; prefer higher provider
  trust). This is new — today dedup is per-source in the DB path.
- **(6) Ranking** — pluggable strategy (Strategy pattern): relevance to query,
  recency, provider trust weight, capability richness. Swappable for an
  AI/embedding ranker later without touching the pipeline.
- **(7) Filtering** — post-hoc application of anything providers couldn't do
  natively (keeps results correct regardless of provider capability).
- **(8) Pagination** — opaque cursor over the merged set (offset or keyset),
  independent of any provider's own paging.

The **fetch-to-DB path** (`_run_fetch`) becomes a *consumer* of the same
pipeline: run search → ingest new `CanonicalJob`s. One code path, two callers
(live search + background ingest).

---

## 9. Caching (`cache/`)

`Cache` protocol (get/set/invalidate) with pluggable backends (in-memory now,
Redis in prod). Cache is keyed and TTL'd by data volatility:

| Data | Key | TTL | Invalidation |
|------|-----|-----|--------------|
| **Search results** | hash(normalized request + provider set) | 5–15 min | TTL only; searches are inherently fresh-ish |
| **Job details** (full description) | `job_id` | 24 h | On re-fetch; details rarely change |
| **Company data** | company domain | 7 d | TTL; enrich lazily |
| **Provider metadata** (capabilities, health) | provider_id | 60 s (health), process-life (capabilities) | health on failure; capabilities on deploy |
| **Model lists / auth tokens** | provider_id | token-expiry-aware | on 401/key change |

Principles: cache the **expensive + stable**, never the **cheap + volatile**.
Search caching is per *(request, provider-set)* so toggling a provider yields a
different key. Stampede protection (single-flight lock) on hot search keys.
Negative-cache provider outages briefly so a down provider isn't hammered.

---

## 10. Parallel execution

**Recommendation: `asyncio` for provider fan-out, with a bounded task queue for
the background ingest.**

Reasoning against the alternatives:

- **Sequential** (today) — unacceptable; latency = Σ providers. At 10 providers
  a search takes 10× the slowest.
- **Thread pool** — works, but provider calls are ~100% I/O (HTTP); threads
  waste memory and hit the GIL for the little CPU (normalization). Fine as an
  interim (see migration) but not the destination.
- **Async** — ideal for high-fan-out I/O: one event loop awaits N providers
  concurrently with per-provider `asyncio.wait_for` timeouts and an
  `asyncio.Semaphore` global concurrency cap. `httpx.AsyncClient` already
  supports it. Live search returns as fast as the slowest *responsive* provider.
- **Task queue / background workers** (Celery/RQ/Arq) — the right tool for the
  **ingest** side (scheduled crawls of all providers, retries, backpressure),
  not for a synchronous user search. Use both: async for live search, a queue
  for periodic ingest.

Partial results: the orchestrator gathers with `return_exceptions=True`,
converts failures to `ProviderResult(status=error)`, and returns whatever
succeeded plus a per-provider status map. **Graceful degradation is the default.**

---

## 11. Error handling (`providers/errors.py`)

A typed hierarchy so the orchestrator reacts by class, not string-matching:

```
ProviderError
 ├── ProviderTimeout          → drop provider from this batch, mark degraded
 ├── ProviderRateLimited      → back off (Retry-After), negative-cache, skip
 ├── ProviderAuthError        → disable provider, alert; never retry blindly
 ├── ProviderUnavailable      → 5xx/network; retry w/ jittered backoff, then skip
 └── ProviderMalformedResponse→ log payload, skip the bad item(s), keep the rest
```

Rules:
- Every provider call is wrapped; an exception becomes a `ProviderResult` with
  a status, never propagates to kill the batch.
- **Partial failure = success with gaps.** Response carries
  `per_provider_status` so the UI can say "LinkedIn timed out — showing 4 of 5
  sources."
- Normalization is per-item try/except: one malformed job is dropped, not the
  page.
- Health checks + auto-disable with exponential backoff prevent a dead provider
  from degrading every search.

---

## 12. AI integration

The `CanonicalJob.ai` dict is the substrate — AI Skills read canonical fields
(`title`, `company`, `salary`, `description`, `tags`) and write their outputs
back into `ai[skill_name]`. **No AI Skill ever imports a provider or reads
`raw`.** Examples map cleanly:

| AI Skill | Reads (canonical only) | Writes |
|----------|------------------------|--------|
| ATS Score | description, tags, title | `ai.ats` |
| Interview Prep | company, title, description | `ai.interview` |
| Company Intelligence | company (+ get_company enrichment) | `ai.company` |
| Salary Analysis | salary, location, title | `ai.salary` |
| Learning Roadmap | tags, description | `ai.roadmap` |
| Resume/Cover Letter | full canonical job | (documents) |

Because every provider funnels through `normalize()`, a new provider
automatically works with every existing AI Skill — that's the payoff of the
canonical model.

---

## 13. Testing strategy

- **Provider contract test** — one parametrized suite run against *every*
  registered provider: `normalize()` of a recorded fixture yields a valid
  `CanonicalJob`; capabilities are self-consistent (declares `FULL_DESCRIPTION`
  ⇒ implements `get_details`); `health_check` returns a `HealthStatus`. Adding
  a provider means adding a fixture, and the shared suite covers it.
- **Recorded fixtures** — check in a real sample response per provider (VCR-style
  or static JSON/HTML); normalization tests run fully offline (as today's
  `test_fetchers.py` already does).
- **Pipeline tests** — orchestrator against fake providers (in-memory
  `JobProvider` stubs) to test selection, dedup, ranking, partial-failure,
  pagination — no network.
- **Capability-matrix tests** — assert business logic adapts (salary filter
  skips providers without it, etc.).
- **Registry tests** — discovery finds all providers; enable/disable respected;
  prefix resolution unique (extends the current registry tests).
- **Contract > mocks:** test the boundary (normalize, capability), not internal
  HTTP calls, so provider refactors don't break tests.

---

## 14. Sequence diagram — a live search

```
User → API: POST /api/search {query, filters, sources}
API → Orchestrator: SearchRequest
Orchestrator → Registry: enabled() ∩ capabilities ∩ sources
Registry → Orchestrator: [LinkedIn, Greenhouse, Lever]
Orchestrator → Cache: get(search_key)
Cache → Orchestrator: MISS
par  (asyncio.gather, per-provider timeout + semaphore)
  Orchestrator → LinkedIn.search(q)    → [raw…] → normalize → [CanonicalJob]
  Orchestrator → Greenhouse.search(q)  → TIMEOUT → ProviderResult(error)
  Orchestrator → Lever.search(q)       → [raw…] → normalize → [CanonicalJob]
end
Orchestrator → dedup → rank → filter → paginate
Orchestrator → Cache: set(search_key, page, ttl=10m)
Orchestrator → API: SearchResponse{ jobs, per_provider_status:{greenhouse:timeout} }
API → User: 200 { jobs, "showing 2 of 3 sources" }
```

Detail view later:
```
User → API: GET /api/job/li_123
API → Registry: by_prefix("li_") → LinkedInProvider
API → Cache: get(details:li_123) → MISS
API → LinkedIn.get_details(...) → JobDetails → Cache.set(24h) → merge → 200
```

---

## 15. Migration plan (phased, non-breaking)

The current `SOURCE_REGISTRY` + `fetch_search` + `RawJob` already point this
direction, so migration is incremental — each phase ships independently with
green tests.

- **Phase 0 — Canonical model (adapter).** Introduce `CanonicalJob` (Pydantic)
  alongside `RawJob`; write `RawJob ↔ CanonicalJob` + `CanonicalJob ↔ DB row`
  adapters. No behavior change. Tests: round-trip adapters. *(Deferred — nothing
  consumes a canonical model yet; do this when the orchestrator lands in Phase 2.)*
- **✅ Phase 1 — Provider ABC, keep functions. DONE.** Added `JobProvider` +
  `FunctionProvider` + `Capability` in `job/providers/`, and a `ProviderRegistry`
  populated from `SOURCE_REGISTRY`. Existing `fetch_<x>` functions are wrapped
  (not rewritten); the registry's `search_fn` resolves through the module
  namespace so test monkeypatching still works. All legacy exports (`SOURCES`,
  `_SOURCE_TO_FN`, `fetch_search`, `fetch_description`, `source_can_describe`)
  unchanged. Capabilities declared per source; `by_prefix` / `with_capability` /
  enable-disable available. Zero user-facing change; 210 tests green.
- **Phase 2 — Orchestrator (sequential first).** Extract selection → normalize
  → dedup → rank → filter → paginate into `SearchOrchestrator`, initially
  **sequential** (matches today) but with per-provider try/except → partial
  results. Point `_run_fetch` at it. Adds dedup/partial-failure wins with no
  concurrency risk yet.
- **Phase 3 — Async fan-out.** Swap the orchestrator's provider loop to
  `asyncio.gather` with timeouts + semaphore; migrate providers to
  `httpx.AsyncClient`. This is the latency win. Providers that can't be async
  (CLI-based) run in a thread executor.
- **Phase 4 — Caching layer.** Add the `Cache` protocol + in-memory backend,
  cache searches/details/company; add Redis backend behind the same protocol
  for prod.
- **Phase 5 — Background ingest queue.** Move scheduled crawling to a task
  queue (Arq/RQ); live search stays synchronous-async. Enables retries,
  backpressure, and per-provider crawl cadence.
- **Phase 6 — Plugin entry points.** Load providers from a
  `jobpilot.providers` entry-point group so new providers can ship as separate
  packages.

Each phase is reversible and independently shippable. At no point does the app
break, and after Phase 1 the promise holds: **a new provider is one new file in
`providers/` that subclasses `JobProvider` — discovery, search, dedup, ranking,
caching, AI Skills, and the UI all pick it up with no other edits.**

---

## 16. How a new provider is added (target state)

1. Create `job/providers/smartrecruiters.py`.
2. `class SmartRecruitersProvider(JobProvider)` with `meta` (id, prefix,
   capabilities), `search()`, `normalize()`, and optionally `get_details()` /
   `get_company()`.
3. Add one recorded fixture for the contract test.

That's it. `__init_subclass__` registers it on import; the registry exposes it;
the orchestrator fans out to it; capabilities gate its features; the canonical
model makes it work with every AI Skill and the whole UI. **No edits to
`orchestrator.py`, `registry.py`, `models/`, the web layer, or any other
provider.** That is the Open/Closed Principle realized.
