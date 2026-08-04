/**
 * MSW request handlers modelling the Flask API at the network boundary.
 *
 * A small in-memory `db` holds state so handlers behave like a real backend:
 * changing a job's status via POST is reflected in subsequent GETs, building a
 * resume transitions its status, etc.  Tests seed `db` and override handlers
 * with `server.use(...)` for edge cases (errors, slow responses).
 *
 * URLs and response shapes mirror web.py exactly — so these handlers exercise
 * the real client.ts URL construction and response parsing.
 */

import { http, HttpResponse } from 'msw'
import type { Job, JobDetail, SearchConfig, FetchStatus, DocumentStatus, Profile } from '@/api/types'
import { buildProfile, buildSearchConfig, buildFetchStatus } from '../fixtures'

interface Db {
  jobs: Job[]
  jobDetails: Record<string, JobDetail>
  profiles: Profile[]
  activeSlug: string | null
  config: SearchConfig
  fetchStatus: FetchStatus
  resumeStatus: Record<string, DocumentStatus>
  clStatus: Record<string, DocumentStatus>
  sources: string[]
}

export const db: Db = {
  jobs: [],
  jobDetails: {},
  profiles: [buildProfile()],
  activeSlug: 'default',
  config: buildSearchConfig(),
  fetchStatus: buildFetchStatus(),
  resumeStatus: {},
  clStatus: {},
  sources: ['LinkedIn', 'Jobicy', 'Himalayas', 'Greenhouse'],
}

export function resetDb() {
  db.jobs = []
  db.jobDetails = {}
  db.profiles = [buildProfile()]
  db.activeSlug = 'default'
  db.config = buildSearchConfig()
  db.fetchStatus = buildFetchStatus()
  db.resumeStatus = {}
  db.clStatus = {}
  db.sources = ['LinkedIn', 'Jobicy', 'Himalayas', 'Greenhouse']
}

/** Seed the job store; also registers each as a fetchable detail. */
export function seedJobs(jobs: Job[], details: JobDetail[] = []) {
  db.jobs = jobs
  for (const j of jobs) {
    db.jobDetails[j.job_id] = { ...(j as JobDetail), description: '', salary_range: null, employment_type: null, status_updated_at: null }
  }
  for (const d of details) db.jobDetails[d.job_id] = d
}

