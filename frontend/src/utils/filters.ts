import type { Job } from '../api/types'

export interface Filters {
  remote: string[];
  source: string;
  posted: string;
  sort: string;
  search: string;
}

export const DEFAULT_FILTERS: Filters = { remote: [], source: '', posted: '', sort: 'match', search: '' };

export function filtersToKey(f: Filters): string {
  return JSON.stringify({ r: f.remote, s: f.source, p: f.posted, so: f.sort, q: f.search });
}

export function applyFilters(jobs: Job[], filters: Filters): Job[] {
  let result = [...jobs];
  if (filters.search) {
    const q = filters.search.toLowerCase();
    result = result.filter(j =>
      j.title.toLowerCase().includes(q) ||
      j.company.toLowerCase().includes(q) ||
      j.location?.toLowerCase().includes(q) ||
      j.source?.toLowerCase().includes(q)
    );
  }
  if (filters.remote.length) result = result.filter(j => filters.remote.includes(j.remote));
  // Source dropdown carries lowercase source ids (from /api/sources) while each
  // job's `source` is a display label (e.g. "LinkedIn"); compare case-insensitively.
  if (filters.source) {
    const want = filters.source.toLowerCase();
    result = result.filter(j => (j.source ?? '').toLowerCase() === want);
  }
  if (filters.posted) {
    const days = parseInt(filters.posted);
    const cutoff = Date.now() - days * 86400000;
    result = result.filter(j => j.posted_at && new Date(j.posted_at).getTime() >= cutoff);
  }
  const sorted = [...result];
  const sortFns: Record<string, (a: Job, b: Job) => number> = {
    match: (a, b) => {
      const sa = a.match?.score ?? null;
      const sb = b.match?.score ?? null;
      if (sa === null && sb === null) return 0;
      if (sa === null) return 1;
      if (sb === null) return -1;
      return sb - sa;
    },
    posted:  (a, b) => new Date(b.posted_at || 0).getTime() - new Date(a.posted_at || 0).getTime(),
    newest:  (a, b) => new Date(b.first_seen_at || 0).getTime() - new Date(a.first_seen_at || 0).getTime(),
    oldest:  (a, b) => new Date(a.first_seen_at || 0).getTime() - new Date(b.first_seen_at || 0).getTime(),
    title:   (a, b) => a.title.localeCompare(b.title),
    company: (a, b) => a.company.localeCompare(b.company),
  };
  sorted.sort(sortFns[filters.sort] ?? sortFns.match);
  return sorted;
}
