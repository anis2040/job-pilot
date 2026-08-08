# Storage & Database Migration Plan

> **Status:** Design document — not implemented yet.  
> **Audience:** Contributors and future maintainers who were not part of the original local-first design decisions.

This document explains **why** JobPilot needs to move away from “everything on the server disk,” **what** we will change in which order, and **what we deliberately will not do** (and why).

For deployment today, see [HOSTING.md](HOSTING.md). For job-provider scaling, see [PROVIDER_ARCHITECTURE.md](PROVIDER_ARCHITECTURE.md).

---

## 1. Background: local-first, cloud-second

JobPilot was built for **single-machine, local use**:

- One Flask process on your laptop or a small VPS
- Per-user data under `profiles/<user_id>/<profile-slug>/`
- A **SQLite file** (`state.db`) per profile for jobs, embeddings, and logs
- **PDF resumes and cover letters** written to disk and served from `/pdf/...`
- LaTeX compilation via `pdflatex` on the same machine

That design is simple, fast to develop, and works well offline or on Docker Compose with a bind mount (`./data/profiles`).

When we deploy to the cloud (e.g. Fly.io with a persistent volume), the same layout still works — **as long as we run a single app instance** tied to one disk. The moment we want to **scale out** (multiple machines, zero-downtime deploys, smaller disks) or treat object storage as the source of truth for files, the current model becomes a bottleneck.

This plan is the agreed path forward: **incremental refactors** that unlock cloud scaling without a risky big-bang rewrite.

**Important constraint:** local development and “run on my machine” must **keep today’s behavior unchanged** — files on disk, SQLite per profile, `/pdf/...` served by Flask. Cloud deploys opt into external storage via configuration. Business logic must not branch on vendor names (`boto3`, R2, etc.) scattered across the codebase.

---

## 2. Design principle: abstraction + local/cloud modes

### Goal

| Runtime | PDFs | Database | Developer experience |
|---------|------|----------|----------------------|
| **Local** (laptop, `./dev.sh`, Docker Compose dev) | Files under `profiles/...` | SQLite `state.db` per profile | Same as today — zero cloud credentials |
| **Cloud** (Fly, managed VPS in “production” mode) | Object storage (S3-compatible) | SQLite on volume *now* → shared SQL *later* | Configured via server `.env` only |

Switching cloud storage vendor (AWS S3 → Cloudflare R2 → Supabase Storage → MinIO) should require **env var changes and at most one small adapter file**, not edits across `web.py`, `documents.py`, and tests.

### Runtime mode

Introduce an explicit deployment mode (exact env name TBD during implementation):

```env
# local  — default when unset in dev; filesystem + SQLite (current behavior)
# cloud  — object storage for PDFs; optional shared SQL in later phases
DEPLOYMENT_MODE=local
```

**Suggested defaults:**

- `DEPLOYMENT_MODE=local` when `FLASK_DEBUG=true` or when no cloud storage config is present
- `DEPLOYMENT_MODE=cloud` in production `.env` / Fly secrets

Mode is resolved **once at startup** in a single factory module — not re-checked in every route.

### Layered abstractions (centralized)

All durable I/O goes through small interfaces in one package (proposed: `job/storage/`). Application code (`documents.py`, `web.py`, `db.py`) depends on **protocols**, not vendors.

```
┌─────────────────────────────────────────────────────────────┐
│  Business logic                                              │
│  job/documents.py   web.py   job/db.py   job/profiles.py     │
└────────────────────────────┬────────────────────────────────┘
                             │ uses
┌────────────────────────────▼────────────────────────────────┐
│  Factories (single entry point)                              │
│  job/storage/__init__.py  →  get_blob_storage()            │
│                             →  get_database()  (Phase 3)     │
└────────────────────────────┬────────────────────────────────┘
                             │ selects by DEPLOYMENT_MODE + env
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
 LocalFilesystemBackend   S3CompatibleBackend   PostgresBackend
 (local mode, Phase 1)    (cloud Phase 1)       (cloud Phase 3)
                          also: R2, MinIO,
                          Supabase via same SDK
```

#### Phase 1 — `BlobStorage` protocol (PDFs and future blobs)

One interface, multiple backends:

| Method | Purpose |
|--------|---------|
| `put(key, data, content_type) -> StoredObject` | Upload bytes after `pdflatex` |
| `get_url(key, *, ttl_seconds) -> str` | Signed or public URL for frontend |
| `open(key) -> bytes` | Optional: proxy download through Flask |
| `delete(key)` | Remove on profile/job cleanup |
| `exists(key) -> bool` | Migration / idempotency |

