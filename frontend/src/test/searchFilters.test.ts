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

  it('keeps an explicit sources array and recovers a missing one', () => {
    expect(normalizeFilters({ sources: ['LinkedIn', 'Jobicy'] }).sources).toEqual(['LinkedIn', 'Jobicy'])
    expect(normalizeFilters({ sources: undefined }).sources).toEqual([])
  })

  it('keeps an explicit locations array and recovers a missing one', () => {
    expect(normalizeFilters({ locations: ['Germany', 'United States'] }).locations).toEqual(['Germany', 'United States'])
    expect(normalizeFilters({ locations: undefined }).locations).toEqual([])
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
      locations: ['Germany'],
    })).toBe('React · LinkedIn · Germany · Remote+Hybrid · 7d · CV ready')
  })

  it('falls back to "Search" when nothing is set', () => {
    expect(searchLabel(DEFAULT_FILTERS)).toBe('Search')
  })
})

describe('deriveFiltersFromSearchRows', () => {
  it('maps work styles and a single source into dashboard filters without changing search text', () => {
    const next = deriveFiltersFromSearchRows(
      [row({ titles: ['React', 'Vue'], workStyles: ['Remote', 'Hybrid'], sources: ['LinkedIn'] })],
      { ...DEFAULT_FILTERS, search: 'manual search' },
      ['LinkedIn', 'Jobicy'],
    )
    expect(next.search).toBe('manual search')
    expect(next.remote).toEqual(['Remote', 'Hybrid'])
    expect(next.source).toBe('LinkedIn')
    expect(next.locations).toEqual(['US'])
  })

  it('does not create a dashboard work-style filter when all styles are selected', () => {
    const next = deriveFiltersFromSearchRows(
      [row({ workStyles: ['Remote', 'Hybrid', 'On-site'] })],
      DEFAULT_FILTERS,
      ['LinkedIn'],
    )
    expect(next.remote).toEqual([])
  })

  it('dedupes locations case-insensitively', () => {
    const next = deriveFiltersFromSearchRows(
      [
        row({ locations: ['Germany'] }),
        row({ id: 'row-2', locations: ['germany', 'United States'] }),
      ],
      DEFAULT_FILTERS,
      [],
    )
    expect(next.locations).toEqual(['Germany', 'United States'])
  })

  it('maps multiple configured sources into a multi-source dashboard filter', () => {
    const next = deriveFiltersFromSearchRows(
      [row({ sources: ['LinkedIn', 'Jobicy'] })],
      DEFAULT_FILTERS,
      ['LinkedIn', 'Jobicy'],
    )
    expect(next.source).toBe('')
    expect(next.sources).toEqual(['LinkedIn', 'Jobicy'])
  })

  it('resolves source casing against known options', () => {
    const next = deriveFiltersFromSearchRows(
      [row({ sources: ['linkedin'] })],
      DEFAULT_FILTERS,
      ['LinkedIn'],
    )
    expect(next.source).toBe('LinkedIn')
    expect(next.sources).toEqual([])
  })

  it('does not copy configured titles into an empty search input', () => {
    const next = deriveFiltersFromSearchRows(
      [
        row({ titles: ['React'] }),
        row({ id: 'row-2', titles: ['react', 'Go'] }),
      ],
      DEFAULT_FILTERS,
      [],
    )
    expect(next.search).toBe('')
  })
})
