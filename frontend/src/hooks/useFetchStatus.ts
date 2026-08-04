import { usePolling } from './usePolling';
import { fetcher as fetcherApi } from '../api/client';
import type { FetchStatus } from '../api/types';

export function useFetchStatus(enabled: boolean) {
  const { data, loading, error } = usePolling<FetchStatus>(
    fetcherApi.status,
    2000,
    enabled,
    d => d.status !== 'running'
  );

  return {
    isRunning: data?.status === 'running',
    source: data?.source ?? null,
    progress: data?.progress ?? null,
    total: data?.total ?? null,
    error: data?.error ?? error,
    message: data?.message ?? '',
    loading,
  };
}
