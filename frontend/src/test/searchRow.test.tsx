/**
 * SearchRow component tests — behaviour-first.
 *
 * Users configure search sources by filling in a query, location, toggling
 * remote, and selecting which job boards to search.  These tests verify that
 * user interactions produce the right state changes passed to the parent.
 *
 * The internal groupSearchEntries / expandSearchRows helpers are implementation
 * details tested implicitly through the Dashboard Settings modal.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SearchRow } from '@/components/ui/SearchRow'
import { expandSearchRows, groupSearchEntries, type SearchRowEntry } from '@/components/ui/searchRowModel'

const SOURCES = ['LinkedIn', 'Jobicy', 'Himalayas']

const defaultEntry: SearchRowEntry = {
  titles: ['Product Manager'],
  locations: ['United States'],
  workStyles: ['Remote', 'Hybrid'],
  sources: ['LinkedIn', 'Jobicy'],
}

describe('SearchRow — user configuring a search', () => {
  it('shows the current query and location values', () => {
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={vi.fn()} onRemove={vi.fn()} />)
    expect(screen.getByRole('button', { name: /remove product manager/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /remove united states/i })).toBeInTheDocument()
  })

  it('user adds another job title', async () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    await userEvent.type(screen.getByPlaceholderText('Add a job title'), 'Engineering Manager{enter}')
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ titles: ['Product Manager', 'Engineering Manager'] }))
  })

  it('selecting a country adds it immediately', async () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    await userEvent.selectOptions(screen.getByLabelText('Add country or location'), 'Germany')
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ locations: ['United States', 'Germany'] }))
  })

  it('user can select multiple work styles including hybrid', async () => {
    const onChange = vi.fn()
    render(<SearchRow entry={{ ...defaultEntry, workStyles: ['Remote'] }} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /hybrid/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ workStyles: ['Remote', 'Hybrid'] }))
  })

  it('checked sources are shown as checked', () => {
    render(<SearchRow entry={{ ...defaultEntry, sources: ['LinkedIn'] }} sources={SOURCES} onChange={vi.fn()} onRemove={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'LinkedIn' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Jobicy' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('clicking an unchecked source adds it', async () => {
    const onChange = vi.fn()
    render(<SearchRow entry={{ ...defaultEntry, sources: ['LinkedIn'] }} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Jobicy' }))
    const updated = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(updated.sources).toContain('Jobicy')
    expect(updated.sources).toContain('LinkedIn')
  })

  it('clicking a checked source removes it', async () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Jobicy' }))
    const updated = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(updated.sources).not.toContain('Jobicy')
    expect(updated.sources).toContain('LinkedIn')
  })

  it('all/none button when all checked — unchecks everything', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={{ ...defaultEntry, sources: ['LinkedIn', 'Jobicy', 'Himalayas'] }} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByText('Clear all'))
    const updated = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(updated.sources).toHaveLength(0)
  })

  it('all/none button when none checked — checks everything', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={{ ...defaultEntry, sources: [] }} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByText('Select all'))
    const updated = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(updated.sources).toEqual(expect.arrayContaining(SOURCES))
  })

  it('remove button calls onRemove', async () => {
    const onRemove = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={vi.fn()} onRemove={onRemove} />)
    await userEvent.click(screen.getByTitle('Remove'))
    expect(onRemove).toHaveBeenCalledTimes(1)
  })
})

describe('Search row model', () => {
  it('saves all work styles as an unrestricted work-style filter', () => {
    const [entry] = expandSearchRows([{ ...defaultEntry, workStyles: ['Remote', 'Hybrid', 'On-site'] }])
    expect(entry.remote).toBe(false)
    expect(entry.work_styles).toEqual([])
  })

  it('loads an unrestricted work-style filter as all selected in the UI', () => {
    const [row] = groupSearchEntries([{ ...expandSearchRows([defaultEntry])[0], remote: false, work_styles: [] }])
    expect(row.workStyles).toEqual(['Remote', 'Hybrid', 'On-site'])
  })
})
