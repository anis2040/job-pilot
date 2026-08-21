import type { Job } from '../api/types'

export interface Filters {
  remote: string[];
  source: string;
  sources: string[];
  locations: string[];
  posted: string;
  cv: string;
  sort: string;
  search: string;
}

export const DEFAULT_FILTERS: Filters = { remote: [], source: '', sources: [], locations: [], posted: '', cv: '', sort: 'posted', search: '' };

export function filtersToKey(f: Filters): string {
  return JSON.stringify({ r: f.remote, s: f.source, ss: f.sources, l: f.locations, p: f.posted, cv: f.cv, so: f.sort, q: f.search });
}

const COUNTRY_SIGNALS: Record<string, string[]> = {
  'united states': ['united states', 'us', 'usa', ' us,', ', us', '(us)', 'u.s.', 'remote us', 'remote - us', 'us remote', 'new york', ', ny'],
  germany: ['germany', 'deutschland', 'berlin', 'munich', 'muenchen', 'hamburg', 'frankfurt', 'cologne', 'koeln', 'dusseldorf', 'de,', ', de'],
  'united kingdom': ['united kingdom', 'uk', 'england', 'london', 'manchester', 'birmingham', 'glasgow', 'edinburgh', 'great britain'],
  france: ['france', 'paris', 'lyon', 'marseille', 'toulouse'],
  canada: ['canada', 'ontario', 'toronto', 'vancouver', 'montreal', 'quebec', 'alberta', 'calgary'],
  netherlands: ['netherlands', 'holland', 'amsterdam', 'rotterdam'],
  spain: ['spain', 'madrid', 'barcelona'],
  portugal: ['portugal', 'lisbon', 'porto'],
  switzerland: ['switzerland', 'zurich', 'geneva'],
  tunisia: ['tunisia', 'tunis'],
  morocco: ['morocco', 'casablanca', 'rabat'],
};

function locationMatches(jobLocation: string, searchLocation: string) {
  const wanted = searchLocation.trim().toLowerCase();
  if (!wanted || ['anywhere', 'worldwide', 'remote'].includes(wanted)) return true;

  const actual = (jobLocation || '').trim().toLowerCase();
  if (!actual || ['remote', 'worldwide', 'anywhere', 'global'].includes(actual)) return true;

  const targetKey = Object.keys(COUNTRY_SIGNALS).find(key => wanted === key || COUNTRY_SIGNALS[key].includes(wanted));
  if (!targetKey) return actual.includes(wanted) || wanted.includes(actual);

  for (const [otherKey, signals] of Object.entries(COUNTRY_SIGNALS)) {
    if (otherKey !== targetKey && signals.some(signal => actual.includes(signal))) return false;
  }
  return COUNTRY_SIGNALS[targetKey].some(signal => actual.includes(signal));
}

export function applyFilters(jobs: Job[], filters: Filters): Job[] {
  let result = [...jobs];
  const searchTerms = filters.search
    .split(/[,;|\n]+/)
    .map(term => term.trim().toLowerCase())
    .filter(Boolean);
  if (searchTerms.length) {
    result = result.filter(j =>
      searchTerms.some(q =>
        j.title.toLowerCase().includes(q) ||
        j.company.toLowerCase().includes(q) ||
        j.location?.toLowerCase().includes(q) ||
        j.source?.toLowerCase().includes(q)
      )
    );
  }
  if (filters.remote.length) result = result.filter(j => filters.remote.includes(j.remote));
  if (filters.locations.length) {
    result = result.filter(j => filters.locations.some(location => locationMatches(j.location, location)));
  }
  // Source dropdown/settings can carry source ids while each job's `source` is
  // a display label (e.g. "LinkedIn"); compare case-insensitively.
  const sourceFilters = filters.sources.length ? filters.sources : filters.source ? [filters.source] : [];
  if (sourceFilters.length) {
    const wants = sourceFilters.map(source => source.toLowerCase());
    result = result.filter(j => wants.includes((j.source ?? '').toLowerCase()));
  }
  if (filters.posted) {
    const days = parseInt(filters.posted);
    const cutoff = Date.now() - days * 86400000;
    result = result.filter(j => j.posted_at && new Date(j.posted_at).getTime() >= cutoff);
  }
  if (filters.cv === 'created') {
    result = result.filter(j => j.resume_status === 'done' && !!j.pdf_url);
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
  sorted.sort(sortFns[filters.sort] ?? sortFns.posted);
  return sorted;
}
