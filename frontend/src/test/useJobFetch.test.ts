import { describe, it, expect } from 'vitest';
import { FETCH_STATUS_POLL_MS, FETCH_JOBS_RELOAD_MS } from '@/pages/Dashboard/hooks/useJobFetch';

describe('useJobFetch tuning', () => {
  it('polls status more often than full job reloads during fetch', () => {
    expect(FETCH_STATUS_POLL_MS).toBeLessThan(FETCH_JOBS_RELOAD_MS);
  });
});
