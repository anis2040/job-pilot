/**
 * Migration-regression + error-recovery integration tests.
 *
 * Each test here guards a behaviour that existed in the original Jinja app and
 * was dropped or weakened in the React migration (evidence: index.html
 * runFetch/saveSettings/switchProfile, job_detail.html status handling).
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderApp } from './utils'
import { server } from './mocks/server'
import { seedJobs, db } from './mocks/handlers'
import { buildJob, buildSearchConfig } from './fixtures'

afterEach(() => vi.useRealTimers())

describe('Job list load failure (regression: silent swallow)', () => {
  it('shows an error state with retry when the jobs request fails', async () => {
    server.use(http.get('/api/jobs', () => HttpResponse.json({ error: 'down' }, { status: 500 })))
    renderApp('/')
    await waitFor(() => {
      expect(screen.getByText(/Couldn't load jobs/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument()
    })
  })

  it('retry re-requests and recovers once the server is back', async () => {
    let fail = true
    server.use(http.get('/api/jobs', () => {
      if (fail) return HttpResponse.json({ error: 'down' }, { status: 500 })
      return HttpResponse.json([buildJob({ job_id: 'r1', title: 'Recovered Job', status: 'pending' })])
    }))
    renderApp('/')
    await waitFor(() => expect(screen.getByText(/Couldn't load jobs/i)).toBeInTheDocument())

    fail = false
    fireEvent.click(screen.getByRole('button', { name: /Retry/i }))

    await waitFor(() => expect(screen.getByText('Recovered Job')).toBeInTheDocument())
  })
})

describe('Fetch jobs with progress (regression: field mismatch + leak)', () => {
  it('polls fetch-status and shows the real progress message', async () => {
    // fetch-status returns { status, message } — the migration briefly read { running }
    let polls = 0
    server.use(
      http.post('/api/fetch', () => { db.fetchStatus = { status: 'running', message: 'Starting fetch…' }; return HttpResponse.json({ status: 'running' }) }),
      http.get('/api/fetch-status', () => {
        polls++
        if (polls >= 2) return HttpResponse.json({ status: 'done', message: 'Done' })
        return HttpResponse.json({ status: 'running', message: 'Fetching LinkedIn…' })
      })
    )
    seedJobs([])
    renderApp('/')
    await waitFor(() => expect(screen.getByText(/No pending jobs/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Fetch jobs now/i }))

    // The real progress message from the API must be shown
    await waitFor(() => expect(screen.getByText(/Fetching LinkedIn/i)).toBeInTheDocument(), { timeout: 4000 })
  })

  it('surfaces an error if the fetch trigger fails', async () => {
    server.use(http.post('/api/fetch', () => HttpResponse.json({ error: 'nope' }, { status: 500 })))
    seedJobs([])
    renderApp('/')
    await waitFor(() => expect(screen.getByText(/No pending jobs/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Fetch jobs now/i }))
    await waitFor(() => expect(screen.getByText(/Could not start fetch/i)).toBeInTheDocument())
  })
})

describe('Settings save clears stale jobs and re-fetches (regression)', () => {
  it('after saving fetch settings, old jobs are cleared and a fetch is triggered', async () => {
    let cleared = false
    let fetchTriggered = false
    server.use(
      http.post('/api/jobs/clear', () => { cleared = true; db.jobs = []; return HttpResponse.json({ ok: true }) }),
      http.post('/api/config', async ({ request }) => { await request.json(); return HttpResponse.json({ ok: true }) }),
      http.post('/api/fetch', () => { fetchTriggered = true; db.fetchStatus = { status: 'done', message: '' }; return HttpResponse.json({ status: 'running' }) }),
    )
    db.config = buildSearchConfig({
      searches: [{ name: 'LinkedIn - PM', source: 'LinkedIn', query: 'PM', location: 'US', max_pages: 3, remote: true }],
    })
    seedJobs([buildJob({ job_id: 'old1', title: 'Old Job', status: 'pending' })])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Old Job')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Search settings/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Save settings/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Save settings/i }))

    await waitFor(() => {
      expect(cleared).toBe(true)
      expect(fetchTriggered).toBe(true)
    })
  })

  it('shows an error and does not close on save failure', async () => {
    server.use(http.post('/api/config', () => HttpResponse.json({ error: 'bad config' }, { status: 400 })))
    db.config = buildSearchConfig({
      searches: [{ name: 'LinkedIn - PM', source: 'LinkedIn', query: 'PM', location: 'US', max_pages: 3, remote: true }],
    })
    seedJobs([buildJob({ job_id: 'old1', title: 'Old Job', status: 'pending' })])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Old Job')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Search settings/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Save settings/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Save settings/i }))

    await waitFor(() => expect(screen.getByText(/Could not save settings/i)).toBeInTheDocument())
    // modal still open
    expect(screen.getByRole('button', { name: /Save settings/i })).toBeInTheDocument()
  })
})

describe('Profile switch to empty profile auto-fetches (regression)', () => {
  it('switching to a profile with no jobs triggers a fetch', async () => {
    let fetchTriggered = false
    db.profiles = [
      { slug: 'p1', name: 'p1', label: 'Primary', initials: 'P', color: '#3b82f6', active: true },
      { slug: 'p2', name: 'p2', label: 'Secondary', initials: 'S', color: '#f59e0b', active: false },
    ]
    db.activeSlug = 'p1'
    seedJobs([buildJob({ job_id: 'x', title: 'Existing Job', status: 'pending' })])
    server.use(
      http.post('/api/profiles/switch/:slug', ({ params }) => {
        db.profiles = db.profiles.map(p => ({ ...p, active: p.slug === params.slug }))
        db.activeSlug = params.slug as string
        db.jobs = []                        // new profile has no jobs
        return HttpResponse.json({ ok: true, slug: params.slug, empty: true })
      }),
      http.post('/api/fetch', () => { fetchTriggered = true; db.fetchStatus = { status: 'done', message: '' }; return HttpResponse.json({ status: 'running' }) }),
    )

    renderApp('/')
    await waitFor(() => expect(screen.getByText('Existing Job')).toBeInTheDocument())

    // Open the profile dropdown and switch to the empty profile
    fireEvent.click(screen.getByLabelText('Profile menu'))
    await waitFor(() => expect(screen.getByRole('menu')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('menuitem', { name: /Secondary/i }))

    await waitFor(() => expect(fetchTriggered).toBe(true), { timeout: 4000 })
  })
})
