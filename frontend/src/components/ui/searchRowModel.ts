import type { SearchEntry } from '../../api/types';

export type WorkStyle = 'Remote' | 'Hybrid' | 'On-site';

export const WORK_STYLES: WorkStyle[] = ['Remote', 'Hybrid', 'On-site'];

export interface SearchRowEntry {
  id?: string;
  titles: string[];
  locations: string[];
  workStyles: WorkStyle[];
  sources: string[];
}

export function createSearchRow(sources: string[] = []): SearchRowEntry {
  return {
    titles: [],
    locations: ['United States'],
    workStyles: ['Remote', 'Hybrid'],
    sources: [...sources],
  };
}

function normalizeKey(value: string) {
  return value.trim().toLowerCase();
}

function addUniqueValue(list: string[], raw: string) {
  const next = raw.trim().replace(/,$/, '');
  if (!next || list.some(item => normalizeKey(item) === normalizeKey(next))) return list;
  return [...list, next];
}

function normalizeWorkStyles(styles: unknown, remote?: boolean): WorkStyle[] {
  if (Array.isArray(styles)) {
    const valid = styles.filter((style): style is WorkStyle => WORK_STYLES.includes(style as WorkStyle));
    if (valid.length) return Array.from(new Set(valid));
  }

  return remote === false ? ['Hybrid', 'On-site'] : ['Remote', 'Hybrid'];
}

function workStyleKey(styles: WorkStyle[]) {
  return WORK_STYLES.filter(style => styles.includes(style)).join('|');
}

export function sameLocation(a: string, b: string) {
  return normalizeKey(a) === normalizeKey(b);
}

export function addUniqueLocation(list: string[], raw: string) {
  return addUniqueValue(list, raw);
}

export function addUniqueTitle(list: string[], raw: string) {
  return addUniqueValue(list, raw);
}

export function deriveTitleFilters(rows: SearchRowEntry[]) {
  return rows.reduce<string[]>((titles, row) => {
    for (const title of row.titles) {
      const next = title.trim().toLowerCase();
      if (next && !titles.includes(next)) titles.push(next);
    }
    return titles;
  }, []);
}

export function groupSearchEntries(entries: SearchEntry[]): SearchRowEntry[] {
  const groups: Record<string, SearchRowEntry> = {};
  for (const e of entries) {
    const workStyles = normalizeWorkStyles(e.work_styles, e.remote);
    const location = (e.location || 'United States').trim();
    // Key on semantic content (query + location + work styles) so that entries
    // sharing the same search intent but different sources are merged into one
    // row — regardless of what group_id was saved. This also self-heals configs
    // where every entry got a unique group_id (the old bug).
    const key = `${e.query.trim().toLowerCase()}||${location.toLowerCase()}||${workStyleKey(workStyles)}`;
    if (!groups[key]) groups[key] = { id: e.group_id, titles: [], locations: [], workStyles, sources: [] };
    groups[key].titles = addUniqueTitle(groups[key].titles, e.query);
    if (!groups[key].sources.includes(e.source)) groups[key].sources.push(e.source);
    groups[key].locations = addUniqueLocation(groups[key].locations, location);
    for (const style of workStyles) {
      if (!groups[key].workStyles.includes(style)) groups[key].workStyles.push(style);
    }
  }
  return Object.values(groups);
}

export function expandSearchRows(rows: SearchRowEntry[]): SearchEntry[] {
  const result: SearchEntry[] = [];
  rows.forEach((row, rowIndex) => {
    const titles = row.titles.map(title => title.trim()).filter(Boolean);
    const workStyles = normalizeWorkStyles(row.workStyles, true);
    const remote = workStyles.includes('Remote') && !workStyles.includes('On-site');
    const groupId = row.id || `search-${rowIndex + 1}`;
    if (!titles.length || !row.sources.length || !row.locations.length) return;
    for (const title of titles) {
      for (const location of row.locations) {
        for (const src of row.sources) {
          result.push({
            group_id: groupId,
            name: `${src} - ${title}`,
            source: src,
            query: title,
            location,
            max_pages: 3,
            remote,
            work_styles: workStyles,
          });
        }
      }
    }
  });
  return result;
}
