import { useState, useCallback, useEffect } from 'react';
import { jobs as jobsApi } from '../api/client';
import type { Job } from '../api/types';

export function useJobs(status: string) {
  const [data, setData] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      const result = await jobsApi.list(status);
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [status]);

  useEffect(() => {
    setLoading(true);
    fetch().finally(() => setLoading(false));
  }, [fetch]);

  return { jobs: data, loading, error, refetch: fetch };
}
