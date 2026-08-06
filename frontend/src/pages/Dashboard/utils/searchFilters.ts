import { WORK_STYLES, type SearchRowEntry } from '../../../components/ui/searchRowModel';
import { DEFAULT_FILTERS, type Filters } from '../../../utils/filters';

export function normalizeFilters(value?: Partial<Filters> | null): Filters {
  return {
    ...DEFAULT_FILTERS,
    ...value,
    remote: Array.isArray(value?.remote) ? value.remote : DEFAULT_FILTERS.remote,
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
  const titles = rows.reduce<string[]>((list, row) => {
    let next = list;
    for (const title of row.titles) next = addUniqueFilterValue(next, title);
    return next;
  }, []);
  const remote = WORK_STYLES.filter(style => rows.some(row => row.workStyles.includes(style)));
  const sources = rows.reduce<string[]>((list, row) => {
    let next = list;
    for (const source of row.sources) next = addUniqueFilterValue(next, source);
    return next;
  }, []);

  return {
    ...current,
    search: titles.join(', '),
    remote,
    source: sources.length === 1 ? resolveSourceValue(sources[0], sourceOptions) : '',
  };
}

export function searchLabel(f: Filters) {
  return [f.search, f.source, f.remote.join('+'), f.posted ? `${f.posted}d` : '', f.cv === 'created' ? 'CV ready' : '']
    .filter(Boolean)
    .join(' · ') || 'Search';
}
