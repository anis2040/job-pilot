/**
 * E2E-style integration tests for single-VM performance optimizations.
 *
 * Uses MSW + fake timers to assert client-side throttling and visibility
 * behaviour without a real browser or backend process.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderApp } from './utils'
import { server } from './mocks/server'
import { seedJobs } from './mocks/handlers'
import {
  FETCH_JOBS_RELOAD_MS,
  FETCH_STATUS_POLL_MS,
} from '@/pages/Dashboard/hooks/useJobFetch'

describe('Performance optimizations (E2E)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('throttles /api/jobs reloads while fetch is running', async () => {
    let jobsCalls = 0
    server.use(
      http.post('/api/fetch', () =>
        HttpResponse.json({ status: 'running', started: true })
      ),
      http.get('/api/fetch-status', () =>
        HttpResponse.json({ status: 'running', message: 'Fetching LinkedIn…' })
      ),
      http.get('/api/jobs', () => {
        jobsCalls++
        return HttpResponse.json([])
      }),
      http.get('/api/job-counts', () =>
        HttpResponse.json({ pending: 0, applied: 0, skipped: 0 })
      )
    )

    seedJobs([])
    renderApp('/')
    await waitFor(() => expect(screen.getByText(/No pending jobs/i)).toBeInTheDocument())

    const beforeFetch = jobsCalls
    fireEvent.click(screen.getByRole('button', { name: /Fetch jobs now/i }))

    await waitFor(() => expect(jobsCalls).toBeGreaterThan(beforeFetch))
    const afterFirstReload = jobsCalls

    // Several status polls — should not reload the full job list yet.
    await vi.advanceTimersByTimeAsync(FETCH_STATUS_POLL_MS * 5)
    expect(jobsCalls).toBe(afterFirstReload)

    // Cross the 12s reload window.
    await vi.advanceTimersByTimeAsync(FETCH_JOBS_RELOAD_MS)
    await waitFor(() => expect(jobsCalls).toBeGreaterThan(afterFirstReload))
  })

  it('pauses dashboard refresh while the tab is hidden', async () => {
    let jobsCalls = 0
    server.use(
      http.get('/api/jobs', () => {
        jobsCalls++
        return HttpResponse.json([])
      })
    )

    seedJobs([])
    renderApp('/')
    await waitFor(() => expect(screen.getByText(/No pending jobs/i)).toBeInTheDocument())
    const baseline = jobsCalls

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'hidden',
    })
    document.dispatchEvent(new Event('visibilitychange'))

    await vi.advanceTimersByTimeAsync(120_000)
    expect(jobsCalls).toBe(baseline)

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'visible',
    })
    document.dispatchEvent(new Event('visibilitychange'))
    await waitFor(() => expect(jobsCalls).toBeGreaterThan(baseline))
  })

  it('surfaces server-busy message when fetch returns 429', async () => {
    server.use(
      http.post('/api/fetch', () =>
        HttpResponse.json(
          { status: 'idle', started: false, message: 'Server busy — 2 fetch(es) already running. Try again shortly.' },
          { status: 429 }
        )
      )
    )

    seedJobs([])
    renderApp('/')
    await waitFor(() => expect(screen.getByText(/No pending jobs/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Fetch jobs now/i }))
    await waitFor(() =>
      expect(screen.getByText(/Server busy — 2 fetch\(es\) already running/i)).toBeInTheDocument()
    )
  })
})