**Backends:**

| Backend | When | Behavior |
|---------|------|----------|
| `LocalFilesystemBackend` | `DEPLOYMENT_MODE=local` | Writes under `profiles/...`; `get_url` returns `/pdf/...` (current behavior) |
| `S3CompatibleBackend` | `DEPLOYMENT_MODE=cloud` | S3 API (`boto3` or `aioboto3`); works with AWS S3, **R2**, MinIO, many others via endpoint URL |

**Vendor swap (cloud):** change env only — no app code changes:

```env
STORAGE_BACKEND=s3          # registry key, not “AWS only”
STORAGE_BUCKET=jobpilot-pdfs
STORAGE_REGION=auto
STORAGE_ENDPOINT=https://....r2.cloudflarestorage.com   # R2 / MinIO
STORAGE_ACCESS_KEY=...
STORAGE_SECRET_KEY=...
```

Adding a new vendor with a non-S3 API (e.g. GCS native SDK) = **one new class** implementing `BlobStorage` + one line in the factory registry.

**What business logic stores:** an opaque **`storage_key`** (and optionally a cached URL), never a vendor-specific path or bucket name. Local backend maps keys to relative paths under the profile tree; cloud backend maps keys to `s3://bucket/key`.

#### Phase 3 — `Database` protocol (optional until shared SQL)

Until Phase 3, `job/db.py` can keep calling SQLite directly in **local mode**. In **cloud mode** on a single volume, same SQLite file — no abstraction required yet.

When moving to Postgres/Turso:

| Method area | Notes |
|-------------|-------|
| Connection / transactions | `get_database()` returns a backend with the same operations `job/db.py` needs today |
| `LocalSqliteBackend` | Current `state.db` per profile — local mode only |
| `PostgresBackend` / `TursoBackend` | Cloud mode; `user_id` + `profile_id` on every query |

Repository functions stay in `job/db.py` (or `job/repository.py`); only the **connection layer** is swappable.

#### Profile/config files (Phase 4)

Same pattern: `ProfileStore` protocol with `LocalProfileStore` (files) and optional `RemoteProfileStore` (DB or object storage). Local mode always uses files.

### Rules for contributors

1. **No direct `Path(...).write_bytes` for PDFs** in business logic — use `get_blob_storage()`.
2. **No `boto3` imports** outside `job/storage/backends/s3.py` (or equivalent).
3. **No `if fly.io` / `if cloud`** in routes — only `DEPLOYMENT_MODE` in the factory.
4. **Tests** use `LocalFilesystemBackend` + temp dirs by default; cloud backends tested with mocks/fakes in CI (no real bucket).
5. **Local mode is not a shim** — it remains a fully supported, first-class deployment target indefinitely.

### Benefits of this shape

| Benefit | Why |
|---------|-----|
| Local dev unchanged | Default backend is filesystem; no API keys for storage |
| Vendor portability | S3-compatible backends share one implementation |
| Minimal blast radius | Swap vendor or fix SDK usage in one directory |
| Incremental delivery | Phase 1 adds `BlobStorage` only; DB abstraction follows when needed |
| Clear code review | Any new direct filesystem write for durable data should be rejected |

### Challenges

| Challenge | Mitigation |
|-----------|------------|
| Two code paths to test | Shared integration tests against `LocalFilesystemBackend`; contract tests for `BlobStorage` interface |
| URL shape differs ( `/pdf/...` vs signed HTTPS) | Frontend already uses `pdf_url` strings; backend normalizes in `get_url()` |
| Existing on-disk PDFs in cloud | One-time migration script using the same `BlobStorage.put()` abstraction |
| Risk of “leaky” abstraction | Enforce via factory + lint/review; document in this file |

---

## 3. Current architecture (what lives where)

```
profiles/
  <user_id>/                    # e.g. google_<sub>
    .env                        # per-user AI API keys
    .active                     # active profile slug
    <profile-slug>/
      profile.md, config.yaml   # candidate profile + search config
      state.db                  # SQLite — jobs, embeddings, fetch/filter logs
      <CompanyName>/
        resumes/                # .tex + generated PDFs
        cover-letters/
```

| Data | Location today | Access pattern |
|------|----------------|----------------|
| Job listings, status, embeddings | `state.db` (SQLite) | Frequent read/write, relational queries |
| Generated PDFs | Local filesystem under profile dir | Write once, read many; served by Flask |
| LaTeX intermediates (`.tex`, `.log`) | Same tree as PDFs | Ephemeral; needed only during compile |
| Profile markdown & YAML | Local filesystem | Occasional read/write |
| Build task status (resume/cl in progress) | **In-memory** (`job/task_state.py`) | Lost on restart |

