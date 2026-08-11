import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import {
  BUILD_CV_INSTRUCTIONS_MAX_LENGTH,
  useBuildCvPositioning,
} from '@/hooks/useBuildCvPositioning'
import { profiles as profilesApi } from '@/api/client'

vi.mock('@/api/client', () => ({
  profiles: {
    getConfig: vi.fn(),
    saveConfig: vi.fn().mockResolvedValue({ ok: true }),
  },
}))

const EXISTING_CONFIG = {
  searches: [{ name: 's1', source: 'LinkedIn', query: 'eng', location: 'Berlin', max_pages: 1, remote: true }],
  title_filter: ['senior'],
  blacklist: ['intern'],
  company_blacklist: ['BadCo'],
}

describe('useBuildCvPositioning', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(profilesApi.getConfig).mockResolvedValue({ ...EXISTING_CONFIG })
    vi.mocked(profilesApi.saveConfig).mockResolvedValue({ ok: true })
  })

  it('loads default positioning when build_cv is missing', async () => {
    const { result } = renderHook(() => useBuildCvPositioning('anis'))

    await waitFor(() => expect(result.current.ready).toBe(true))

    expect(result.current.positioning).toBe('balanced')
    expect(result.current.instructions).toBe('')
  })

  it('loads saved positioning config', async () => {
    vi.mocked(profilesApi.getConfig).mockResolvedValue({
      ...EXISTING_CONFIG,
      build_cv: { experience_positioning: 'aggressive', additional_instructions: 'Focus on product roles' },
    })

    const { result } = renderHook(() => useBuildCvPositioning('anis'))

    await waitFor(() => expect(result.current.positioning).toBe('aggressive'))
    expect(result.current.instructions).toBe('Focus on product roles')
  })

  it('saves a stance with read-modify-write semantics', async () => {
    vi.mocked(profilesApi.getConfig).mockResolvedValue({
      ...EXISTING_CONFIG,
      build_cv: { experience_positioning: 'balanced', additional_instructions: 'Keep instructions' },
    })
    const { result } = renderHook(() => useBuildCvPositioning('anis'))
    await waitFor(() => expect(result.current.ready).toBe(true))

    await act(async () => { await result.current.savePositioning('conservative') })

    expect(profilesApi.saveConfig).toHaveBeenCalledWith('anis', {
      ...EXISTING_CONFIG,
      build_cv: { experience_positioning: 'conservative', additional_instructions: 'Keep instructions' },
    })
  })

  it('trims and caps additional instructions before saving', async () => {
    const longInstructions = `  ${'x'.repeat(BUILD_CV_INSTRUCTIONS_MAX_LENGTH + 20)}  `
    const { result } = renderHook(() => useBuildCvPositioning('anis'))
    await waitFor(() => expect(result.current.ready).toBe(true))

    act(() => { result.current.setInstructions(longInstructions) })
    await act(async () => { await result.current.saveInstructions() })

    const [, saved] = vi.mocked(profilesApi.saveConfig).mock.calls[0]
    expect(saved.build_cv?.additional_instructions).toHaveLength(BUILD_CV_INSTRUCTIONS_MAX_LENGTH)
    expect(saved.build_cv?.additional_instructions).toBe('x'.repeat(BUILD_CV_INSTRUCTIONS_MAX_LENGTH))
  })
})
