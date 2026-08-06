/**
 * Dashboard user-flow integration tests.
 *
 * Renders the real Dashboard through the app router + providers; only the
 * network is mocked (MSW). Prefer role/label queries so refactors that keep
 * user-visible behaviour green stay green.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderApp } from './utils'
import { server } from './mocks/server'
import { seedJobs, db } from './mocks/handlers'
import { buildJob, buildJobDetail, buildMatch } from './fixtures'
import { LS_RECENT, LS_SAVED, PAGE_SIZE, SPLIT_MIN } from '@/pages/Dashboard/constants'

function setViewportWidth(width: number) {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: width })
  window.dispatchEvent(new Event('resize'))
}

function jobTitles() {
  return Array.from(document.querySelectorAll('.job-row-title')).map(el => el.textContent ?? '')
}

function seedPendingSample() {
  seedJobs([
    buildJob({ job_id: 'j1', title: 'React Developer', company: 'Alpha Tech', remote: 'Remote', source: 'LinkedIn', status: 'pending' }),
    buildJob({ job_id: 'j2', title: 'Vue Designer', company: 'Beta Studio', remote: 'Hybrid', source: 'Jobicy', status: 'pending' }),
    buildJob({ job_id: 'j3', title: 'Backend Engineer', company: 'Gamma Corp', remote: 'On-site', source: 'Himalayas', status: 'pending' }),
  ])
}

beforeEach(() => {
  setViewportWidth(SPLIT_MIN + 200)
  localStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Dashboard shell', () => {
  it('shows status tabs with counts and marks Pending selected', async () => {
    seedJobs([
      buildJob({ job_id: 'p1', title: 'Pending Role', status: 'pending' }),
      buildJob({ job_id: 'a1', title: 'Applied Role', status: 'applied' }),
      buildJob({ job_id: 's1', title: 'Skipped Role', status: 'skipped' }),
    ])
    renderApp('/')

    await waitFor(() => expect(screen.getByText('Pending Role')).toBeInTheDocument())

    const pending = screen.getByRole('tab', { name: /Pending/i })
    const applied = screen.getByRole('tab', { name: /Applied/i })
    const skipped = screen.getByRole('tab', { name: /Skipped/i })

    expect(pending).toHaveAttribute('aria-selected', 'true')
    expect(applied).toHaveAttribute('aria-selected', 'false')
    expect(skipped).toHaveAttribute('aria-selected', 'false')
    expect(within(pending).getByText('1')).toBeInTheDocument()
    expect(within(applied).getByText('1')).toBeInTheDocument()
    expect(within(skipped).getByText('1')).toBeInTheDocument()
    expect(screen.getByTestId('filter-result-count')).toHaveTextContent('1 jobs')
  })

  it('exposes search, fetch, and settings controls', async () => {
    seedPendingSample()
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    expect(screen.getByLabelText('Search jobs')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Fetch jobs' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Search settings' })).toBeInTheDocument()
  })
})

describe('Tab navigation', () => {
  it('switches lists when the user opens Applied and Skipped', async () => {
    const user = userEvent.setup()
    seedJobs([
      buildJob({ job_id: 'p1', title: 'Pending Role', status: 'pending' }),
      buildJob({ job_id: 'a1', title: 'Applied Role', status: 'applied' }),
      buildJob({ job_id: 's1', title: 'Skipped Role', status: 'skipped' }),
    ])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Pending Role')).toBeInTheDocument())

    await user.click(screen.getByRole('tab', { name: /Applied/i }))
    await waitFor(() => {
      expect(screen.getByText('Applied Role')).toBeInTheDocument()
      expect(screen.queryByText('Pending Role')).toBeNull()
    })
    expect(screen.getByRole('tab', { name: /Applied/i })).toHaveAttribute('aria-selected', 'true')

    await user.click(screen.getByRole('tab', { name: /Skipped/i }))
    await waitFor(() => {
      expect(screen.getByText('Skipped Role')).toBeInTheDocument()
      expect(screen.queryByText('Applied Role')).toBeNull()
    })
  })

  it('clears the open detail panel when changing tabs', async () => {
    const user = userEvent.setup()
    seedJobs([
      buildJob({ job_id: 'p1', title: 'Pending Role', status: 'pending' }),
      buildJob({ job_id: 'a1', title: 'Applied Role', status: 'applied' }),
    ], [
      buildJobDetail({ job_id: 'p1', title: 'Pending Role', description: 'Pending description body' }),
    ])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Pending Role')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Pending Role' }))
    await waitFor(() => expect(screen.getByTestId('detail-panel')).toBeInTheDocument())

    await user.click(screen.getByRole('tab', { name: /Applied/i }))
    await waitFor(() => {
      expect(screen.queryByTestId('detail-panel')).toBeNull()
      expect(screen.getByText('Applied Role')).toBeInTheDocument()
    })
  })

  it('shows an empty state without a fetch CTA on Applied/Skipped', async () => {
    const user = userEvent.setup()
    seedJobs([buildJob({ job_id: 'p1', title: 'Only Pending', status: 'pending' })])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Only Pending')).toBeInTheDocument())

    await user.click(screen.getByRole('tab', { name: /Applied/i }))
    await waitFor(() => expect(screen.getByText(/No applied jobs/i)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /Fetch jobs now/i })).toBeNull()
  })
})

describe('Detail panel (wide viewport)', () => {
  it('opens the side panel when a job row is clicked', async () => {
    const user = userEvent.setup()
    seedJobs(
      [buildJob({ job_id: 'j1', title: 'React Developer', company: 'Alpha Tech', status: 'pending' })],
      [buildJobDetail({
        job_id: 'j1',
        title: 'React Developer',
        company: 'Alpha Tech',
        description: 'Build delightful React apps with TypeScript.',
        match: buildMatch({ matched: ['React', 'TypeScript'], missing: ['Go'] }),
      })],
    )
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'React Developer' }))

    const panel = await screen.findByTestId('detail-panel')
    expect(panel).toHaveAttribute('aria-label', 'Job details')
    await waitFor(() => expect(within(panel).getByText(/Build delightful React apps/i)).toBeInTheDocument())
    expect(within(panel).getByText('React')).toBeInTheDocument()
    expect(within(panel).getByText('Go')).toBeInTheDocument()
    expect(screen.getByTestId('job-row-j1')).toHaveAttribute('aria-pressed', 'true')
  })

  it('closes the panel when the same row is clicked again', async () => {
    const user = userEvent.setup()
    seedJobs(
      [buildJob({ job_id: 'j1', title: 'React Developer', status: 'pending' })],
      [buildJobDetail({ job_id: 'j1', title: 'React Developer', description: 'Panel body' })],
    )
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'React Developer' }))
    await screen.findByTestId('detail-panel')

    await user.click(screen.getByRole('button', { name: 'React Developer' }))
    await waitFor(() => expect(screen.queryByTestId('detail-panel')).toBeNull())
  })

  it('closes the panel via the close control', async () => {
    const user = userEvent.setup()
    seedJobs(
      [buildJob({ job_id: 'j1', title: 'React Developer', status: 'pending' })],
      [buildJobDetail({ job_id: 'j1', title: 'React Developer', description: 'Panel body' })],
    )
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'React Developer' }))
    await screen.findByTestId('detail-panel')

    await user.click(screen.getByRole('button', { name: 'Close panel' }))
    await waitFor(() => expect(screen.queryByTestId('detail-panel')).toBeNull())
  })

  it('navigates to the full detail page from the panel maximize control', async () => {
    const user = userEvent.setup()
    seedJobs(
      [buildJob({ job_id: 'j1', title: 'React Developer', status: 'pending' })],
      [buildJobDetail({ job_id: 'j1', title: 'React Developer', description: 'Panel body' })],
    )
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'React Developer' }))
    await screen.findByTestId('detail-panel')

    await user.click(screen.getByRole('button', { name: 'Open full detail' }))
    await waitFor(() => {
      expect(screen.queryByTestId('detail-panel')).toBeNull()
      expect(screen.getAllByText('React Developer').length).toBeGreaterThan(0)
    })
  })

  it('closes the panel after applying from the row', async () => {
    const user = userEvent.setup()
    seedJobs(
      [
        buildJob({ job_id: 'j1', title: 'React Developer', status: 'pending' }),
        buildJob({ job_id: 'j2', title: 'Go Engineer', status: 'pending' }),
      ],
      [buildJobDetail({ job_id: 'j1', title: 'React Developer', description: 'Panel body' })],
    )
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'React Developer' }))
    await screen.findByTestId('detail-panel')

    const row = screen.getByTestId('job-row-j1')
    await user.click(within(row).getByTitle('Mark applied'))

    await waitFor(() => {
      expect(screen.queryByText('React Developer')).toBeNull()
      expect(screen.queryByTestId('detail-panel')).toBeNull()
      expect(screen.getByText('Go Engineer')).toBeInTheDocument()
    })
  })
})

describe('Narrow viewport navigation', () => {
  it('navigates to /job/:id instead of opening a side panel', async () => {
    const user = userEvent.setup()
    setViewportWidth(SPLIT_MIN - 100)
    seedJobs(
      [buildJob({ job_id: 'j1', title: 'React Developer', status: 'pending' })],
      [buildJobDetail({ job_id: 'j1', title: 'React Developer', description: 'Full page description' })],
    )
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'React Developer' }))

    await waitFor(() => {
      expect(screen.queryByTestId('detail-panel')).toBeNull()
      expect(screen.getByText(/Full page description/i)).toBeInTheDocument()
    })
  })
})

describe('Restore flow', () => {
  it('restores an applied job back to Pending', async () => {
    const user = userEvent.setup()
    seedJobs([buildJob({ job_id: 'a1', title: 'Applied Role', status: 'applied' })])
    renderApp('/')

    await user.click(screen.getByRole('tab', { name: /Applied/i }))
    await waitFor(() => expect(screen.getByText('Applied Role')).toBeInTheDocument())

    const row = screen.getByTestId('job-row-a1')
    await user.click(within(row).getByTitle('Restore to pending'))

    await waitFor(() => expect(screen.queryByText('Applied Role')).toBeNull())

    await user.click(screen.getByRole('tab', { name: /Pending/i }))
    await waitFor(() => expect(screen.getByText('Applied Role')).toBeInTheDocument())
  })
})

describe('Saved and recent searches', () => {
  it('saves the current filters and reapplies them from a chip', async () => {
    const user = userEvent.setup()
    seedPendingSample()
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /^Remote$/i }))
    await waitFor(() => expect(screen.getByTestId('filter-result-count')).toHaveTextContent('1 jobs'))

    const saveBtn = screen.getByRole('button', { name: 'Save this search' })
    expect(saveBtn).toBeEnabled()
    await user.click(saveBtn)

    await waitFor(() => expect(screen.getByText(/Search saved/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Search saved' })).toHaveAttribute('aria-pressed', 'true')
    expect(JSON.parse(localStorage.getItem(LS_SAVED) || '[]')).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    await waitFor(() => expect(screen.getByTestId('filter-result-count')).toHaveTextContent('3 jobs'))

    await user.click(screen.getByRole('button', { name: /Apply saved search:/i }))
    await waitFor(() => {
      expect(screen.getByText('React Developer')).toBeInTheDocument()
      expect(screen.queryByText('Vue Designer')).toBeNull()
      expect(screen.getByRole('button', { name: /^Remote$/i })).toHaveAttribute('aria-pressed', 'true')
    })
  })

  it('removes a saved search chip without applying it', async () => {
    const user = userEvent.setup()
    localStorage.setItem(LS_SAVED, JSON.stringify([{
      search: '', source: 'LinkedIn', remote: ['Remote'], posted: '', cv: '', sort: 'match',
    }]))
    seedPendingSample()
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    expect(screen.getByTestId('search-chips')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Remove saved search:/i }))

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Apply saved search:/i })).toBeNull()
      expect(JSON.parse(localStorage.getItem(LS_SAVED) || '[]')).toHaveLength(0)
    })
    // Removing should not have applied the filter
    expect(screen.getByTestId('filter-result-count')).toHaveTextContent('3 jobs')
  })

  it('captures a recent search on source change and reapplies it', async () => {
    const user = userEvent.setup()
    seedPendingSample()
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.selectOptions(screen.getByLabelText('Filter by source'), 'Jobicy')
    await waitFor(() => expect(screen.getByText('Vue Designer')).toBeInTheDocument())

    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem(LS_RECENT) || '[]').length).toBeGreaterThan(0)
    })

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    await waitFor(() => expect(screen.getByTestId('filter-result-count')).toHaveTextContent('3 jobs'))

    await user.click(screen.getByRole('button', { name: /Apply recent search:/i }))
    await waitFor(() => {
      expect(screen.getByLabelText('Filter by source')).toHaveValue('Jobicy')
      expect(jobTitles()).toEqual(['Vue Designer'])
    })
  })

  it('keeps the Save control disabled until a filter is set', async () => {
    seedPendingSample()
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Save this search' })).toBeDisabled()
  })
})

describe('Pagination', () => {
  it('pages through results and resets to page 1 when filters change', async () => {
    const user = userEvent.setup()
    seedJobs(Array.from({ length: PAGE_SIZE + 3 }, (_, i) => buildJob({
      job_id: `paged-${i + 1}`,
      title: `Paged Job ${i + 1}`,
      status: 'pending',
      remote: i === PAGE_SIZE + 1 ? 'Remote' : 'Hybrid',
    })))
    renderApp('/')

    await waitFor(() => expect(screen.getByText('Paged Job 1')).toBeInTheDocument())
    expect(screen.queryByText(`Paged Job ${PAGE_SIZE + 1}`)).toBeNull()
    expect(screen.getByRole('navigation', { name: 'Pagination' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(screen.getByText(`Paged Job ${PAGE_SIZE + 1}`)).toBeInTheDocument())
    expect(screen.queryByText('Paged Job 1')).toBeNull()
    expect(screen.getByRole('button', { name: 'Page 2' })).toHaveAttribute('aria-current', 'page')

    await user.click(screen.getByRole('button', { name: /^Remote$/i }))
    await waitFor(() => {
      expect(screen.getByText(`Paged Job ${PAGE_SIZE + 2}`)).toBeInTheDocument()
      expect(screen.queryByRole('navigation', { name: 'Pagination' })).toBeNull()
    })
  })
})

describe('Sort options', () => {
  it('sorts by title A–Z', async () => {
    const user = userEvent.setup()
    seedJobs([
      buildJob({ job_id: 'j1', title: 'Zebra Role', status: 'pending' }),
      buildJob({ job_id: 'j2', title: 'Alpha Role', status: 'pending' }),
      buildJob({ job_id: 'j3', title: 'Middle Role', status: 'pending' }),
    ])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Zebra Role')).toBeInTheDocument())

    await user.selectOptions(screen.getByLabelText('Sort jobs'), 'title')
    await waitFor(() => {
      expect(jobTitles()).toEqual(['Alpha Role', 'Middle Role', 'Zebra Role'])
    })
  })

  it('sorts by company A–Z', async () => {
    const user = userEvent.setup()
    seedJobs([
      buildJob({ job_id: 'j1', title: 'Role One', company: 'Zebra Co', status: 'pending' }),
      buildJob({ job_id: 'j2', title: 'Role Two', company: 'Alpha Co', status: 'pending' }),
    ])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Role One')).toBeInTheDocument())

    await user.selectOptions(screen.getByLabelText('Sort jobs'), 'company')
    await waitFor(() => {
      expect(jobTitles()).toEqual(['Role Two', 'Role One'])
    })
  })
})

describe('Row interactions', () => {
  it('opens a job with keyboard Enter without needing a mouse click', async () => {
    const user = userEvent.setup()
    seedJobs(
      [buildJob({ job_id: 'j1', title: 'Keyboard Role', status: 'pending' })],
      [buildJobDetail({ job_id: 'j1', title: 'Keyboard Role', description: 'Opened via keyboard' })],
    )
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Keyboard Role')).toBeInTheDocument())

    const row = screen.getByRole('button', { name: 'Keyboard Role' })
    row.focus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(screen.getByTestId('detail-panel')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText(/Opened via keyboard/i)).toBeInTheDocument())
  })

  it('does not open the panel when clicking a status action', async () => {
    const user = userEvent.setup()
    seedJobs([
      buildJob({ job_id: 'j1', title: 'React Developer', status: 'pending' }),
      buildJob({ job_id: 'j2', title: 'Go Engineer', status: 'pending' }),
    ])
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    const row = screen.getByTestId('job-row-j1')
    await user.click(within(row).getByTitle('Skip'))

    await waitFor(() => expect(screen.queryByText('React Developer')).toBeNull())
    expect(screen.queryByTestId('detail-panel')).toBeNull()
  })
})

describe('Fetch from the toolbar', () => {
  it('starts a fetch from the header Fetch jobs button', async () => {
    const user = userEvent.setup()
    let fetchTriggered = false
    let polls = 0
    server.use(
      http.post('/api/fetch', () => {
        fetchTriggered = true
        db.fetchStatus = { status: 'running', message: 'Starting fetch…' }
        return HttpResponse.json({ status: 'running' })
      }),
      http.get('/api/fetch-status', () => {
        polls++
        if (polls >= 2) {
          db.jobs = [buildJob({ job_id: 'new-1', title: 'Fresh Role', status: 'pending' })]
          return HttpResponse.json({ status: 'done', message: 'Done' })
        }
        return HttpResponse.json({ status: 'running', message: 'Fetching…' })
      }),
    )
    seedJobs([])
    renderApp('/')
    await waitFor(() => expect(screen.getByText(/No pending jobs/i)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Fetch jobs' }))
    await waitFor(() => expect(fetchTriggered).toBe(true))
    await waitFor(() => expect(screen.getByText('Fresh Role')).toBeInTheDocument(), { timeout: 4000 })
  })
})

describe('Empty filter state clear action', () => {
  it('offers Clear filters from the no-match empty state', async () => {
    const user = userEvent.setup()
    seedPendingSample()
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    await user.type(screen.getByLabelText('Search jobs'), 'zzzznope')
    await waitFor(() => expect(screen.getByText(/No jobs match your filters/i)).toBeInTheDocument())

    const clearButtons = screen.getAllByRole('button', { name: /Clear filters/i })
    await user.click(clearButtons[clearButtons.length - 1])

    await waitFor(() => {
      expect(screen.getByText('React Developer')).toBeInTheDocument()
      expect(screen.getByLabelText('Search jobs')).toHaveValue('')
    })
  })
})