On Fly.io, `profiles/` is mounted on a **block volume** (see `fly.toml`). That survives restarts but **does not attach to more than one machine at a time**, so horizontal scaling is blocked.

Relevant code today:

- Database: `job/db.py` → `get_db_path()` → `profiles/.../state.db`
- PDF build: `job/documents.py` → writes under `get_resumes_path()`, stores local `pdf_path`
- PDF serve: `web.py` → `GET /pdf/<path>` reads from disk

---

## 4. Why we need to change something

### Problems with “everything on disk” in the cloud

1. **Scaling** — A Fly/Railway volume (or EBS disk) belongs to one VM. Running two app instances means either duplicated data or unsafe shared access to SQLite.
2. **Disk size & cost** — PDFs and embeddings grow per user. Keeping them on the app volume increases backup size and machine storage needs.
3. **Deploy fragility** — Containers are meant to be replaceable; durable user data should not depend on the container filesystem.
4. **Backup & restore** — Tar-ing `profiles/` works for a hobby deploy, but object storage + managed DB give clearer backup/restore stories.
5. **Multi-instance correctness** — In-memory task state (`task_state.py`) is already lost on restart; multiple instances would not share build/fetch progress anyway.

### What we are *not* trying to solve in phase 1

- Rewriting the entire app for serverless (long-running fetch jobs and `pdflatex` still need a worker process).
- Migrating every file (profile.md, config.yaml, `.env`) on day one — those follow after PDFs and DB.

---

## 5. Key decision: PDFs to object storage, SQLite stays off object storage

### PDFs → external object storage (S3, R2, Supabase Storage, etc.)

**Decision:** Yes — this is the **first** migration step.

**Why:**

- PDFs are **large, immutable blobs** after generation — a perfect fit for object storage.
- Any number of app instances can serve the same file via a URL or signed link.
- The app volume shrinks; backups of “hot” data (DB) separate from “cold” files (PDFs).
- `pdflatex` still runs locally in a **temp directory**; only the **finished PDF** is uploaded.

**Benefits:**

| Benefit | Explanation |
|---------|-------------|
| Horizontal scaling | All instances read the same PDF without a shared filesystem |
| Cheaper storage | Object storage is typically cheaper per GB than SSD volumes |
| CDN-friendly | Public or signed URLs can be cached at the edge |
| Clear lifecycle | Delete/replace PDFs by key without scanning directories |

**Challenges:**

| Challenge | Mitigation |
|-----------|------------|
| LaTeX still needs local disk | Compile in `/tmp` (or profile temp dir), upload result, delete temp files |
| Auth for downloads | Use signed URLs or an authenticated proxy endpoint instead of open `/pdf/...` |
| Code paths assume filesystem paths | `BlobStorage` abstraction (§2); store `storage_key` + resolved `pdf_url`, not raw filesystem paths in business logic |
| Migration of existing PDFs | One-time script: upload existing files, rewrite references |
| Frontend expects `/pdf/...` | Update API responses to return full URL or new path pattern |

---

### SQLite → object storage as a “temporary” database

**Decision:** **No** — do not put the live SQLite file on S3/R2/GCS or mount object storage as a filesystem.

**Why:**

SQLite is a **single file** that expects a **local POSIX filesystem** with reliable file locking and atomic writes. Object storage (S3, R2, GCS) is **key/value blob storage**, not a database filesystem. You cannot safely `sqlite3.connect("s3://bucket/state.db")` and run a production app against it.

| Approach | Verdict |
|----------|---------|
| SQLite file on S3/R2 (live) | **Does not work** |
| S3 via FUSE (s3fs, goofys) | **Unsafe** — corruption risk under concurrent access |
| Periodic copy/sync of `state.db` to S3 | **Backup only** — not for runtime; active writes + sync = corruption risk |
| SQLite on a **block volume** (current Fly mount) | **Works** for **one instance** — what we have today |
| **Litestream** (replicate SQLite → S3) | Good for **disaster recovery**, not for multi-writer scaling |
| **Postgres / Turso** | Correct path when we need shared, multi-instance SQL |

**Short-term:** keep SQLite on the persistent volume **or** migrate to hosted SQL — there is no safe middle step of “SQLite on object storage until later.”

---

## 6. Phased migration plan

