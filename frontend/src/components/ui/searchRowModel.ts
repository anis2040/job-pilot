import type { SearchEntry } from '../../api/types';

export interface SearchRowEntry {
  query: string;
  locations: string[];
  remote: boolean;
  sources: string[];
}

export function sameLocation(a: string, b: string) {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

export function addUniqueLocation(list: string[], raw: string) {
  const next = raw.trim().replace(/,$/, '');
  if (!next || list.some(item => sameLocation(item, next))) return list;
  return [...list, next];
}

export function groupSearchEntries(entries: SearchEntry[]): SearchRowEntry[] {
  const groups: Record<string, SearchRowEntry> = {};
  for (const e of entries) {
    const key = `${e.query}||${e.remote ?? true}`;
    if (!groups[key]) groups[key] = { query: e.query, locations: [], remote: e.remote !== false, sources: [] };
    if (!groups[key].sources.includes(e.source)) groups[key].sources.push(e.source);
    groups[key].locations = addUniqueLocation(groups[key].locations, e.location || 'United States');
  }
  return Object.values(groups);
}

export function expandSearchRows(rows: SearchRowEntry[]): SearchEntry[] {
  const result: SearchEntry[] = [];
  for (const row of rows) {
    if (!row.query || !row.sources.length || !row.locations.length) continue;
    for (const location of row.locations) {
      for (const src of row.sources) {
        result.push({ name: `${src} - ${row.query}`, source: src, query: row.query, location, max_pages: 3, remote: row.remote });
      }
    }
  }
  return result;
}
