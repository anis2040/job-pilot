import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useAiSettings } from '@/pages/AiSettings/hooks/useAiSettings';
import { aiSettings as aiSettingsApi, setup } from '@/api/client';

const showToast = vi.fn();

vi.mock('@/components/ui/useToast', () => ({
  useToast: () => ({ showToast }),
}));

vi.mock('@/api/client', () => ({
  aiSettings: {
    get: vi.fn(),
    save: vi.fn(),
    test: vi.fn(),
  },
  setup: {
    saveGroqKey: vi.fn(),
    saveGeminiKey: vi.fn(),
    saveAnthropicKey: vi.fn(),
    saveOpenrouterKey: vi.fn(),
  },
}));

const BASE_SETTINGS = {
  active_provider: 'groq',
  preferred_provider: 'groq',
  semantic_match: false,
  embeddings_available: true,
  providers: {
    groq: { configured: true, model: 'llama-3.3-70b-versatile', key_set: true, key: '', models: ['llama-3.3-70b-versatile'], usage: null },
    gemini: { configured: true, model: 'gemini-3.5-flash-lite', key_set: true, key: '', models: ['gemini-3.5-flash-lite'], usage: null },
    claude: { configured: false, model: 'claude-cli', key_set: false, key: '', models: [], usage: null },
  },
};

