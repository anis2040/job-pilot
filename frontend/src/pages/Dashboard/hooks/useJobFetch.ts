import { useState, useRef, useEffect } from 'react';
import { fetcher as fetcherApi } from '../../../api/client';
import { useToast } from '../../../components/ui/useToast';

type LoadFn = () => Promise<unknown>;

/** Poll fetch-status only; reload jobs at start, finish, and at most this often while running. */
export const FETCH_STATUS_POLL_MS = 2000;
export const FETCH_JOBS_RELOAD_MS = 12000;

export function useJobFetch(loadJobs: LoadFn, loadCounts: LoadFn, setLoading: (loading: boolean) => void) {
  const { showToast } = useToast();
  const [fetchRunning, setFetchRunning] = useState(false);
  const [fetchMessage, setFetchMessage] = useState('');
  const fetchPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fetchRefreshInFlightRef = useRef(false);
  const lastJobsReloadAtRef = useRef(0);
  const lastRunningMessageRef = useRef('');
  const handleFetchRef = useRef<() => void>(() => {});

  useEffect(() => () => { if (fetchPollRef.current) clearInterval(fetchPollRef.current); }, []);

  const reloadJobsIfDue = (force: boolean) => {
    if (fetchRefreshInFlightRef.current) return;
    const now = Date.now();
    if (!force && now - lastJobsReloadAtRef.current < FETCH_JOBS_RELOAD_MS) return;
    lastJobsReloadAtRef.current = now;
    fetchRefreshInFlightRef.current = true;
    Promise.all([loadJobs(), loadCounts()]).finally(() => {
      fetchRefreshInFlightRef.current = false;
    });
  };

  const handleFetch = async () => {
    setFetchRunning(true);
    setFetchMessage('Starting fetch…');
    lastRunningMessageRef.current = '';
    lastJobsReloadAtRef.current = 0;
    try {
      const result = await fetcherApi.trigger();
      if (!result.started) {
        setFetchRunning(false);
        showToast(result.message || 'Could not start fetch — please try again', 'err');
        return;
      }
    } catch {
      setFetchRunning(false);
      showToast('Could not start fetch — please try again', 'err');
      return;
    }
    if (fetchPollRef.current) clearInterval(fetchPollRef.current);
    const pollFetchStatus = async () => {
      try {
        const s = await fetcherApi.status();
        if (s.status === 'running' && s.message) {
          lastRunningMessageRef.current = s.message;
          setFetchMessage(s.message);
        } else if (s.message && !lastRunningMessageRef.current) {
          setFetchMessage(s.message);
        }
        if (s.status === 'running') {
          reloadJobsIfDue(lastJobsReloadAtRef.current === 0);
        }
        if (s.status !== 'running') {
          if (fetchPollRef.current) clearInterval(fetchPollRef.current);
          fetchPollRef.current = null;
          setFetchRunning(false);
          setLoading(true);
          await Promise.all([loadJobs(), loadCounts()]);
          setLoading(false);
          setTimeout(() => setFetchMessage(''), 3000);
        }
        return s.status === 'running';
      } catch {
        if (fetchPollRef.current) clearInterval(fetchPollRef.current);
        fetchPollRef.current = null;
        setFetchRunning(false);
        showToast('Lost connection while fetching', 'err');
        return false;
      }
    };
    if (await pollFetchStatus()) {
      fetchPollRef.current = setInterval(pollFetchStatus, FETCH_STATUS_POLL_MS);
    }
  };

  handleFetchRef.current = handleFetch;

  return { fetchRunning, fetchMessage, handleFetch, handleFetchRef };
}