Each phase is independently valuable. Later phases do not block shipping earlier ones. **Every phase must preserve local mode** (§2) — cloud behavior is additive, selected by config.

### Phase 1 — `BlobStorage` abstraction + cloud PDFs (recommended first)

**Goal:** One interface for PDFs; local mode keeps filesystem behavior; cloud mode uploads to object storage.

**Scope:**

1. Add `job/storage/` with `BlobStorage` protocol, factory (`get_blob_storage()`), and backends:
   - `LocalFilesystemBackend` — default; current `profiles/...` layout + `/pdf/...` URLs
   - `S3CompatibleBackend` — cloud; endpoint URL makes R2/MinIO/AWS interchangeable
2. Refactor `job/documents.py` to call `blob_storage.put(...)` after `pdflatex` (compile still uses local temp dir in **both** modes).
3. Refactor `web.py`:
   - Local: keep `GET /pdf/<path>` for `LocalFilesystemBackend`
   - Cloud: signed URLs from `get_url()`, or thin authenticated proxy using `blob_storage.open()`
4. Store **`storage_key`** in task state / metadata; expose **`pdf_url`** to API (frontend unchanged).
5. Env: `DEPLOYMENT_MODE`, `STORAGE_*` vars (see §2); document in `.env.example`.

**Benefits:** Unlocks multi-instance PDF access in cloud; local dev untouched; vendor changes are env-only.

**Challenges:** Contract tests for both backends; migrating existing cloud-volume PDFs via the same `put()` API.

**Out of scope for phase 1:** SQLite abstraction, profile.md, config.yaml, per-user `.env`.

---

### Phase 2 — Database backups (not a runtime migration)

**Goal:** Protect against volume loss without changing application database code.

**Scope:**

