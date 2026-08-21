import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useStance } from '@/hooks/useStance'
import { profiles as profilesApi } from '@/api/client'

const activeProfile = { slug: 'anis', name: 'anis', label: 'Anis', initials: 'A', color: '#3b82f6', active: true }

vi.mock('@/hooks/useProfile', () => ({
  useProfile: () => ({ active: activeProfile }),
}))

vi.mock('@/api/client', () => ({
  profiles: {
    getConfig: vi.fn(),
    saveConfig: vi.fn().mockResolvedValue({ ok: true }),
  },
}))

describe('useStance', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(profilesApi.getConfig).mockResolvedValue({
      searches: [{ name: 's1', source: 'LinkedIn', query: 'eng', location: 'Berlin', max_pages: 1, remote: true }],
      title_filter: ['frontend'],
      blacklist: ['intern'],
      company_blacklist: ['BadCo'],
    })
    vi.mocked(profilesApi.saveConfig).mockResolvedValue({ ok: true })
  })

  it('loads Balanced by default when build_cv is missing', async () => {
    const { result } = renderHook(() => useStance())

    await waitFor(() => expect(result.current.ready).toBe(true))

    expect(result.current.stance).toBe('balanced')
    expect(result.current.resumeTemplateId).toBe('us')
  })

  it('loads a saved stance from profile config', async () => {
    vi.mocked(profilesApi.getConfig).mockResolvedValue({
      searches: [],
      title_filter: [],
      blacklist: [],
      company_blacklist: [],
      build_cv: { experience_positioning: 'aggressive', additional_instructions: 'Focus on roadmap', resume_template_id: 'eu' },
    })

    const { result } = renderHook(() => useStance())

    await waitFor(() => expect(result.current.stance).toBe('aggressive'))
    expect(result.current.resumeTemplateId).toBe('eu')
  })

  it('saves stance without clobbering existing config or instructions', async () => {
    vi.mocked(profilesApi.getConfig).mockResolvedValue({
      searches: [{ name: 's1', source: 'LinkedIn', query: 'eng', location: 'Berlin', max_pages: 1, remote: true }],
      title_filter: ['frontend'],
      blacklist: ['intern'],
      company_blacklist: ['BadCo'],
      build_cv: { experience_positioning: 'balanced', additional_instructions: 'Keep this', resume_template_id: 'eu' },
    })
    const { result } = renderHook(() => useStance())
    await waitFor(() => expect(result.current.ready).toBe(true))

    await act(async () => { await result.current.saveStance('conservative') })

    expect(profilesApi.saveConfig).toHaveBeenCalledWith('anis', expect.objectContaining({
      searches: [{ name: 's1', source: 'LinkedIn', query: 'eng', location: 'Berlin', max_pages: 1, remote: true }],
      title_filter: ['frontend'],
      blacklist: ['intern'],
      company_blacklist: ['BadCo'],
      build_cv: { experience_positioning: 'conservative', additional_instructions: 'Keep this', resume_template_id: 'eu' },
    }))
  })

  it('saves template without clobbering existing config or instructions', async () => {
    vi.mocked(profilesApi.getConfig).mockResolvedValue({
      searches: [{ name: 's1', source: 'LinkedIn', query: 'eng', location: 'Berlin', max_pages: 1, remote: true }],
      title_filter: ['frontend'],
      blacklist: ['intern'],
      company_blacklist: ['BadCo'],
      build_cv: { experience_positioning: 'balanced', additional_instructions: 'Keep this', resume_template_id: 'us' },
    })
    const { result } = renderHook(() => useStance())
    await waitFor(() => expect(result.current.ready).toBe(true))

    await act(async () => { await result.current.saveResumeTemplate('eu') })

    expect(profilesApi.saveConfig).toHaveBeenCalledWith('anis', expect.objectContaining({
      searches: [{ name: 's1', source: 'LinkedIn', query: 'eng', location: 'Berlin', max_pages: 1, remote: true }],
      title_filter: ['frontend'],
      blacklist: ['intern'],
      company_blacklist: ['BadCo'],
      build_cv: { experience_positioning: 'balanced', additional_instructions: 'Keep this', resume_template_id: 'eu' },
    }))
  })
})
