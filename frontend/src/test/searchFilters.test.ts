import { describe, it, expect } from 'vitest'
import { DEFAULT_FILTERS } from '@/utils/filters'
import {
  deriveFiltersFromSearchRows,
  normalizeFilters,
  searchLabel,
} from '@/pages/Dashboard/utils/searchFilters'
import type { SearchRowEntry } from '@/components/ui/searchRowModel'

function row(overrides: Partial<SearchRowEntry> = {}): SearchRowEntry {
  return {
    id: 'row-1',
    titles: ['Engineer'],
    locations: ['US'],
    sources: ['LinkedIn'],
    workStyles: ['Remote'],
    ...overrides,
  }
}

describe('normalizeFilters', () => {
  it('fills missing fields from defaults', () => {
    expect(normalizeFilters({ search: 'React' })).toEqual({
      ...DEFAULT_FILTERS,
      search: 'React',
    })
  })

  it('keeps an explicit remote array and recovers a missing one', () => {
    expect(normalizeFilters({ remote: ['Hybrid'] }).remote).toEqual(['Hybrid'])
    expect(normalizeFilters({ remote: undefined }).remote).toEqual([])
    expect(normalizeFilters(null)).toEqual(DEFAULT_FILTERS)
  })
})

describe('searchLabel', () => {
  it('joins the active filter dimensions for chip display', () => {
    expect(searchLabel({
      ...DEFAULT_FILTERS,
      search: 'React',
      source: 'LinkedIn',
      remote: ['Remote', 'Hybrid'],
      posted: '7',
      cv: 'created',
    })).toBe('React · LinkedIn · Remote+Hybrid · 7d · CV ready')
  })

  it('falls back to "Search" when nothing is set', () => {
    expect(searchLabel(DEFAULT_FILTERS)).toBe('Search')
  })
})

describe('deriveFiltersFromSearchRows', () => {
  it('maps titles, work styles, and a single source into dashboard filters', () => {
    const next = deriveFiltersFromSearchRows(
      [row({ titles: ['React', 'Vue'], workStyles: ['Remote', 'Hybrid'], sources: ['LinkedIn'] })],
      DEFAULT_FILTERS,
      ['LinkedIn', 'Jobicy'],
    )
    expect(next.search).toBe('React, Vue')
    expect(next.remote).toEqual(['Remote', 'Hybrid'])
    expect(next.source).toBe('LinkedIn')
  })

  it('clears source when multiple sources are configured', () => {
    const next = deriveFiltersFromSearchRows(
      [row({ sources: ['LinkedIn', 'Jobicy'] })],
      DEFAULT_FILTERS,
      ['LinkedIn', 'Jobicy'],
    )
    expect(next.source).toBe('')
  })

  it('resolves source casing against known options', () => {
    const next = deriveFiltersFromSearchRows(
      [row({ sources: ['linkedin'] })],
      DEFAULT_FILTERS,
      ['LinkedIn'],
    )
    expect(next.source).toBe('LinkedIn')
  })

  it('dedupes titles case-insensitively', () => {
    const next = deriveFiltersFromSearchRows(
      [
        row({ titles: ['React'] }),
        row({ id: 'row-2', titles: ['react', 'Go'] }),
      ],
      DEFAULT_FILTERS,
      [],
    )
    expect(next.search).toBe('React, Go')
  })
})
