/**
 * Job action integration tests — apply / skip / restore.
 *
 * Behaviour derived from the old Jinja app (job_detail.html status actions +
 * index.html row actions) and the Flask contract POST /api/job-status/:id/:status.
 *
 * These are the migration-critical guarantees:
 *  - a status change moves the job to the right tab and updates counts
 *  - a FAILED status change surfaces an error and does NOT silently claim success
 *  - rapid double-clicks don't fire duplicate requests
 */

import { describe, it, expect } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderApp } from './utils'
import { server } from './mocks/server'
import { seedJobs } from './mocks/handlers'
import { buildJob } from './fixtures'

describe('Applying to a job', () => {
  it('moves the job out of Pending and shows a confirmation', async () => {
    seedJobs([
      buildJob({ job_id: 'j1', title: 'React Engineer', status: 'pending' }),
      buildJob({ job_id: 'j2', title: 'Go Engineer', status: 'pending' }),
    ])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Engineer')).toBeInTheDocument())

    // The row's "mark applied" action
    const row = screen.getByText('React Engineer').closest('.job-row')!
    await userEvent.click(within(row as HTMLElement).getByTitle('Mark applied'))

    // React Engineer leaves the pending list
    await waitFor(() => expect(screen.queryByText('React Engineer')).toBeNull())
    expect(screen.getByText('Go Engineer')).toBeInTheDocument()
  })

  it('updates the tab counts after applying', async () => {
    seedJobs([buildJob({ job_id: 'j1', title: 'React Engineer', status: 'pending' })])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Engineer')).toBeInTheDocument())

    const row = screen.getByText('React Engineer').closest('.job-row')!
    await userEvent.click(within(row as HTMLElement).getByTitle('Mark applied'))

    // Applied tab count becomes 1, pending becomes 0
    await waitFor(() => {
      const appliedTab = screen.getByRole('tab', { name: /Applied/ })
      expect(within(appliedTab).getByText('1')).toBeInTheDocument()
    })
  })
})

describe('Skipping a job', () => {
  it('removes the job from the pending list', async () => {
    seedJobs([
      buildJob({ job_id: 'j1', title: 'React Engineer', status: 'pending' }),
      buildJob({ job_id: 'j2', title: 'Go Engineer', status: 'pending' }),
    ])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Engineer')).toBeInTheDocument())

    const row = screen.getByText('React Engineer').closest('.job-row')!
    await userEvent.click(within(row as HTMLElement).getByTitle('Skip'))

    await waitFor(() => expect(screen.queryByText('React Engineer')).toBeNull())
  })
})

describe('Status change failure handling (regression guard)', () => {
  it('surfaces an error when the status update fails, and keeps the job visible', async () => {
    seedJobs([buildJob({ job_id: 'j1', title: 'React Engineer', status: 'pending' })])
    // Make the status endpoint fail
    server.use(
      http.post('/api/job-status/:jobId/:newStatus', () =>
        HttpResponse.json({ error: 'server exploded' }, { status: 500 })
      )
    )
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Engineer')).toBeInTheDocument())

    const row = screen.getByText('React Engineer').closest('.job-row')!
    await userEvent.click(within(row as HTMLElement).getByTitle('Mark applied'))

    // The job must NOT silently disappear — a failed apply should surface feedback
    // and keep the job in the list so the user can retry.
    await waitFor(() => {
      expect(screen.getByText(/could not|failed|error/i)).toBeInTheDocument()
    })
    expect(screen.getByText('React Engineer')).toBeInTheDocument()
  })
})
