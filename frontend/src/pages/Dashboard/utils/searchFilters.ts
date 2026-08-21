import { WORK_STYLES, type SearchRowEntry } from '../../../components/ui/searchRowModel';
import { DEFAULT_FILTERS, type Filters } from '../../../utils/filters';

export function normalizeFilters(value?: Partial<Filters> | null): Filters {
  return {
    ...DEFAULT_FILTERS,
    ...value,
    remote: Array.isArray(value?.remote) ? value.remote : DEFAULT_FILTERS.remote,
    sources: Array.isArray(value?.sources) ? value.sources : DEFAULT_FILTERS.sources,
    locations: Array.isArray(value?.locations) ? value.locations : DEFAULT_FILTERS.locations,
  };
}

function sameFilterValue(a: string, b: string) {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

function addUniqueFilterValue(list: string[], raw: string) {
  const next = raw.trim();
  if (!next || list.some(item => sameFilterValue(item, next))) return list;
  return [...list, next];
}

function resolveSourceValue(source: string, options: string[]) {
  return options.find(option => sameFilterValue(option, source)) ?? source;
}

export function deriveFiltersFromSearchRows(rows: SearchRowEntry[], current: Filters, sourceOptions: string[]): Filters {
  const selectedWorkStyles = WORK_STYLES.filter(style => rows.some(row => row.workStyles.includes(style)));
  const remote = selectedWorkStyles.length === WORK_STYLES.length ? [] : selectedWorkStyles;
  const sources = rows.reduce<string[]>((list, row) => {
    let next = list;
    for (const source of row.sources) next = addUniqueFilterValue(next, source);
    return next;
  }, []);
  const locations = rows.reduce<string[]>((list, row) => {
    let next = list;
    for (const location of row.locations) next = addUniqueFilterValue(next, location);
    return next;
  }, []);

  return {
    ...current,
    remote,
    source: sources.length === 1 ? resolveSourceValue(sources[0], sourceOptions) : '',
    sources: sources.length > 1 ? sources.map(source => resolveSourceValue(source, sourceOptions)) : [],
    locations,
  };
}

export function searchLabel(f: Filters) {
  const sourceLabel = f.source || f.sources.join('+');
  return [f.search, sourceLabel, f.locations.join('+'), f.remote.join('+'), f.posted ? `${f.posted}d` : '', f.cv === 'created' ? 'CV ready' : '']
    .filter(Boolean)
    .join(' · ') || 'Search';
}
