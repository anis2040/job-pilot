import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import {
  useTransientAlert,
  ALERT_FADE_MS,
  ALERT_CLEAR_MS,
} from '@/pages/AiSettings/hooks/useTransientAlert';

describe('useTransientAlert', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts with no alert and not fading', () => {
    const { result } = renderHook(() => useTransientAlert());
    expect(result.current.alert).toBeNull();
    expect(result.current.fading).toBe(false);
  });

  it('keeps neutral alerts visible without fade or clear', () => {
    const { result } = renderHook(() => useTransientAlert());

    act(() => {
      result.current.setAlert({ kind: 'neutral', text: 'Saving key…' });
    });
    expect(result.current.alert).toEqual({ kind: 'neutral', text: 'Saving key…' });
    expect(result.current.fading).toBe(false);

    act(() => {
      vi.advanceTimersByTime(ALERT_CLEAR_MS + 100);
    });
    expect(result.current.alert).toEqual({ kind: 'neutral', text: 'Saving key…' });
    expect(result.current.fading).toBe(false);
  });

  it('fades ok/err alerts then clears them', () => {
    const { result } = renderHook(() => useTransientAlert());

    act(() => {
      result.current.setAlert({ kind: 'ok', text: 'Key saved' });
    });
    expect(result.current.fading).toBe(false);

    act(() => {
      vi.advanceTimersByTime(ALERT_FADE_MS);
    });
    expect(result.current.fading).toBe(true);
    expect(result.current.alert).toEqual({ kind: 'ok', text: 'Key saved' });

    act(() => {
      vi.advanceTimersByTime(ALERT_CLEAR_MS - ALERT_FADE_MS);
    });
    expect(result.current.alert).toBeNull();
    expect(result.current.fading).toBe(false);
  });

  it('resets timers when alert is replaced', () => {
    const { result } = renderHook(() => useTransientAlert());

    act(() => {
      result.current.setAlert({ kind: 'ok', text: 'First' });
    });
    act(() => {
      vi.advanceTimersByTime(ALERT_FADE_MS);
    });
    expect(result.current.fading).toBe(true);

    act(() => {
      result.current.setAlert({ kind: 'ok', text: 'Second' });
    });
    expect(result.current.fading).toBe(false);
    expect(result.current.alert).toEqual({ kind: 'ok', text: 'Second' });

    act(() => {
      vi.advanceTimersByTime(ALERT_CLEAR_MS);
    });
    expect(result.current.alert).toBeNull();
  });

  it('clears fading when alert is set to null', () => {
    const { result } = renderHook(() => useTransientAlert());

    act(() => {
      result.current.setAlert({ kind: 'err', text: 'Failed' });
    });
    act(() => {
      vi.advanceTimersByTime(ALERT_FADE_MS);
    });
    expect(result.current.fading).toBe(true);

    act(() => {
      result.current.setAlert(null);
    });
    expect(result.current.alert).toBeNull();
    expect(result.current.fading).toBe(false);

    act(() => {
      vi.advanceTimersByTime(ALERT_CLEAR_MS);
    });
    expect(result.current.alert).toBeNull();
  });

  it('cleans up timers on unmount', () => {
    const clearSpy = vi.spyOn(window, 'clearTimeout');
    const { result, unmount } = renderHook(() => useTransientAlert());

    act(() => {
      result.current.setAlert({ kind: 'ok', text: 'Key saved' });
    });
    unmount();

    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });
});