- [Litestream](https://litestream.io/) continuous replication of each `state.db` to object storage, **or**
- Scheduled `sqlite3 .backup` / dump to S3 with retention policy.

**Benefits:** Point-in-time recovery; sleep better on Fly volume failures.

**Challenges:** One backup stream per profile DB today (many files); operational setup. Does **not** enable horizontal scaling.

---

### Phase 3 — Shared SQL database (when scaling beyond one instance)

**Goal:** One database for all users and profiles; app instances are stateless aside from temp files.

**Scope:**

1. Choose **Postgres** (Neon, Supabase, RDS) or **Turso/libSQL** (SQLite-compatible, lighter dialect change).
2. Schema: add `user_id` and `profile_id` (or slug) to tables currently isolated per `state.db`.
3. Replace `job/db.py` connection logic (`get_db_path()` → connection pool / DSN).
4. Data migration script: import each `profiles/.../state.db` into shared tables.
5. Deprecate per-profile `state.db` files.

**Benefits:** True horizontal scaling; simpler ops; one backup target; enables future features (admin, analytics, cross-device).

**Challenges:** Largest refactor in this plan; embedding column size; migration testing; tenant isolation must be enforced in every query.

**Alternative (Fly-only, advanced):** [LiteFS](https://fly.io/docs/litefs/) for replicated SQLite — possible but adds operational complexity; Postgres is the default recommendation when outgrowing single-instance SQLite.

---

### Phase 4 — Profile & config data (optional follow-up)

**Goal:** Move remaining profile artifacts off the volume or encrypt-at-rest consistently.

**Candidates:**

- `profile.md` / `profile.json` → DB or object storage
- `config.yaml` → DB JSON column
- Per-user `.env` (AI keys) → encrypted secrets table or KMS-backed storage

**Benefits:** Fully stateless app containers; easier GDPR/export/delete per user.

**Challenges:** Setup flow and CLI today assume files on disk; need backward-compatible migration.

---

## 7. Target end state (vision)

### Cloud mode (production)

```
                    ┌─────────────────────────────────┐
                    │   Flask app (1..N instances)     │
                    │   stateless, replaceable         │
                    │   get_blob_storage() / get_db()  │
                    └───────────┬─────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
     ┌────────────────┐ ┌──────────────┐ ┌─────────────────┐
     │ Managed SQL     │ │ Object store  │ │ Temp local disk │
     │ (Postgres/Turso)│ │ via BlobStorage│ │ pdflatex /tmp   │
     │ jobs, embeddings│ │ S3-compatible │ │                 │
     └────────────────┘ └──────────────┘ └─────────────────┘
```

### Local mode (development — permanent)

```
  Flask app  →  get_blob_storage()  →  LocalFilesystemBackend
           →  job/db.py             →  SQLite state.db (unchanged)
           →  profiles/... on disk  →  same tree as today
```

- **SQL:** source of truth for jobs, status, metadata, storage keys.
- **Object storage (cloud):** source of truth for PDF bytes via `BlobStorage`.
- **Local filesystem (local mode):** source of truth for everything durable — no regression.
- **Local temp (both modes):** only for LaTeX compile.

---

## 8. What stays the same — permanently in local mode

Local mode is **not** a temporary fallback. It remains the default developer experience:

- **`./dev.sh` / Docker Compose dev** — `DEPLOYMENT_MODE=local` (or unset)
- **Filesystem layout** under `profiles/` — identical to today
- **SQLite per profile** — no cloud DB required to hack on the app
- **`/pdf/...` routes** — served from disk via `LocalFilesystemBackend`

Cloud mode adds alternate backends behind the same interfaces. Do not remove local backends when Phase 3 ships.

For a **single-instance cloud VPS** that prefers simplicity, `DEPLOYMENT_MODE=local` with a bind mount is still valid (see [HOSTING.md](HOSTING.md)) — object storage is for when you need shared files across instances or smaller volumes.

---

## 9. Implementation checklist (when work starts)

### Phase 0 — Abstraction scaffolding

- [ ] Create `job/storage/` package: `BlobStorage` protocol, `StoredObject` type, `get_blob_storage()` factory
- [ ] Resolve `DEPLOYMENT_MODE` at startup (document in `.env.example`)
- [ ] `LocalFilesystemBackend` — wrap current path logic; must pass all existing tests unchanged

### Phase 1 — Cloud PDFs

- [ ] `S3CompatibleBackend` — single module; S3/R2/MinIO via endpoint + credentials env vars
- [ ] Refactor `job/documents.py` to use `get_blob_storage().put()` (no direct PDF path writes)
- [ ] Refactor `web.py` PDF serving through backend (`get_url` / proxy / local `/pdf/...`)
- [ ] Store `storage_key` in task state; keep `pdf_url` in API responses
- [ ] Migration script for existing PDFs on cloud volumes (uses `BlobStorage.put`)
- [ ] Contract tests: local backend = current behavior; S3 backend = mocked client in CI

### Phase 2 — Backups

- [ ] Choose Litestream vs scheduled dump
- [ ] Document restore procedure in [HOSTING.md](HOSTING.md)

### Phase 3 — Shared SQL

- [ ] `get_database()` factory + `LocalSqliteBackend` (local mode) + `PostgresBackend` (cloud)
- [ ] Schema design with `user_id` / `profile_id`
- [ ] Repository layer in `job/db.py` (or `job/repository.py`) — no vendor SQL in routes
- [ ] One-shot migration from per-profile SQLite files
- [ ] Integration tests for tenant isolation; local mode tests still use file SQLite

---

## 10. Summary table

| Move | Do it? | When | Main benefit | Main challenge |
|------|--------|------|--------------|----------------|
| **`BlobStorage` abstraction** | **Yes** | Phase 0–1 | Local unchanged; vendor swap in one place | Two backends to test |
| PDFs → object storage (cloud only) | **Yes** | Phase 1 | Scale files across instances | Signed URLs + migration |
| Keep local filesystem (local mode) | **Yes** | Always | Zero-friction dev | Must not regress |
| SQLite → S3 (live) | **No** | — | — | Corruption; not a filesystem |
| SQLite on volume | **OK short-term** | Cloud now | Zero migration cost | Single instance only |
| SQLite → object storage backup | **Yes** | Phase 2 | Disaster recovery | Not a scaling fix |
| SQLite → Postgres/Turso (cloud) | **Yes** | Phase 3 | Multi-instance, ops | Largest code migration |
| Profile files → DB/storage | **Maybe** | Phase 4 | Fully stateless app | Setup/CLI changes |

---

## 11. References in this repo

| Topic | Location |
|-------|----------|
| Current hosting & volume layout | [HOSTING.md](HOSTING.md) |
| SQLite access | `job/db.py`, `job/profiles.py` (`get_db_path`) |
| PDF generation | `job/documents.py`, `job/latex.py` |
| PDF HTTP serving | `web.py` (`/pdf/...`, `_pdf_url`) |
| Fly volume mount | `fly.toml` |
| In-memory build state | `job/task_state.py` |
| Proposed storage package | `job/storage/` *(to be created)* |
| Local user id (dev without OAuth) | `job/user_context.py` (`LOCAL_USER_ID`) |

---

*Last updated: 2026-08-08 — includes local/cloud mode split and centralized storage abstraction.*
