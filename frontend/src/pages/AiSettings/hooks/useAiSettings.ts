import { useCallback, useEffect, useState } from 'react';
import { aiSettings as aiSettingsApi } from '../../../api/client';
import { useToast } from '../../../components/ui/useToast';
import type { AiSettings } from '../../../api/types';
import { KEY_SAVE, PROVIDER_META } from '../constants';
import type { ProviderTestResponse } from '../types';

function resolvePreferred(settings: AiSettings): string | null {
  return settings.preferred_provider || settings.active_provider || null;
}

export function useAiSettings() {
  const [data, setData] = useState<AiSettings | null>(null);
  const [preferred, setPreferred] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const { showToast } = useToast();

  const refresh = useCallback(async () => {
    const updated = await aiSettingsApi.get();
    setData(updated);
    setPreferred(resolvePreferred(updated));
    setLoadError(false);
    return updated;
  }, []);

  useEffect(() => {
    void refresh().catch(() => setLoadError(true));
  }, [refresh]);

  const retryLoad = useCallback(() => {
    setLoadError(false);
    void refresh().catch(() => setLoadError(true));
  }, [refresh]);

  const selectProvider = useCallback(async (pid: string) => {
    if (pid === preferred) return;
    const prev = preferred;
    setPreferred(pid);
    try {
      await aiSettingsApi.save({ preferred_provider: pid });
      await refresh();
    } catch {
      setPreferred(prev);
      showToast('Failed to save preference', 'err');
    }
  }, [preferred, refresh, showToast]);

  const saveKey = useCallback(async (pid: string, key: string) => {
    const saveFn = KEY_SAVE[pid];
    if (!saveFn) return false;
    try {
      const res = await saveFn(key);
      if (res.ok) {
        await refresh();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, [refresh]);

  const saveModel = useCallback(async (pid: string, model: string) => {
    if (pid === 'claude') return;
    const label = PROVIDER_META[pid]?.label ?? pid;
    const prev = preferred;
    setPreferred(pid);
    try {
      await aiSettingsApi.save({ [`${pid}_model`]: model, preferred_provider: pid });
      await refresh();
      showToast(`${label} model saved`);
    } catch {
      setPreferred(prev);
      showToast(`Failed to save ${label} model`, 'err');
    }
  }, [preferred, refresh, showToast]);

  const testProvider = useCallback(async (pid: string): Promise<ProviderTestResponse> => {
    try {
      return await aiSettingsApi.test(pid);
    } catch {
      return { ok: false, error: 'Connection test failed' };
    }
  }, []);

  const toggleSemantic = useCallback(async (checked: boolean) => {
    try {
      await aiSettingsApi.save({ semantic_match: checked });
      setData(d => d ? { ...d, semantic_match: checked } : d);
      showToast(checked ? 'Smart matching on' : 'Smart matching off');
    } catch {
      showToast('Failed to update', 'err');
    }
  }, [showToast]);

  return {
    data,
    preferred,
    loadError,
    retryLoad,
    selectProvider,
    saveKey,
    saveModel,
    testProvider,
    toggleSemantic,
  };
}
