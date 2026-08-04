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

const SOURCES = ['LinkedIn', 'Jobicy', 'Himalayas']

const defaultEntry = {
  query: 'Product Manager',
  locations: ['United States'],
  remote: true,
  sources: ['LinkedIn', 'Jobicy'],
}

describe('SearchRow — user configuring a search', () => {
  it('shows the current query and location values', () => {
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={vi.fn()} onRemove={vi.fn()} />)
    expect(screen.getByDisplayValue('Product Manager')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /remove united states/i })).toBeInTheDocument()
  })

  it('user changes the job title query', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. Product Manager'), { target: { value: 'Engineering Manager' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ query: 'Engineering Manager' }))
  })

  it('user adds another location', async () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    await userEvent.type(screen.getByPlaceholderText('Add a country or location'), 'United Kingdom')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ locations: ['United States', 'United Kingdom'] }))
  })

  it('user switches to location-based mode', async () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /location-based/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ remote: false }))
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
