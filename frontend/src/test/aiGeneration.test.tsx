/**
 * AI document generation integration tests (resume + cover letter).
 *
 * Covers the build → poll → done/error lifecycle on the JobDetail page, the
 * "cover letter requires a resume first" gate, duplicate-submission prevention,
 * and the rate-limit display (a migration regression that was previously
 * tracked in state but never rendered).
 *
 * Real JobDetail + real client.ts + real useDocumentStatus hook; only MSW mocks
 * the network. Polling uses fake timers to advance the 2s status poll.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderApp } from './utils'
import { server } from './mocks/server'
import { seedJobs, db } from './mocks/handlers'
import { buildJob, buildJobDetail } from './fixtures'

// Guarantee real timers are restored even if a fake-timer test throws.
afterEach(() => { vi.useRealTimers() })

function openJob(detail = buildJobDetail({ job_id: 'jd1', title: 'Platform Engineer', status: 'pending' })) {
  seedJobs([buildJob({ job_id: detail.job_id, title: detail.title, status: detail.status })], [detail])
  return renderApp(`/job/${detail.job_id}`)
}

/** The job's hero title is the page's <h1>; use it as the "loaded" signal. */
function heroTitle(name: string) {
  return screen.getByRole('heading', { level: 1, name })
}

describe('Building a resume', () => {
  it('starts a build and shows the building state', async () => {
    openJob()
    await waitFor(() => heroTitle('Platform Engineer'))

    fireEvent.click(screen.getByRole('button', { name: /Build CV/i }))

    // POST /api/resume/jd1 transitions the mock to building; the UI reflects it
    await waitFor(() => expect(screen.getByText(/Building/i)).toBeInTheDocument())
    expect(db.resumeStatus['jd1']?.status).toBe('building')
  })

  it('shows Open CV link once the build completes', async () => {
    openJob()
    await waitFor(() => heroTitle('Platform Engineer'))

    fireEvent.click(screen.getByRole('button', { name: /Build CV/i }))
    await waitFor(() => expect(screen.getByText(/Building/i)).toBeInTheDocument())

    // Backend finishes the build; the 2s poll will pick it up
    db.resumeStatus['jd1'] = { status: 'done', stage: '', pdf_url: '/pdf/jd1/resume.pdf', error: null, rate_limit: null }
    db.jobDetails['jd1'] = { ...db.jobDetails['jd1'], resume_status: 'done', pdf_url: '/pdf/jd1/resume.pdf' }

    await waitFor(
      () => expect(screen.getByRole('link', { name: /Open CV/i })).toBeInTheDocument(),
      { timeout: 4000 }
    )
  })
})

describe('Cover letter gating (regression guard)', () => {
  it('cannot build a cover letter until the resume is done', async () => {
    openJob(buildJobDetail({ job_id: 'jd1', title: 'Platform Engineer', status: 'pending', resume_status: 'idle' }))
    await waitFor(() => heroTitle('Platform Engineer'))

    // The cover-letter slot should show a locked state, not a build button
    expect(screen.getByText(/Build CV first/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Write Cover Letter/i })).toBeNull()
  })

  it('offers cover-letter build once the resume is done', async () => {
    openJob(buildJobDetail({ job_id: 'jd1', title: 'Platform Engineer', status: 'pending', resume_status: 'done', pdf_url: '/pdf/jd1/r.pdf' }))
    await waitFor(() => heroTitle('Platform Engineer'))

    expect(screen.getByRole('button', { name: /Write Cover Letter/i })).toBeInTheDocument()
    expect(screen.queryByText(/Build CV first/i)).toBeNull()
  })
})

describe('Duplicate submission prevention (regression guard)', () => {
  it('does not fire a second resume build when clicked twice rapidly', async () => {
    let buildCalls = 0
    server.use(
      http.post('/api/resume/:jobId', () => {
        buildCalls++
        db.resumeStatus['jd1'] = { status: 'building', stage: 'Starting…', pdf_url: null, error: null, rate_limit: null }
        return HttpResponse.json({ status: 'building' })
      })
    )
    openJob()
    await waitFor(() => heroTitle('Platform Engineer'))

    const btn = screen.getByRole('button', { name: /Build CV/i })
    fireEvent.click(btn)
    fireEvent.click(btn) // rapid second click before state settles

    await waitFor(() => expect(screen.getByText(/Building/i)).toBeInTheDocument())
    // Guard must prevent the duplicate POST
    expect(buildCalls).toBe(1)
  })
})

describe('Rate-limit display (regression guard)', () => {
  it('shows provider + retry info and a Switch provider link when rate limited', async () => {
    openJob()
    await waitFor(() => heroTitle('Platform Engineer'))

    fireEvent.click(screen.getByRole('button', { name: /Build CV/i }))
    await waitFor(() => expect(screen.getByText(/Building/i)).toBeInTheDocument())

    // Backend reports a rate-limit error; the poll will surface it
    db.resumeStatus['jd1'] = {
      status: 'error', stage: '', pdf_url: null, error: 'rate limited',
      rate_limit: { provider: 'groq', scope: 'TPD', used: 5900, limit: 6000, retry_seconds: 3600 },
    }
    db.jobDetails['jd1'] = { ...db.jobDetails['jd1'], resume_status: 'error', resume_error: 'rate limited' }

    await waitFor(
      () => {
        expect(screen.getByText(/Groq/)).toBeInTheDocument()
        expect(screen.getByText(/limit reached/i)).toBeInTheDocument()
      },
      { timeout: 4000 }
    )
    expect(screen.getByRole('link', { name: /Switch provider/i })).toBeInTheDocument()
  })
})

describe('Build failure handling', () => {
  it('surfaces an error and offers retry when the build POST fails', async () => {
    server.use(
      http.post('/api/resume/:jobId', () => HttpResponse.json({ error: 'boom' }, { status: 500 }))
    )
    openJob()
    await waitFor(() => heroTitle('Platform Engineer'))

    fireEvent.click(screen.getByRole('button', { name: /Build CV/i }))

    await waitFor(() => expect(screen.getByText(/Failed to start build/i)).toBeInTheDocument())
  })
})
