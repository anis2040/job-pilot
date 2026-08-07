import { useState, useRef, useEffect } from 'react';
import { fetcher as fetcherApi } from '../../../api/client';
import { useToast } from '../../../components/ui/useToast';

type LoadFn = () => Promise<unknown>;

export function useJobFetch(loadJobs: LoadFn, loadCounts: LoadFn, setLoading: (loading: boolean) => void) {
  const { showToast } = useToast();
  const [fetchRunning, setFetchRunning] = useState(false);
  const [fetchMessage, setFetchMessage] = useState('');
  const fetchPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fetchRefreshInFlightRef = useRef(false);
  const handleFetchRef = useRef<() => void>(() => {});

  useEffect(() => () => { if (fetchPollRef.current) clearInterval(fetchPollRef.current); }, []);

  const handleFetch = async () => {
    setFetchRunning(true);
    setFetchMessage('Starting fetch…');
    try {
      await fetcherApi.trigger();
    } catch {
      setFetchRunning(false);
      showToast('Could not start fetch — please try again', 'err');
      return;
    }
    if (fetchPollRef.current) clearInterval(fetchPollRef.current);
    fetchPollRef.current = setInterval(async () => {
      try {
        const s = await fetcherApi.status();
        if (s.message) setFetchMessage(s.message);
        if (s.status === 'running' && !fetchRefreshInFlightRef.current) {
          fetchRefreshInFlightRef.current = true;
          Promise.all([loadJobs(), loadCounts()]).finally(() => {
            fetchRefreshInFlightRef.current = false;
          });
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
      } catch {
        if (fetchPollRef.current) clearInterval(fetchPollRef.current);
        fetchPollRef.current = null;
        setFetchRunning(false);
        showToast('Lost connection while fetching', 'err');
      }
    }, 1500);
  };

  handleFetchRef.current = handleFetch;

  return { fetchRunning, fetchMessage, handleFetch, handleFetchRef };
}
