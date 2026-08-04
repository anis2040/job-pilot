import { describe, it, expect } from 'vitest'
import { escapeHtml, safeUrl, fmtK, fmtDate } from '@/utils/format'

describe('escapeHtml', () => {
  it('returns empty string for null', () => expect(escapeHtml(null)).toBe(''))
  it('returns empty string for undefined', () => expect(escapeHtml(undefined)).toBe(''))
  it('escapes &', () => expect(escapeHtml('a & b')).toBe('a &amp; b'))
  it('escapes <', () => expect(escapeHtml('<div>')).toBe('&lt;div&gt;'))
  it('escapes >', () => expect(escapeHtml('a > b')).toBe('a &gt; b'))
  it('escapes "', () => expect(escapeHtml('"quoted"')).toBe('&quot;quoted&quot;'))
  it("escapes '", () => expect(escapeHtml("it's")).toBe('it&#39;s'))
  it('escapes multiple special chars', () =>
    expect(escapeHtml('<a href="url">text & more</a>'))
      .toBe('&lt;a href=&quot;url&quot;&gt;text &amp; more&lt;/a&gt;'))
  it('returns plain string unchanged', () => expect(escapeHtml('hello world')).toBe('hello world'))
  it('coerces numbers', () => expect(escapeHtml(42 as unknown as string)).toBe('42'))
})

describe('safeUrl', () => {
  it('allows https URLs', () => expect(safeUrl('https://example.com')).toBe('https://example.com'))
  it('allows http URLs', () => expect(safeUrl('http://example.com')).toBe('http://example.com'))
  it('allows same-origin paths', () => expect(safeUrl('/pdf/resume.pdf')).toBe('/pdf/resume.pdf'))
  it('allows root path', () => expect(safeUrl('/')).toBe('/'))
  it('blocks javascript: protocol', () => expect(safeUrl('javascript:alert(1)')).toBe('#'))
  it('blocks data: protocol', () => expect(safeUrl('data:text/html,<h1>hi</h1>')).toBe('#'))
  it('blocks relative paths without /', () => expect(safeUrl('evil.com')).toBe('#'))
  it('returns # for empty string', () => expect(safeUrl('')).toBe('#'))
  it('returns # for null', () => expect(safeUrl(null)).toBe('#'))
  it('returns # for undefined', () => expect(safeUrl(undefined)).toBe('#'))
})

describe('fmtK', () => {
  it('returns "0" for 0', () => expect(fmtK(0)).toBe('0'))
  it('returns string for sub-1000', () => expect(fmtK(999)).toBe('999'))
  it('formats 1000 as 1.0k', () => expect(fmtK(1000)).toBe('1.0k'))
  it('formats 1500 as 1.5k', () => expect(fmtK(1500)).toBe('1.5k'))
  it('formats 9999 as 10.0k', () => expect(fmtK(9999)).toBe('10.0k'))
  it('formats 10000 as 10k (no decimal)', () => expect(fmtK(10000)).toBe('10k'))
  it('formats 12345 as 12k', () => expect(fmtK(12345)).toBe('12k'))
  it('treats null as 0', () => expect(fmtK(null as unknown as number)).toBe('0'))
})

describe('fmtDate', () => {
  it('returns empty string for empty input', () => expect(fmtDate('')).toBe(''))
  it('returns empty string for null', () => expect(fmtDate(null as unknown as string)).toBe(''))
  it('formats a valid ISO date', () => {
    const result = fmtDate('2026-08-04T12:00:00Z')
    // Just check it's non-empty and contains the year
    expect(result).toBeTruthy()
    expect(result).toContain('2026')
  })
  it('returns a non-empty string for invalid date (browser-specific)', () => {
    // jsdom's Date.toLocaleDateString returns "Invalid Date" for invalid inputs
    const result = fmtDate('not-a-date')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })
})
