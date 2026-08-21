/**
 * Resume Positioning section — behaviour-first.
 *
 * The user picks how far their resume reaches (Conservative / Balanced /
 * Strong Match) and optionally adds instructions, then saves. The critical
 * contract: saving positioning must NOT clobber the profile's existing
 * search/blacklist config (the backend POST overwrites the whole file, so the
 * section must read-modify-write).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ToastProvider } from '@/components/ui/Toast'
import { ProfileProvider } from '@/hooks/ProfileProvider'

vi.mock('@/api/client', () => ({
  profiles: {
    list: vi.fn().mockResolvedValue({
      profiles: [{ slug: 'anis', name: 'anis', label: 'Anis', initials: 'A', color: '#3b82f6', active: true }],
      active_slug: 'anis',
    }),
    active: vi.fn(),
    create: vi.fn(), switch: vi.fn(), delete: vi.fn(), setLabel: vi.fn(),
    getMarkdown: vi.fn().mockResolvedValue({ content: '' }),
    saveMarkdown: vi.fn().mockResolvedValue({ ok: true }),
    getConfig: vi.fn(),
    saveConfig: vi.fn().mockResolvedValue({ ok: true }),
    clearJobs: vi.fn(),
  },
  setup: { parseResume: vi.fn(), suggestConfig: vi.fn() },
  constants: {
    get: vi.fn().mockResolvedValue({ sources: [], remote_types: [], remote_css: {}, job_statuses: [], default_blacklist: [] }),
    sources: vi.fn().mockResolvedValue([]),
  },
  jobs: { list: vi.fn().mockResolvedValue([]), counts: vi.fn().mockResolvedValue({ pending: 0, applied: 0, skipped: 0 }), get: vi.fn(), setStatus: vi.fn(), similar: vi.fn().mockResolvedValue([]), description: vi.fn(), clear: vi.fn() },
  documents: {
    templates: vi.fn().mockResolvedValue({
      default_template_id: 'us',
      templates: [
        { id: 'us', label: 'US', region: 'US', supports_profile_image: false },
        { id: 'eu', label: 'EU', region: 'EU', supports_profile_image: true },
      ],
    }),
    buildResume: vi.fn(),
    resumeStatus: vi.fn(),
    buildCoverLetter: vi.fn(),
    coverLetterStatus: vi.fn(),
  },
  fetcher: { trigger: vi.fn(), status: vi.fn().mockResolvedValue({ status: 'idle', message: '' }) },
  config: { get: vi.fn().mockResolvedValue({ searches: [], title_filter: [], blacklist: [], company_blacklist: [] }), save: vi.fn() },
  aiSettings: { get: vi.fn(), save: vi.fn(), test: vi.fn() },
}))

import { profiles as profilesApi } from '@/api/client'
import ProfileSettingsPage from '@/pages/ProfileSettings/index'

const EXISTING_CONFIG = {
  searches: [{ name: 's1', source: 'LinkedIn', query: 'eng', location: 'Berlin', max_pages: 1, remote: true }],
  title_filter: ['senior'],
  blacklist: ['intern'],
  company_blacklist: ['BadCo'],
}

function renderPage(slug = 'anis') {
  return render(
    <MemoryRouter initialEntries={[`/profile-settings/${slug}`]}>
      <ToastProvider>
        <ProfileProvider>
          <Routes>
            <Route path="/profile-settings/:slug" element={<ProfileSettingsPage />} />
          </Routes>
        </ProfileProvider>
      </ToastProvider>
    </MemoryRouter>
  )
}

async function openPositioning() {
  renderPage()
  await waitFor(() => expect(screen.getByText('🎯 Resume Positioning')).toBeInTheDocument())
  fireEvent.click(screen.getByText('🎯 Resume Positioning'))
  await waitFor(() => expect(screen.getByText('Strong Match')).toBeInTheDocument())
}

describe('Resume Positioning', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(profilesApi.list).mockResolvedValue({
      profiles: [{ slug: 'anis', name: 'anis', label: 'Anis', initials: 'A', color: '#3b82f6', active: true }],
      active_slug: 'anis',
    })
    vi.mocked(profilesApi.getConfig).mockResolvedValue({ ...EXISTING_CONFIG })
    vi.mocked(profilesApi.saveConfig).mockResolvedValue({ ok: true })
  })

  it('renders the three stance options and the non-negotiables note', async () => {
    await openPositioning()
    expect(screen.getByText('Conservative')).toBeInTheDocument()
    expect(screen.getByText('Balanced')).toBeInTheDocument()
    expect(screen.getByText('Strong Match')).toBeInTheDocument()
    expect(screen.getByText(/Never changed, on any setting/)).toBeInTheDocument()
  })

  it('defaults to Balanced when no build_cv is set', async () => {
    await openPositioning()
    const balanced = screen.getByRole('radio', { name: /Balanced/ }) as HTMLInputElement
    expect(balanced.checked).toBe(true)
  })

  it('loads a saved stance from config', async () => {
    vi.mocked(profilesApi.getConfig).mockResolvedValue({
      ...EXISTING_CONFIG,
      build_cv: { experience_positioning: 'aggressive', additional_instructions: 'foo', resume_template_id: 'eu' },
    })
    await openPositioning()
    const strong = screen.getByRole('radio', { name: /Strong Match/ }) as HTMLInputElement
    await waitFor(() => expect(strong.checked).toBe(true))
    await waitFor(() => expect(screen.getByRole('button', { name: 'EU' })).toHaveAttribute('aria-pressed', 'true'))
  })

  it('saves the default resume template for the profile', async () => {
    await openPositioning()
    await waitFor(() => expect(screen.getByRole('button', { name: 'EU' })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'EU' }))

    await waitFor(() => expect(profilesApi.saveConfig).toHaveBeenCalled())
    const [slug, cfg] = vi.mocked(profilesApi.saveConfig).mock.calls[0]
    expect(slug).toBe('anis')
    expect(cfg.searches).toEqual(EXISTING_CONFIG.searches)
    expect(cfg.build_cv?.resume_template_id).toBe('eu')
  })

  it('read-modify-write: selecting a stance auto-saves and preserves existing search config', async () => {
    await openPositioning()
    // Selecting a stance persists immediately — no separate Save click needed.
    fireEvent.click(screen.getByRole('radio', { name: /Strong Match/ }))

    await waitFor(() => expect(profilesApi.saveConfig).toHaveBeenCalled())
    const [slug, cfg] = vi.mocked(profilesApi.saveConfig).mock.calls[0]
    expect(slug).toBe('anis')
    // The existing search/blacklist keys must survive.
    expect(cfg.searches).toEqual(EXISTING_CONFIG.searches)
    expect(cfg.blacklist).toEqual(EXISTING_CONFIG.blacklist)
    expect(cfg.company_blacklist).toEqual(EXISTING_CONFIG.company_blacklist)
    expect(cfg.title_filter).toEqual(EXISTING_CONFIG.title_filter)
    // And the new stance is merged in.
    expect(cfg.build_cv?.experience_positioning).toBe('aggressive')
    expect(cfg.build_cv?.resume_template_id).toBe('us')
  })

  it('saves additional instructions', async () => {
    await openPositioning()
    await userEvent.type(
      screen.getByPlaceholderText(/emphasize stakeholder management/i),
      'Focus on roadmap',
    )
    fireEvent.click(screen.getByText('Save instructions'))
    await waitFor(() => expect(profilesApi.saveConfig).toHaveBeenCalled())
    const [, cfg] = vi.mocked(profilesApi.saveConfig).mock.calls[0]
    expect(cfg.build_cv?.additional_instructions).toBe('Focus on roadmap')
  })

  it('caps additional instructions at 500 characters in the form', async () => {
    await openPositioning()
    const textarea = screen.getByPlaceholderText(/emphasize stakeholder management/i) as HTMLTextAreaElement

    expect(textarea.maxLength).toBe(500)
    expect(screen.getByText(/max 500 characters/i)).toBeInTheDocument()
  })
})