describe('useAiSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(aiSettingsApi.get).mockResolvedValue({ ...BASE_SETTINGS });
    vi.mocked(aiSettingsApi.save).mockResolvedValue({ ok: true, updated: [] });
    vi.mocked(aiSettingsApi.test).mockResolvedValue({ ok: true, model: 'test-model', latency_ms: 42 });
    vi.mocked(setup.saveGroqKey).mockResolvedValue({ ok: true });
  });

  it('loads settings and preferred provider on mount', async () => {
    const { result } = renderHook(() => useAiSettings());

    await waitFor(() => expect(result.current.data).not.toBeNull());
    expect(result.current.preferred).toBe('groq');
  });

  it('falls back to active_provider when preferred_provider is null', async () => {
    vi.mocked(aiSettingsApi.get).mockResolvedValue({
      ...BASE_SETTINGS,
      preferred_provider: null,
      active_provider: 'gemini',
    });

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.preferred).toBe('gemini'));
  });

  it('selectProvider saves preference and refreshes', async () => {
    const refreshed = { ...BASE_SETTINGS, preferred_provider: 'gemini', active_provider: 'gemini' };
    vi.mocked(aiSettingsApi.get)
      .mockResolvedValueOnce({ ...BASE_SETTINGS })
      .mockResolvedValueOnce(refreshed);

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    await act(async () => {
      await result.current.selectProvider('gemini');
    });

    expect(aiSettingsApi.save).toHaveBeenCalledWith({ preferred_provider: 'gemini' });
    expect(result.current.preferred).toBe('gemini');
  });

  it('selectProvider shows error toast on failure and rolls back preference', async () => {
    vi.mocked(aiSettingsApi.save).mockRejectedValueOnce(new Error('fail'));

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    await act(async () => {
      await result.current.selectProvider('gemini');
    });

    expect(showToast).toHaveBeenCalledWith('Failed to save preference', 'err');
    expect(result.current.preferred).toBe('groq');
  });

  it('selectProvider skips save when already preferred', async () => {
    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    await act(async () => {
      await result.current.selectProvider('groq');
    });

    expect(aiSettingsApi.save).not.toHaveBeenCalled();
  });

  it('sets loadError when initial load fails', async () => {
    vi.mocked(aiSettingsApi.get).mockRejectedValueOnce(new Error('fail'));

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it('retryLoad clears loadError on success', async () => {
    vi.mocked(aiSettingsApi.get)
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce({ ...BASE_SETTINGS });

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.loadError).toBe(true));

    act(() => {
      result.current.retryLoad();
    });

    await waitFor(() => expect(result.current.loadError).toBe(false));
    expect(result.current.data).not.toBeNull();
  });

  it('saveKey calls setup and refreshes on success', async () => {
    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    let ok = false;
    await act(async () => {
      ok = await result.current.saveKey('groq', 'gsk_new_key');
    });

    expect(setup.saveGroqKey).toHaveBeenCalledWith('gsk_new_key');
    expect(aiSettingsApi.get).toHaveBeenCalledTimes(2);
    expect(ok).toBe(true);
  });

  it('saveKey returns false for unknown provider', async () => {
    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    let ok = true;
    await act(async () => {
      ok = await result.current.saveKey('unknown', 'key');
    });
    expect(ok).toBe(false);
  });

  it('saveKey returns false on API failure', async () => {
    vi.mocked(setup.saveGroqKey).mockRejectedValueOnce(new Error('fail'));

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    let ok = true;
    await act(async () => {
      ok = await result.current.saveKey('groq', 'gsk_new_key');
    });
    expect(ok).toBe(false);
  });

  it('saveModel posts model and preferred provider', async () => {
    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    await act(async () => {
      await result.current.saveModel('gemini', 'gemini-3.5-flash');
    });

    expect(aiSettingsApi.save).toHaveBeenCalledWith({
      gemini_model: 'gemini-3.5-flash',
      preferred_provider: 'gemini',
    });
    expect(showToast).toHaveBeenCalledWith('Gemini model saved');
  });

  it('saveModel is a no-op for claude', async () => {
    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    await act(async () => {
      await result.current.saveModel('claude', 'claude-cli');
    });

    expect(aiSettingsApi.save).not.toHaveBeenCalled();
  });

  it('saveModel shows error toast on failure and rolls back preference', async () => {
    vi.mocked(aiSettingsApi.save).mockRejectedValueOnce(new Error('fail'));

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    await act(async () => {
      await result.current.saveModel('gemini', 'gemini-3.5-flash');
    });

    expect(showToast).toHaveBeenCalledWith('Failed to save Gemini model', 'err');
    expect(result.current.preferred).toBe('groq');
  });

  it('testProvider forwards to aiSettings.test', async () => {
    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    let res: Awaited<ReturnType<typeof result.current.testProvider>> | undefined;
    await act(async () => {
      res = await result.current.testProvider('groq');
    });

    expect(aiSettingsApi.test).toHaveBeenCalledWith('groq');
    expect(res).toEqual({ ok: true, model: 'test-model', latency_ms: 42 });
  });

  it('testProvider returns error response on API failure', async () => {
    vi.mocked(aiSettingsApi.test).mockRejectedValueOnce(new Error('fail'));

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    let res: Awaited<ReturnType<typeof result.current.testProvider>> | undefined;
    await act(async () => {
      res = await result.current.testProvider('groq');
    });

    expect(res).toEqual({ ok: false, error: 'Connection test failed' });
  });

  it('toggleSemantic updates local state and toasts', async () => {
    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    await act(async () => {
      await result.current.toggleSemantic(true);
    });

    expect(aiSettingsApi.save).toHaveBeenCalledWith({ semantic_match: true });
    expect(result.current.data?.semantic_match).toBe(true);
    expect(showToast).toHaveBeenCalledWith('Smart matching on');

    await act(async () => {
      await result.current.toggleSemantic(false);
    });
    expect(showToast).toHaveBeenCalledWith('Smart matching off');
  });

  it('toggleSemantic shows error toast on failure', async () => {
    vi.mocked(aiSettingsApi.save).mockRejectedValueOnce(new Error('fail'));

    const { result } = renderHook(() => useAiSettings());
    await waitFor(() => expect(result.current.data).not.toBeNull());

    await act(async () => {
      await result.current.toggleSemantic(true);
    });

    expect(showToast).toHaveBeenCalledWith('Failed to update', 'err');
  });
});
