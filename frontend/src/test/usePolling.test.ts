import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePolling } from '@/hooks/usePolling'

describe('usePolling', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('calls fetcher immediately when enabled', async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 'idle' })
    renderHook(() => usePolling(fetcher, 2000, true))
    await act(async () => {})
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('does not call fetcher when disabled', async () => {
    const fetcher = vi.fn().mockResolvedValue({})
    renderHook(() => usePolling(fetcher, 2000, false))
    await act(async () => {})
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('calls fetcher again after interval', async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 'running' })
    renderHook(() => usePolling(fetcher, 2000, true))
    await act(async () => {})
    expect(fetcher).toHaveBeenCalledTimes(1)
    await act(async () => { vi.advanceTimersByTime(2000) })
    await act(async () => {})
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('stops polling when stopWhen returns true', async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 'done' })
    renderHook(() => usePolling(fetcher, 1000, true, (d: { status: string }) => d.status === 'done'))
    await act(async () => {})
    // Advance timer — should NOT call again since stopWhen returned true
    await act(async () => { vi.advanceTimersByTime(3000) })
    await act(async () => {})
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('sets error on fetch failure', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => usePolling(fetcher, 1000, true))
    await act(async () => {})
    expect(result.current.error).toBe('Network error')
  })

  it('sets data on success', async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 42 })
    const { result } = renderHook(() => usePolling(fetcher, 1000, true))
    await act(async () => {})
    expect(result.current.data).toEqual({ value: 42 })
  })

  it('stops polling when disabled mid-run', async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 'running' })
    const { rerender } = renderHook(
      ({ enabled }) => usePolling(fetcher, 1000, enabled),
      { initialProps: { enabled: true } }
    )
    await act(async () => {})
    expect(fetcher).toHaveBeenCalledTimes(1)
    rerender({ enabled: false })
    await act(async () => { vi.advanceTimersByTime(3000) })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('clears interval on unmount', async () => {
    const fetcher = vi.fn().mockResolvedValue({})
    const { unmount } = renderHook(() => usePolling(fetcher, 1000, true))
    await act(async () => {})
    unmount()
    await act(async () => { vi.advanceTimersByTime(3000) })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})