export const handlers = [
  // ── Jobs ──
  http.get('/api/jobs', ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status') ?? 'pending'
    return HttpResponse.json(db.jobs.filter(j => j.status === status))
  }),

  http.get('/api/job-counts', () => HttpResponse.json({
    pending: db.jobs.filter(j => j.status === 'pending').length,
    applied: db.jobs.filter(j => j.status === 'applied').length,
    skipped: db.jobs.filter(j => j.status === 'skipped').length,
  })),

  http.get('/api/job/:jobId', ({ params }) => {
    const detail = db.jobDetails[params.jobId as string]
    if (!detail) return HttpResponse.json({ error: 'Job not found' }, { status: 404 })
    return HttpResponse.json(detail)
  }),

  http.get('/api/job/:jobId/description', ({ params }) => {
    const detail = db.jobDetails[params.jobId as string]
    return HttpResponse.json({ description: detail?.description ?? '', remote: detail?.remote ?? '', match: detail?.match ?? null })
  }),

  http.get('/api/jobs/similar/:jobId', () => HttpResponse.json([])),

  http.post('/api/job-status/:jobId/:newStatus', ({ params }) => {
    const { jobId, newStatus } = params as { jobId: string; newStatus: string }
    if (!['applied', 'skipped', 'pending'].includes(newStatus)) {
      return HttpResponse.json({ error: 'Invalid status' }, { status: 400 })
    }
    const job = db.jobs.find(j => j.job_id === jobId)
    if (job) job.status = newStatus as Job['status']
    if (db.jobDetails[jobId]) db.jobDetails[jobId].status = newStatus as Job['status']
    return HttpResponse.json({ ok: true })
  }),

  http.post('/api/jobs/clear', () => {
    db.jobs = []
    return HttpResponse.json({ ok: true })
  }),

  // ── Documents ──
  http.post('/api/resume/:jobId', ({ params }) => {
    const jobId = params.jobId as string
    db.resumeStatus[jobId] = { status: 'building', stage: 'Starting…', pdf_url: null, error: null, rate_limit: null }
    return HttpResponse.json({ status: 'building' })
  }),
  http.get('/api/resume-status/:jobId', ({ params }) => {
    const jobId = params.jobId as string
    return HttpResponse.json(db.resumeStatus[jobId] ?? { status: 'idle', stage: '', pdf_url: null, error: null, rate_limit: null })
  }),
  http.post('/api/cover-letter/:jobId', ({ params }) => {
    const jobId = params.jobId as string
    db.clStatus[jobId] = { status: 'building', stage: 'Starting…', pdf_url: null, error: null, rate_limit: null }
    return HttpResponse.json({ status: 'building' })
  }),
  http.get('/api/cover-letter-status/:jobId', ({ params }) => {
    const jobId = params.jobId as string
    return HttpResponse.json(db.clStatus[jobId] ?? { status: 'idle', stage: '', pdf_url: null, error: null, rate_limit: null, preview: '' })
  }),

  // ── Fetch ──
  http.post('/api/fetch', () => {
    db.fetchStatus = { status: 'running', message: 'Starting fetch…' }
    return HttpResponse.json({ status: 'running' })
  }),
  http.get('/api/fetch-status', () => HttpResponse.json(db.fetchStatus)),

  // ── Config ──
  http.get('/api/config', () => HttpResponse.json(db.config)),
  http.post('/api/config', async ({ request }) => {
    db.config = (await request.json()) as SearchConfig
    return HttpResponse.json({ ok: true, fetch_required: false })
  }),

  // ── Profiles ──
  http.get('/api/profiles', () => HttpResponse.json({ profiles: db.profiles, active_slug: db.activeSlug })),
  http.get('/api/profiles/active', () => {
    const active = db.profiles.find(p => p.active)
    return HttpResponse.json({ active: active ?? null })
  }),
  http.post('/api/profiles/new', () => HttpResponse.json({ ok: true, slug: 'new-profile' })),
  http.post('/api/profiles/switch/:slug', ({ params }) => {
    const slug = params.slug as string
    db.profiles = db.profiles.map(p => ({ ...p, active: p.slug === slug }))
    db.activeSlug = slug
    return HttpResponse.json({ ok: true, slug, empty: db.jobs.length === 0 })
  }),
  http.post('/api/profiles/delete/:slug', () => HttpResponse.json({ ok: true })),
  http.post('/api/profiles/:slug/label', async ({ request }) => {
    await request.json()
    return HttpResponse.json({ ok: true })
  }),
  http.get('/api/profiles/:slug/profile-md', () => HttpResponse.json({ content: '' })),
  http.post('/api/profiles/:slug/profile-md', async ({ request }) => {
    await request.json()
    return HttpResponse.json({ ok: true })
  }),
  http.get('/api/profiles/:slug/config', () => HttpResponse.json(db.config)),
  http.post('/api/profiles/:slug/config', async ({ request }) => {
    db.config = (await request.json()) as SearchConfig
    return HttpResponse.json({ ok: true, fetch_required: false })
  }),
  http.post('/api/profiles/:slug/clear-jobs', () => HttpResponse.json({ ok: true })),

  // ── Constants ──
  http.get('/api/constants', () => HttpResponse.json({
    sources: db.sources, remote_types: ['Remote', 'Hybrid', 'On-site'], remote_css: {}, job_statuses: ['pending', 'applied', 'skipped'], default_blacklist: [],
  })),
  http.get('/api/sources', () => HttpResponse.json(db.sources)),

  // ── AI settings (minimal) ──
  http.get('/api/ai-settings', () => HttpResponse.json({
    active_provider: 'groq', preferred_provider: 'groq', semantic_match: false, embeddings_available: false, providers: {},
  })),
]
