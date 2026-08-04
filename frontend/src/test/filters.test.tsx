/**
 * Search / filter / sort integration tests.
 *
 * Rendered against the REAL Dashboard with the REAL api/client.ts — only the
 * network is mocked (MSW).  This exercises URL construction (?status=…),
 * response parsing, and the full filter→render pipeline the way a user drives it.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { renderApp } from './utils'
import { seedJobs, db } from './mocks/handlers'
import { buildJob, buildMatch } from './fixtures'

function jobRowTitles() {
  return Array.from(document.querySelectorAll('.job-row-title')).map(el => el.textContent ?? '')
}

const SAMPLE = () => [
  buildJob({ job_id: 'j1', title: 'React Developer',  company: 'Alpha Tech',  remote: 'Remote',  source: 'LinkedIn',  status: 'pending', posted_at: new Date(Date.now() - 12 * 3600000).toISOString() }),
  buildJob({ job_id: 'j2', title: 'Vue Designer',     company: 'Beta Studio', remote: 'Hybrid',  source: 'Jobicy',    status: 'pending', posted_at: new Date(Date.now() - 5 * 86400000).toISOString() }),
  buildJob({ job_id: 'j3', title: 'Backend Engineer', company: 'Gamma Corp',  remote: 'On-site', source: 'Himalayas', status: 'pending', posted_at: new Date(Date.now() - 15 * 86400000).toISOString() }),
  buildJob({ job_id: 'j4', title: 'DevOps Engineer',  company: 'Alpha Tech',  remote: 'Remote',  source: 'LinkedIn',  status: 'pending', posted_at: new Date(Date.now() - 2 * 86400000).toISOString(), match: buildMatch({ score: 72, semantic_score: 72 }) }),
  buildJob({ job_id: 'j5', title: 'Product Manager',  company: 'Delta Inc',   remote: 'Hybrid',  source: 'LinkedIn',  status: 'pending', posted_at: new Date(Date.now() - 8 * 86400000).toISOString(), match: buildMatch({ score: 88, semantic_score: 88 }) }),
]

beforeEach(() => seedJobs(SAMPLE()))

describe('Loading and rendering jobs', () => {
  it('loads pending jobs and renders every one', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    expect(jobRowTitles()).toEqual(expect.arrayContaining([
      'React Developer', 'Vue Designer', 'Backend Engineer', 'DevOps Engineer', 'Product Manager',
    ]))
  })

  it('requests the correct status when a different tab is opened', async () => {
    // Seed an applied job; the applied tab must request ?status=applied
    db.jobs.push(buildJob({ job_id: 'a1', title: 'Applied Role', status: 'applied' }))
    renderApp('/')
    await waitFor(() => expect(screen.getByText('React Developer')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Applied/ }))

    await waitFor(() => {
      expect(screen.getByText('Applied Role')).toBeInTheDocument()
      expect(screen.queryByText('React Developer')).toBeNull() // pending jobs gone
    })
  })
})

describe('Work-type filter chips', () => {
  it('Remote chip narrows the list to Remote jobs', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))

    fireEvent.click(screen.getByText('🌐 Remote'))

    await waitFor(() => {
      const t = jobRowTitles()
      expect(t).toContain('React Developer')
      expect(t).toContain('DevOps Engineer')
      expect(t).not.toContain('Vue Designer')
      expect(t).not.toContain('Backend Engineer')
    })
  })

  it('Remote + Hybrid together (OR) exclude On-site', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.click(screen.getByText('🌐 Remote'))
    fireEvent.click(screen.getByText('🏠 Hybrid'))
    await waitFor(() => expect(jobRowTitles()).not.toContain('Backend Engineer'))
    expect(jobRowTitles()).toContain('Vue Designer')
  })

  it('toggling a chip off restores the full list', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.click(screen.getByText('🌐 Remote'))
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(2))
    fireEvent.click(screen.getByText('🌐 Remote'))
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
  })
})

describe('Source and posted-date filters', () => {
  it('source dropdown filters to a single source', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.change(screen.getByLabelText('Filter by source'), { target: { value: 'Jobicy' } })
    await waitFor(() => {
      expect(jobRowTitles()).toEqual(['Vue Designer'])
    })
  })

  it('the source dropdown option value matches the jobs\' source label (id/label regression)', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    const select = screen.getByLabelText('Filter by source') as HTMLSelectElement
    const optionValues = Array.from(select.options).map(o => o.value)
    // Options must carry the capitalised labels present on jobs (e.g. "LinkedIn"),
    // not the lowercase source ids ("linkedin") which never match j.source.
    expect(optionValues).toContain('LinkedIn')
    expect(optionValues).toContain('Jobicy')
    // Selecting one actually narrows the list (proves value === job.source)
    fireEvent.change(select, { target: { value: 'LinkedIn' } })
    await waitFor(() => {
      const t = jobRowTitles()
      expect(t).toContain('React Developer')
      expect(t).toContain('DevOps Engineer')
      expect(t).toContain('Product Manager')
      expect(t).not.toContain('Vue Designer')
    })
  })

  it('posted "past 24 hours" keeps only fresh jobs', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.change(screen.getByLabelText('Filter by posting date'), { target: { value: '1' } })
    await waitFor(() => {
      const t = jobRowTitles()
      expect(t).toContain('React Developer') // 12h old
      expect(t).not.toContain('Vue Designer') // 5d old
    })
  })
})

describe('Search bar', () => {
  it('filters by title, company, or source (case-insensitive)', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.change(screen.getByPlaceholderText(/Search by title/i), { target: { value: 'ALPHA' } })
    await waitFor(() => {
      const t = jobRowTitles()
      expect(t).toContain('React Developer') // company Alpha Tech
      expect(t).toContain('DevOps Engineer')
      expect(t).not.toContain('Vue Designer')
    })
  })

  it('clear button empties the search and restores the list', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.change(screen.getByPlaceholderText(/Search by title/i), { target: { value: 'react' } })
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(1))
    fireEvent.click(screen.getByLabelText('Clear search'))
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
  })

  it('shows the no-match empty state when nothing matches', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.change(screen.getByPlaceholderText(/Search by title/i), { target: { value: 'zzzznope' } })
    await waitFor(() => expect(screen.getByText(/No jobs match your filters/i)).toBeInTheDocument())
  })
})

describe('Sorting', () => {
  it('Best match ranks higher-scoring jobs first and no-match jobs last', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.change(screen.getByLabelText('Sort jobs'), { target: { value: 'match' } })
    await waitFor(() => {
      const t = jobRowTitles()
      expect(t.indexOf('Product Manager')).toBeLessThan(t.indexOf('DevOps Engineer')) // 88 > 72
      expect(t.indexOf('React Developer')).toBeGreaterThan(t.indexOf('DevOps Engineer')) // null last
    })
  })

  it('Posted date shows newest first', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.change(screen.getByLabelText('Sort jobs'), { target: { value: 'posted' } })
    await waitFor(() => {
      const t = jobRowTitles()
      expect(t[0]).toBe('React Developer')   // 12h
      expect(t[t.length - 1]).toBe('Backend Engineer') // 15d
    })
  })
})

describe('Combined filters', () => {
  it('Remote chip + LinkedIn source narrows to the intersection', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.click(screen.getByText('🌐 Remote'))
    fireEvent.change(screen.getByLabelText('Filter by source'), { target: { value: 'LinkedIn' } })
    await waitFor(() => {
      const t = jobRowTitles()
      expect(t).toContain('React Developer')
      expect(t).toContain('DevOps Engineer')
      expect(t).not.toContain('Vue Designer')
    })
  })

  it('Clear filters resets everything', async () => {
    renderApp('/')
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
    fireEvent.click(screen.getByText('🌐 Remote'))
    fireEvent.change(screen.getByLabelText('Filter by source'), { target: { value: 'LinkedIn' } })
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(2))
    fireEvent.click(screen.getByText('Clear filters'))
    await waitFor(() => expect(document.querySelectorAll('.job-row')).toHaveLength(5))
  })
})

describe('Empty and error states', () => {
  it('shows the fetch CTA when there are genuinely no jobs', async () => {
    db.jobs = []
    renderApp('/')
    await waitFor(() => {
      expect(screen.getByText(/No pending jobs/i)).toBeInTheDocument()
      expect(screen.getByText(/Fetch jobs now/i)).toBeInTheDocument()
    })
  })
})
