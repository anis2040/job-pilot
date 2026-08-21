/**
 * Profile form tests — behaviour-first.
 *
 * Users fill out a structured form with their name, experience, education etc.
 * They save it.  If they reload, their data is still there.
 *
 * The fact that we serialise to markdown internally is irrelevant — tests
 * should verify the user-visible contract: data entered persists and
 * reloads correctly.
 *
 * We test this via ProfileSettings which is the real component users interact
 * with, with the API mocked.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ToastProvider } from '@/components/ui/Toast'
import { ProfileProvider } from '@/hooks/ProfileProvider'

// ── Mock API ──────────────────────────────────────────────────────────────────

vi.mock('@/api/client', () => ({
  profiles: {
    list: vi.fn().mockResolvedValue({
      profiles: [{ slug: 'anis', name: 'anis', label: 'Anis', initials: 'A', color: '#3b82f6', active: true }],
      active_slug: 'anis',
    }),
    active: vi.fn(),
    create: vi.fn(),
    switch: vi.fn(),
    delete: vi.fn(),
    setLabel: vi.fn(),
    getMarkdown: vi.fn(),
    saveMarkdown: vi.fn(),
    uploadImage: vi.fn().mockResolvedValue({ ok: true, image_url: '/api/profiles/anis/image?v=1' }),
    deleteImage: vi.fn().mockResolvedValue({ ok: true }),
    getConfig: vi.fn().mockResolvedValue({ searches: [], title_filter: [], blacklist: [], company_blacklist: [] }),
    saveConfig: vi.fn().mockResolvedValue({ ok: true }),
    clearJobs: vi.fn(),
  },
  setup: {
    parseResume: vi.fn(),
    suggestConfig: vi.fn(),
  },
  constants: {
    get: vi.fn().mockResolvedValue({ sources: ['LinkedIn', 'Jobicy'], remote_types: [], remote_css: {}, job_statuses: [], default_blacklist: [] }),
    sources: vi.fn().mockResolvedValue(['LinkedIn', 'Jobicy']),
  },
  jobs: { list: vi.fn().mockResolvedValue([]), counts: vi.fn().mockResolvedValue({ pending: 0, applied: 0, skipped: 0 }), get: vi.fn(), setStatus: vi.fn(), similar: vi.fn().mockResolvedValue([]), description: vi.fn(), clear: vi.fn() },
  documents: { templates: vi.fn(), buildResume: vi.fn(), resumeStatus: vi.fn(), buildCoverLetter: vi.fn(), coverLetterStatus: vi.fn() },
  fetcher: { trigger: vi.fn(), status: vi.fn().mockResolvedValue({ status: 'idle', message: '' }) },
  config: { get: vi.fn().mockResolvedValue({ searches: [], title_filter: [], blacklist: [], company_blacklist: [] }), save: vi.fn() },
  aiSettings: { get: vi.fn(), save: vi.fn(), test: vi.fn() },
}))

import { profiles as profilesApi } from '@/api/client'
import ProfileSettingsPage from '@/pages/ProfileSettings/index'

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderProfileSettings(slug = 'anis') {
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

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('Profile form — saving data', () => {
  beforeEach(() => {
    vi.mocked(profilesApi.getMarkdown).mockResolvedValue({ content: '' })
    vi.mocked(profilesApi.saveMarkdown).mockResolvedValue({ ok: true })
    vi.clearAllMocks()
    vi.mocked(profilesApi.list).mockResolvedValue({
      profiles: [{ slug: 'anis', name: 'anis', label: 'Anis', initials: 'A', color: '#3b82f6', active: true }],
      active_slug: 'anis',
    })
    vi.mocked(profilesApi.getMarkdown).mockResolvedValue({ content: '' })
    vi.mocked(profilesApi.saveMarkdown).mockResolvedValue({ ok: true })
    vi.mocked(profilesApi.getConfig).mockResolvedValue({ searches: [], title_filter: [], blacklist: [], company_blacklist: [] })
  })

  it('shows profile form fields when Profile section is active', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByPlaceholderText('Jane Smith')).toBeInTheDocument())
    expect(screen.getByPlaceholderText('jane@example.com')).toBeInTheDocument()
    // Location appears in contact + experience blocks — assert at least one exists
    expect(screen.getAllByPlaceholderText('City, Country').length).toBeGreaterThan(0)
  })

  it('calls saveMarkdown with name and email when user saves', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByPlaceholderText('Jane Smith')).toBeInTheDocument())

    await userEvent.type(screen.getByPlaceholderText('Jane Smith'), 'Anis Helaoui')
    await userEvent.type(screen.getByPlaceholderText('jane@example.com'), 'anis@example.com')
    fireEvent.click(screen.getByText('Save profile'))

    await waitFor(() => {
      expect(profilesApi.saveMarkdown).toHaveBeenCalledWith('anis', expect.stringContaining('Anis Helaoui'))
      const [, md] = vi.mocked(profilesApi.saveMarkdown).mock.calls[0]
      expect(md).toContain('anis@example.com')
    })
  })

  it('validates that name is required — shows error toast, does not save', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByText('Save profile')).toBeInTheDocument())

    // Click save with empty name
    fireEvent.click(screen.getByText('Save profile'))

    // Error toast should appear with the specific message
    await waitFor(() => expect(screen.getByText('Please enter your full name')).toBeInTheDocument())
    expect(profilesApi.saveMarkdown).not.toHaveBeenCalled()
  })

  it('pre-fills form fields from existing profile markdown', async () => {
    const existingMd = [
      '# Anis Helaoui — Full Profile', '',
      '## Contact',
      '- Location: Tunis, Tunisia',
      '- Email: anis@example.com',
      '- Phone: +216 99 000 000',
      '', '---',
    ].join('\n')
    vi.mocked(profilesApi.getMarkdown).mockResolvedValue({ content: existingMd })

    renderProfileSettings()

    await waitFor(() => {
      expect(screen.getByText('✓ Saved profile loaded')).toBeInTheDocument()
      expect((screen.getByPlaceholderText('Jane Smith') as HTMLInputElement).value).toBe('Anis Helaoui')
      expect((screen.getByPlaceholderText('jane@example.com') as HTMLInputElement).value).toBe('anis@example.com')
      // Phone has a unique placeholder
      expect((screen.getByPlaceholderText('+1 555 000 0000') as HTMLInputElement).value).toBe('+216 99 000 000')
    })
  })

  it('saves professional summary text', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByPlaceholderText('Jane Smith')).toBeInTheDocument())

    await userEvent.type(screen.getByPlaceholderText('Jane Smith'), 'Anis')
    await userEvent.type(screen.getByPlaceholderText('jane@example.com'), 'anis@example.com')
    // textarea has a unique placeholder
    await userEvent.type(
      screen.getByPlaceholderText('2–3 sentence professional summary'),
      'Experienced product manager.'
    )
    fireEvent.click(screen.getByText('Save profile'))

    await waitFor(() => {
      const [, md] = vi.mocked(profilesApi.saveMarkdown).mock.calls[0]
      expect(md).toContain('Experienced product manager.')
    })
  })

  it('can add and save a competency', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByPlaceholderText('Jane Smith')).toBeInTheDocument())

    await userEvent.type(screen.getByPlaceholderText('Jane Smith'), 'Anis')
    await userEvent.type(screen.getByPlaceholderText('jane@example.com'), 'anis@example.com')

    const [firstCompetency] = screen.getAllByPlaceholderText('e.g. Agile / SAFe Methodologies')
    await userEvent.type(firstCompetency, 'Product Strategy')
    fireEvent.click(screen.getByText('Save profile'))

    await waitFor(() => {
      const [, md] = vi.mocked(profilesApi.saveMarkdown).mock.calls[0]
      expect(md).toContain('Product Strategy')
    })
  })

  it('data survives a round-trip: save then reload shows same values', async () => {
    let savedContent = ''
    vi.mocked(profilesApi.saveMarkdown).mockImplementation(async (_slug, content) => {
      savedContent = content
      return { ok: true }
    })

    const { unmount } = renderProfileSettings()
    await waitFor(() => expect(screen.getByPlaceholderText('Jane Smith')).toBeInTheDocument())
    await userEvent.type(screen.getByPlaceholderText('Jane Smith'), 'Anis Helaoui')
    await userEvent.type(screen.getByPlaceholderText('jane@example.com'), 'anis@test.com')
    fireEvent.click(screen.getByText('Save profile'))
    await waitFor(() => expect(savedContent).toBeTruthy())
    unmount()

    // Reload: API returns what was saved
    vi.mocked(profilesApi.getMarkdown).mockResolvedValue({ content: savedContent })
    renderProfileSettings()

    await waitFor(() => {
      expect((screen.getByPlaceholderText('Jane Smith') as HTMLInputElement).value).toBe('Anis Helaoui')
      expect((screen.getByPlaceholderText('jane@example.com') as HTMLInputElement).value).toBe('anis@test.com')
    })
  })
})

describe('Profile form — search settings section', () => {
  beforeEach(() => {
    vi.mocked(profilesApi.getMarkdown).mockResolvedValue({ content: '' })
    vi.mocked(profilesApi.getConfig).mockResolvedValue({
      searches: [
        { name: 'LinkedIn - Product Manager', source: 'LinkedIn', query: 'Product Manager', location: 'United States', max_pages: 3, remote: true },
      ],
      title_filter: ['product manager', 'pm'],
      blacklist: ['junior', 'intern'],
      company_blacklist: [],
    })
  })

  it('shows search settings when user clicks that nav item', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByText('🔍 Search Settings')).toBeInTheDocument())

    fireEvent.click(screen.getByText('🔍 Search Settings'))

    await waitFor(() => {
      expect(screen.getByText('Search Settings')).toBeInTheDocument()
      // Should load and show the existing search query
      expect(screen.getByRole('button', { name: /remove product manager/i })).toBeInTheDocument()
    })
  })

  it('does not show a separate title filter control', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByText('🔍 Search Settings')).toBeInTheDocument())
    fireEvent.click(screen.getByText('🔍 Search Settings'))

    await waitFor(() => {
      expect(screen.queryByText(/Title Filter/i)).not.toBeInTheDocument()
    })
  })

  it('shows existing blacklist entries as tags', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByText('🔍 Search Settings')).toBeInTheDocument())
    fireEvent.click(screen.getByText('🔍 Search Settings'))

    await waitFor(() => {
      expect(screen.getByText('junior')).toBeInTheDocument()
      expect(screen.getByText('intern')).toBeInTheDocument()
    })
  })

  it('saving search settings calls saveConfig with the right data', async () => {
    renderProfileSettings()
    await waitFor(() => expect(screen.getByText('🔍 Search Settings')).toBeInTheDocument())
    fireEvent.click(screen.getByText('🔍 Search Settings'))
    await waitFor(() => expect(screen.getByText('Save search settings')).toBeInTheDocument())

    fireEvent.click(screen.getByText('Save search settings'))

    await waitFor(() => {
      expect(profilesApi.saveConfig).toHaveBeenCalledWith('anis', expect.objectContaining({
        title_filter: ['product manager'],
        blacklist: expect.arrayContaining(['junior', 'intern']),
      }))
    })
  })
})
