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
  location: 'United States',
  remote: true,
  sources: ['LinkedIn', 'Jobicy'],
}

describe('SearchRow — user configuring a search', () => {
  it('shows the current query and location values', () => {
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={vi.fn()} onRemove={vi.fn()} />)
    expect(screen.getByDisplayValue('Product Manager')).toBeInTheDocument()
    expect(screen.getByDisplayValue('United States')).toBeInTheDocument()
  })

  it('user changes the job title query', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. Product Manager'), { target: { value: 'Engineering Manager' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ query: 'Engineering Manager' }))
  })

  it('user changes the location', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.change(screen.getByDisplayValue('United States'), { target: { value: 'United Kingdom' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ location: 'United Kingdom' }))
  })

  it('user unchecks the Remote toggle — remote becomes false', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /remote/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ remote: false }))
  })

  it('checked sources are shown as checked', () => {
    render(<SearchRow entry={{ ...defaultEntry, sources: ['LinkedIn'] }} sources={SOURCES} onChange={vi.fn()} onRemove={vi.fn()} />)
    const linkedinCb = screen.getByRole('checkbox', { name: /linkedin/i, hidden: true })
    const jobicyCb = screen.getByRole('checkbox', { name: /jobicy/i, hidden: true })
    expect(linkedinCb).toBeChecked()
    expect(jobicyCb).not.toBeChecked()
  })

  it('clicking an unchecked source adds it', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={{ ...defaultEntry, sources: ['LinkedIn'] }} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByText('Jobicy').closest('label')!)
    const updated = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(updated.sources).toContain('Jobicy')
    expect(updated.sources).toContain('LinkedIn')
  })

  it('clicking a checked source removes it', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={defaultEntry} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByText('Jobicy').closest('label')!)
    const updated = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(updated.sources).not.toContain('Jobicy')
    expect(updated.sources).toContain('LinkedIn')
  })

  it('all/none button when all checked — unchecks everything', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={{ ...defaultEntry, sources: ['LinkedIn', 'Jobicy', 'Himalayas'] }} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByText('all/none'))
    const updated = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(updated.sources).toHaveLength(0)
  })

  it('all/none button when none checked — checks everything', () => {
    const onChange = vi.fn()
    render(<SearchRow entry={{ ...defaultEntry, sources: [] }} sources={SOURCES} onChange={onChange} onRemove={vi.fn()} />)
    fireEvent.click(screen.getByText('all/none'))
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
