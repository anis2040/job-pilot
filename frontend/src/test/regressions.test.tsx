/**
 * Migration-regression + error-recovery integration tests.
 *
 * Each test here guards a behaviour that existed in the original Jinja app and
 * was dropped or weakened in the React migration (evidence: index.html
 * runFetch/saveSettings/switchProfile, job_detail.html status handling).
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderApp } from './utils'
import { server } from './mocks/server'
import { seedJobs, db } from './mocks/handlers'
import { buildJob, buildJobDetail, buildMatch, buildSearchConfig } from './fixtures'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

function setWideViewport() {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1400 })
  window.dispatchEvent(new Event('resize'))
}

describe('Shared app header', () => {
  it('is present exactly once on dashboard routes', async () => {
    seedJobs([buildJob({ job_id: 'header-1', title: 'Header Role', status: 'pending' })])

    renderApp('/')
    await waitFor(() => expect(screen.getByText('Header Role')).toBeInTheDocument())

    expect(screen.getByLabelText('JobPilot AI home')).toBeInTheDocument()
    expect(document.querySelectorAll('.app-header')).toHaveLength(1)
  })

  it('is present exactly once on secondary pages', async () => {
    renderApp('/ai-settings')

    await waitFor(() => expect(screen.getByText(/AI Model Settings/i)).toBeInTheDocument())
    expect(screen.getByLabelText('JobPilot AI home')).toBeInTheDocument()
    expect(document.querySelectorAll('.app-header')).toHaveLength(1)
  })
})

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

  it('shows newly fetched jobs before the full fetch run finishes', async () => {
    let polls = 0
    server.use(
      http.post('/api/fetch', () => {
        db.fetchStatus = { status: 'running', message: 'Starting fetch…' }
        return HttpResponse.json({ status: 'running' })
      }),
      http.get('/api/fetch-status', () => {
        polls++
        if (polls === 1) {
          db.jobs = [buildJob({ job_id: 'stream-1', title: 'Streaming Job', status: 'pending' })]
          db.fetchStatus = { status: 'running', message: 'Fetching Jobicy…' }
          return HttpResponse.json(db.fetchStatus)
        }
        if (polls >= 3) {
          db.fetchStatus = { status: 'done', message: 'Done' }
          return HttpResponse.json(db.fetchStatus)
        }
        return HttpResponse.json({ status: 'running', message: 'Fetching LinkedIn…' })
      })
    )
    seedJobs([])
    renderApp('/')
    await waitFor(() => expect(screen.getByText(/No pending jobs/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Fetch jobs now/i }))

    await waitFor(() => expect(screen.getByText('Streaming Job')).toBeInTheDocument(), { timeout: 2800 })
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

describe('Settings save refresh strategy', () => {
  it('narrowing work styles updates local filters without clearing or fetching', async () => {
    let cleared = false
    let fetchTriggered = false
    server.use(
      http.post('/api/jobs/clear', () => { cleared = true; db.jobs = []; return HttpResponse.json({ ok: true }) }),
      http.post('/api/config', async ({ request }) => { db.config = (await request.json()) as typeof db.config; return HttpResponse.json({ ok: true, fetch_required: false }) }),
      http.post('/api/fetch', () => { fetchTriggered = true; db.fetchStatus = { status: 'done', message: '' }; return HttpResponse.json({ status: 'running' }) }),
    )
    db.config = buildSearchConfig({
      searches: [{
        group_id: 'search-1',
        name: 'LinkedIn - Engineer',
        source: 'LinkedIn',
        query: 'Engineer',
        location: 'US',
        max_pages: 3,
        remote: true,
        work_styles: ['Remote', 'Hybrid'],
      }],
    })
    seedJobs([
      buildJob({ job_id: 'remote1', title: 'Remote Engineer', source: 'LinkedIn', remote: 'Remote', status: 'pending' }),
      buildJob({ job_id: 'hybrid1', title: 'Hybrid Engineer', source: 'LinkedIn', remote: 'Hybrid', status: 'pending' }),
    ])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Remote Engineer')).toBeInTheDocument())
    expect(screen.getByText('Hybrid Engineer')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Search settings/i }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Hybrid/i }))
    fireEvent.click(screen.getByRole('button', { name: /Save settings/i }))

    await waitFor(() => {
      expect(screen.queryByText('Hybrid Engineer')).toBeNull()
      expect(screen.getByText('Remote Engineer')).toBeInTheDocument()
    })
    expect(cleared).toBe(false)
    expect(fetchTriggered).toBe(false)
  })

  it('expanded settings trigger an incremental fetch without clearing existing jobs', async () => {
    let cleared = false
    let fetchTriggered = false
    server.use(
      http.post('/api/jobs/clear', () => { cleared = true; db.jobs = []; return HttpResponse.json({ ok: true }) }),
      http.post('/api/config', async ({ request }) => { db.config = (await request.json()) as typeof db.config; return HttpResponse.json({ ok: true, fetch_required: true }) }),
      http.post('/api/fetch', () => { fetchTriggered = true; db.fetchStatus = { status: 'done', message: '' }; return HttpResponse.json({ status: 'running' }) }),
    )
    db.config = buildSearchConfig({
      searches: [{ name: 'LinkedIn - Old Job', source: 'LinkedIn', query: 'Old Job', location: 'US', max_pages: 3, remote: true }],
    })
    seedJobs([buildJob({ job_id: 'old1', title: 'Old Job', status: 'pending' })])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Old Job')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Search settings/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Save settings/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Save settings/i }))

    await waitFor(() => expect(fetchTriggered).toBe(true))
    expect(cleared).toBe(false)
  })

  it('shows an error and does not close on save failure', async () => {
    server.use(http.post('/api/config', () => HttpResponse.json({ error: 'bad config' }, { status: 400 })))
    db.config = buildSearchConfig({
      searches: [{ name: 'LinkedIn - Old Job', source: 'LinkedIn', query: 'Old Job', location: 'US', max_pages: 3, remote: true }],
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

  it('syncs the filter bar from the saved fetch settings', async () => {
    server.use(
      http.post('/api/fetch', () => { db.fetchStatus = { status: 'done', message: '' }; return HttpResponse.json({ status: 'running' }) }),
    )
    db.config = buildSearchConfig({
      searches: [{
        group_id: 'search-1',
        name: 'LinkedIn - Product Manager',
        source: 'LinkedIn',
        query: 'Product Manager',
        location: 'Germany',
        max_pages: 3,
        remote: false,
        work_styles: ['Hybrid'],
      }],
    })
    seedJobs([buildJob({ job_id: 'pm1', title: 'Product Manager', source: 'LinkedIn', remote: 'Hybrid', status: 'pending' })])

    renderApp('/')
    await waitFor(() => expect(screen.getByText('Product Manager')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Search settings/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Save settings/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Save settings/i }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByLabelText('Search jobs')).toHaveValue('Product Manager')
    expect(screen.getAllByRole('button', { name: /Hybrid/i }).find(el => el.classList.contains('filter-chip'))).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getAllByRole('button', { name: /Remote/i }).find(el => el.classList.contains('filter-chip'))).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByLabelText('Filter by source')).toHaveValue('LinkedIn')
  })
})

describe('Dashboard row skill details (regression guard)', () => {
  it('keeps extracted skill names out of the compact job row', async () => {
    seedJobs([
      buildJob({
        job_id: 'matched-1',
        title: 'Platform Engineer',
        match: buildMatch({ matched: ['GraphQL'], missing: ['Terraform'], semantic_score: 76 }),
      }),
    ])
    renderApp('/')

    await waitFor(() => expect(screen.getByText('Platform Engineer')).toBeInTheDocument())
    expect(screen.getByText('76% fit')).toBeInTheDocument()
    expect(screen.queryByText('GraphQL')).toBeNull()
    expect(screen.queryByText('Terraform')).toBeNull()
  })
})

describe('Pagination scroll behavior (regression guard)', () => {
  it('changes pages without forcing the window back to the top', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    seedJobs(Array.from({ length: 26 }, (_, i) => buildJob({
      job_id: `paged-${i + 1}`,
      title: `Paged Job ${i + 1}`,
      status: 'pending',
    })))

    renderApp('/')
    await waitFor(() => expect(screen.getByText('Paged Job 1')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))

    await waitFor(() => expect(screen.getByText('Paged Job 26')).toBeInTheDocument())
    expect(scrollTo).not.toHaveBeenCalled()
  })
})

describe('Workplace badge correction (regression guard)', () => {
  it('updates the row from Remote to Hybrid when the full description has the stronger signal', async () => {
    setWideViewport()
    server.use(
      http.get('/api/job/:jobId/description', () => HttpResponse.json({
        description: 'Hybrid work model with regular office collaboration days.',
        remote: 'Hybrid',
        match: null,
      }))
    )
    seedJobs([
      buildJob({ job_id: 'hybrid-1', title: 'Platform Engineer', status: 'pending', remote: 'Remote' }),
    ])

    renderApp('/')
    await waitFor(() => expect(screen.getByText('Platform Engineer')).toBeInTheDocument())

    expect(within(screen.getByTestId('job-row-hybrid-1')).getByText('Remote')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Platform Engineer'))

    await waitFor(() => expect(within(screen.getByTestId('job-row-hybrid-1')).getByText('Hybrid')).toBeInTheDocument())
    expect(within(screen.getByTestId('job-row-hybrid-1')).queryByText('Remote')).toBeNull()
  })

  it('fetches the full StepStone description even when the stored row has a snippet', async () => {
    setWideViewport()
    let descriptionFetches = 0
    const fullDescription = 'Was Deinen Job ausmacht\n• Begleitung der Entwicklung komplexer Webprojekte\nDas wünschen wir uns\nSehr gute Deutschkenntnisse'
    const job = buildJob({
      job_id: 'ss_3',
      title: 'Frontend Engineer',
      source: 'StepStone',
      status: 'pending',
    })
    seedJobs([job], [buildJobDetail({ ...job, description: 'Remote work possible' })])
    server.use(
      http.get('/api/job/:jobId/description', () => {
        descriptionFetches++
        return HttpResponse.json({ description: fullDescription, remote: 'Hybrid', match: null })
      })
    )

    renderApp('/')
    await waitFor(() => expect(screen.getByText('Frontend Engineer')).toBeInTheDocument())

    fireEvent.click(screen.getByText('Frontend Engineer'))

    await waitFor(() => expect(screen.getByText(/Was Deinen Job ausmacht/)).toBeInTheDocument())
    expect(screen.getByText(/Sehr gute Deutschkenntnisse/)).toBeInTheDocument()
    expect(descriptionFetches).toBe(1)
  })

  it('fetches full StepStone descriptions on the standalone detail page', async () => {
    const fullDescription = 'Was wir Dir bieten\n• 50 % remote arbeiten\nUnbefristeter Arbeitsvertrag'
    const job = buildJob({
      job_id: 'ss_4',
      title: 'Angular Developer',
      source: 'StepStone',
      status: 'pending',
    })
    seedJobs([job], [buildJobDetail({ ...job, description: 'Short StepStone snippet' })])
    server.use(
      http.get('/api/job/:jobId/description', () => HttpResponse.json({
        description: fullDescription,
        remote: 'Hybrid',
        match: null,
      }))
    )

    renderApp('/job/ss_4')
    await waitFor(() => expect(screen.getAllByText('Angular Developer').length).toBeGreaterThan(0))

    await waitFor(() => expect(screen.getByText(/Was wir Dir bieten/)).toBeInTheDocument())
    expect(screen.getByText(/Unbefristeter Arbeitsvertrag/)).toBeInTheDocument()
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
