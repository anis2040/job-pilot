/**
 * Job description rendering tests.
 *
 * The user pastes or receives a raw plain-text job description.  The renderer
 * converts it into readable HTML that appears inside a div.  These tests mount
 * that HTML into a real DOM node and query what the user actually sees —
 * structured headings, bullet lists, readable text — not the raw HTML strings.
 */

import { describe, it, expect } from 'vitest'
import { formatDescription } from '@/utils/descriptionRenderer'

function mountHtml(html: string): HTMLDivElement {
  const div = document.createElement('div')
  div.innerHTML = html
  document.body.appendChild(div)
  return div
}

function cleanup(el: HTMLElement) {
  document.body.removeChild(el)
}

describe('Job description — what the user sees', () => {
  it('plain text paragraphs are readable (wrapped in block elements)', () => {
    const html = formatDescription('we are looking for a motivated engineer.\n\nyou will work on backend systems.')
    const el = mountHtml(html)
    expect(el.textContent).toContain('we are looking for a motivated engineer.')
    expect(el.textContent).toContain('you will work on backend systems.')
    cleanup(el)
  })

  it('bullet list items are rendered as a list the user can read', () => {
    const text = '- 5+ years TypeScript\n- Experience with React\n- Strong communication skills'
    const html = formatDescription(text)
    const el = mountHtml(html)
    const items = el.querySelectorAll('li')
    expect(items.length).toBe(3)
    expect(items[0].textContent).toBe('5+ years TypeScript')
    expect(items[1].textContent).toBe('Experience with React')
    expect(items[2].textContent).toBe('Strong communication skills')
    cleanup(el)
  })

  it('section headings are rendered as heading elements', () => {
    const text = 'Requirements:\n- TypeScript\n\nWhat We Offer:\n- Competitive salary'
    const html = formatDescription(text)
    const el = mountHtml(html)
    const headings = el.querySelectorAll('h4')
    expect(headings.length).toBe(2)
    expect(headings[0].textContent).toBe('Requirements')
    expect(headings[1].textContent).toBe('What We Offer')
    cleanup(el)
  })

  it('"show more" and "show less" noise from the source site is stripped', () => {
    const text = 'We are hiring.\nshow more\nGreat benefits.\nshow less'
    const html = formatDescription(text)
    const el = mountHtml(html)
    expect(el.textContent).not.toMatch(/show more/i)
    expect(el.textContent).not.toMatch(/show less/i)
    expect(el.textContent).toContain('We are hiring.')
    expect(el.textContent).toContain('Great benefits.')
    cleanup(el)
  })

  it('XSS payloads in job descriptions are not executable', () => {
    const executed = { flag: false }
    ;(window as unknown as Record<string, unknown>).__xss_test = executed
    const text = '<script>window.__xss_test.flag = true</script>\nReal job description here.'
    const html = formatDescription(text)
    const el = mountHtml(html)
    // The script should not have executed
    expect(executed.flag).toBe(false)
    // But the surrounding text should still be visible
    expect(el.textContent).toContain('Real job description here.')
    cleanup(el)
  })

  it('HTML entities in source text are decoded and displayed correctly', () => {
    const text = 'Salary: $80,000 &amp; benefits'
    const html = formatDescription(text)
    const el = mountHtml(html)
    expect(el.textContent).toContain('$80,000 & benefits')
    cleanup(el)
  })

  it('mixed content renders all sections in order', () => {
    const text = [
      'About the role:',
      'We are a fast-growing startup.',
      '',
      'Requirements:',
      '- 3+ years experience',
      '- Remote-friendly',
    ].join('\n')
    const html = formatDescription(text)
    const el = mountHtml(html)
    const headings = Array.from(el.querySelectorAll('h4')).map(h => h.textContent)
    const bullets = Array.from(el.querySelectorAll('li')).map(l => l.textContent)
    expect(headings).toContain('About the role')
    expect(headings).toContain('Requirements')
    expect(bullets).toContain('3+ years experience')
    expect(bullets).toContain('Remote-friendly')
    // All text content is present
    expect(el.textContent).toContain('We are a fast-growing startup.')
    cleanup(el)
  })

  it('empty description produces no visible content', () => {
    const html = formatDescription('')
    const el = mountHtml(html)
    expect(el.textContent?.trim()).toBe('')
    cleanup(el)
  })
})
