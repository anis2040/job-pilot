import type { SearchEntry } from '../../api/types';

interface SearchRowProps {
  entry: { query: string; location: string; remote: boolean; sources: string[] };
  sources: string[];
  onRemove: () => void;
  onChange: (updated: { query: string; location: string; remote: boolean; sources: string[] }) => void;
}

export function SearchRow({ entry, sources, onRemove, onChange }: SearchRowProps) {
  const toggleSource = (src: string) => {
    const next = entry.sources.includes(src)
      ? entry.sources.filter(s => s !== src)
      : [...entry.sources, src];
    onChange({ ...entry, sources: next });
  };

  const toggleAll = () => {
    const allChecked = sources.every(s => entry.sources.includes(s));
    onChange({ ...entry, sources: allChecked ? [] : [...sources] });
  };

  return (
    <div className="search-row">
      <div className="search-row-fields">
        <input
          type="text"
          placeholder="e.g. Product Manager"
          value={entry.query}
          onChange={e => onChange({ ...entry, query: e.target.value })}
        />
        <input
          type="text"
          placeholder="United States"
          value={entry.location}
          onChange={e => onChange({ ...entry, location: e.target.value })}
        />
        <label className="toggle-remote">
          <input
            type="checkbox"
            checked={entry.remote}
            onChange={e => onChange({ ...entry, remote: e.target.checked })}
          /> Remote
        </label>
        <button className="btn-icon" title="Remove" onClick={onRemove}>✕</button>
      </div>
      <div className="search-sources">
        <span style={{ fontSize: '0.7rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', marginRight: 4 }}>Sources:</span>
        {sources.map(src => (
          <label
            key={src}
            className={`source-cb${entry.sources.includes(src) ? ' checked' : ''}`}
            onClick={() => toggleSource(src)}
          >
            <input
              type="checkbox"
              className="src-cb"
              value={src}
              checked={entry.sources.includes(src)}
              onChange={() => toggleSource(src)}
            /> {src}
          </label>
        ))}
        <button className="source-all-btn" type="button" onClick={toggleAll}>all/none</button>
      </div>
    </div>
  );
}

// Converts flat SearchEntry[] (one per source) to grouped rows
export function groupSearchEntries(entries: SearchEntry[]) {
  const groups: Record<string, { query: string; location: string; remote: boolean; sources: string[] }> = {};
  for (const e of entries) {
    const key = `${e.query}||${e.location || ''}||${e.remote ?? true}`;
    if (!groups[key]) groups[key] = { query: e.query, location: e.location || 'United States', remote: e.remote !== false, sources: [] };
    groups[key].sources.push(e.source);
  }
  return Object.values(groups);
}

// Expands grouped rows back to flat SearchEntry[]
export function expandSearchRows(rows: { query: string; location: string; remote: boolean; sources: string[] }[]): SearchEntry[] {
  const result: SearchEntry[] = [];
  for (const row of rows) {
    if (!row.query || !row.sources.length) continue;
    for (const src of row.sources) {
      result.push({ name: `${src} - ${row.query}`, source: src, query: row.query, location: row.location, max_pages: 3, remote: row.remote });
    }
  }
  return result;
}
