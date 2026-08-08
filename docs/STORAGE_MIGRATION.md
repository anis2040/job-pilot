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

---

## 2. Current architecture (what lives where)

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

## 3. Why we need to change something

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

## 4. Key decision: PDFs to object storage, SQLite stays off object storage

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
| Code paths assume filesystem paths | Introduce a storage abstraction; store `pdf_url` or object key in DB/task state, not `pdf_path` |
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

## 5. Phased migration plan

Each phase is independently valuable. Later phases do not block shipping earlier ones.

### Phase 1 — PDFs to object storage (recommended first)

**Goal:** Generated resumes and cover letters live in object storage; app serves links, not local files.

**Scope:**

1. Add a `StorageBackend` interface (e.g. `put_pdf`, `get_url`, `delete`).
2. After `pdflatex` in `job/documents.py`, upload PDF → store returned URL/key.
3. Replace `/pdf/<path>` disk serving with signed URLs or `/api/documents/...` proxy.
4. Update API fields (`pdf_url`, `cl_pdf_url`) — frontend already consumes URLs.
5. Env config: `STORAGE_BACKEND=s3|r2|local`, bucket, credentials (server `.env` only).

**Benefits:** Unlocks multi-instance PDF access; reduces volume size; clearest ROI for engineering effort.

**Challenges:** Storage credentials in production; signed URL expiry; migrating existing PDFs; keeping local dev simple (default `local` backend).

**Out of scope for phase 1:** SQLite, profile.md, config.yaml, per-user `.env`.

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

## 6. Target end state (vision)

```
                    ┌─────────────────────────────────┐
                    │   Flask app (1..N instances)     │
                    │   stateless, replaceable         │
                    └───────────┬─────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
     ┌────────────────┐ ┌──────────────┐ ┌─────────────────┐
     │ Managed SQL     │ │ Object store  │ │ Temp local disk │
     │ (Postgres/Turso)│ │ PDFs, backups │ │ pdflatex /tmp   │
     │ jobs, embeddings│ │               │ │                 │
     └────────────────┘ └──────────────┘ └─────────────────┘
```

- **SQL:** source of truth for jobs, status, metadata, URLs to PDFs.
- **Object storage:** source of truth for PDF bytes.
- **Local temp:** only for LaTeX compile; nothing durable.

---

## 7. What stays the same for now

Until phases complete:

- **Docker Compose / `./data/profiles`** remains valid for local dev and small VPS deploys.
- **SQLite on a volume** remains acceptable for **low traffic, single instance** (current Fly setup).
- **Per-user Google auth** and profile isolation semantics unchanged — only the storage layer moves.

Do not delete the volume-first path until Phase 3+ is done and tested.

---

## 8. Implementation checklist (when work starts)

### Phase 1 — PDFs

- [ ] Define `StorageBackend` protocol + `local` and `s3` (or R2) implementations
- [ ] Wire upload after successful `pdflatex` in `job/documents.py`
- [ ] Store object key or HTTPS URL in task state / job metadata
- [ ] Replace or supplement `serve_pdf` in `web.py`
- [ ] Document env vars in `.env.example`
- [ ] Migration script for existing PDFs on disk
- [ ] Tests with mocked storage (no real bucket in CI)

### Phase 2 — Backups

- [ ] Choose Litestream vs scheduled dump
- [ ] Document restore procedure in [HOSTING.md](HOSTING.md)

### Phase 3 — Shared SQL

- [ ] Schema design with `user_id` / `profile_id`
- [ ] Adapter layer in `job/db.py` (or rename to `job/repository.py`)
- [ ] One-shot migration from per-profile SQLite files
- [ ] Integration tests for tenant isolation

---

## 9. Summary table

| Move | Do it? | When | Main benefit | Main challenge |
|------|--------|------|--------------|----------------|
| PDFs → object storage | **Yes** | Phase 1 | Scale files across instances | LaTeX temp + signed URLs |
| SQLite → S3 (live) | **No** | — | — | Corruption; not a filesystem |
| SQLite on volume | **OK short-term** | Now | Zero migration cost | Single instance only |
| SQLite → object storage backup | **Yes** | Phase 2 | Disaster recovery | Not a scaling fix |
| SQLite → Postgres/Turso | **Yes** | Phase 3 | Multi-instance, ops | Largest code migration |
| Profile files → DB/storage | **Maybe** | Phase 4 | Fully stateless app | Setup/CLI changes |

---

## 10. References in this repo

| Topic | Location |
|-------|----------|
| Current hosting & volume layout | [HOSTING.md](HOSTING.md) |
| SQLite access | `job/db.py`, `job/profiles.py` (`get_db_path`) |
| PDF generation | `job/documents.py`, `job/latex.py` |
| PDF HTTP serving | `web.py` (`/pdf/...`, `_pdf_url`) |
| Fly volume mount | `fly.toml` |
| In-memory build state | `job/task_state.py` |

---

*Last updated: 2026-08-08 — captured from architecture discussion before implementation.*
