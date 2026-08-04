import { useId, useState } from 'react';
import type { SearchEntry } from '../../api/types';

export interface SearchRowEntry {
  query: string;
  locations: string[];
  remote: boolean;
  sources: string[];
}

interface SearchRowProps {
  entry: SearchRowEntry;
  sources: string[];
  onRemove: () => void;
  onChange: (updated: SearchRowEntry) => void;
}

const LOCATION_SUGGESTIONS = [
  'United States',
  'Germany',
  'United Kingdom',
  'Netherlands',
  'France',
  'Spain',
  'Portugal',
  'Switzerland',
  'Canada',
  'United Arab Emirates',
  'Saudi Arabia',
  'Tunisia',
  'Morocco',
  'Remote Europe',
];

function sameLocation(a: string, b: string) {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

function addUniqueLocation(list: string[], raw: string) {
  const next = raw.trim().replace(/,$/, '');
  if (!next || list.some(item => sameLocation(item, next))) return list;
  return [...list, next];
}

export function SearchRow({ entry, sources, onRemove, onChange }: SearchRowProps) {
  const [locationInput, setLocationInput] = useState('');
  const datalistId = useId();

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

  const commitLocation = (raw = locationInput) => {
    const next = addUniqueLocation(entry.locations, raw);
    if (next !== entry.locations) onChange({ ...entry, locations: next });
    setLocationInput('');
  };

  const removeLocation = (location: string) => {
    onChange({ ...entry, locations: entry.locations.filter(item => !sameLocation(item, location)) });
  };

  return (
    <div className="search-row">
      <div className="search-row-fields search-row-fields-top">
        <input
          type="text"
          placeholder="e.g. Product Manager"
          value={entry.query}
          onChange={e => onChange({ ...entry, query: e.target.value })}
        />
        <button className="btn-icon" type="button" title="Remove" onClick={onRemove}>✕</button>
      </div>

      <div className="search-row-grid">
        <div className="search-row-panel">
          <div className="search-row-label">Countries / locations</div>
          <div className="search-location-add">
            <input
              type="text"
              list={datalistId}
              placeholder="Add a country or location"
              value={locationInput}
              onChange={e => setLocationInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ',') {
                  e.preventDefault();
                  commitLocation();
                }
              }}
              onBlur={() => { if (locationInput.trim()) commitLocation(); }}
            />
            <datalist id={datalistId}>
              {LOCATION_SUGGESTIONS.map(option => <option key={option} value={option} />)}
            </datalist>
            <button className="btn btn-ghost btn-sm" type="button" onClick={() => commitLocation()} disabled={!locationInput.trim()}>
              Add
            </button>
          </div>
          <div className="search-location-tags">
            {entry.locations.map(location => (
              <button
                key={location}
                type="button"
                className="search-chip location-chip"
                onClick={() => removeLocation(location)}
                aria-label={`Remove ${location}`}
              >
                {location}
                <span aria-hidden="true">✕</span>
              </button>
            ))}
            {!entry.locations.length && <span className="search-row-hint">Add one or more countries per search.</span>}
          </div>
        </div>

        <div className="search-row-panel search-row-panel-compact">
          <div className="search-row-label">Work style</div>
          <div className="remote-choice-group" role="group" aria-label="Work style preference">
            <button
              type="button"
              className={`remote-choice${entry.remote ? ' active' : ''}`}
              aria-pressed={entry.remote}
              onClick={() => onChange({ ...entry, remote: true })}
            >
              <strong>Remote-friendly</strong>
              <span>Include remote-first results</span>
            </button>
            <button
              type="button"
              className={`remote-choice${!entry.remote ? ' active' : ''}`}
              aria-pressed={!entry.remote}
              onClick={() => onChange({ ...entry, remote: false })}
            >
              <strong>Location-based</strong>
              <span>Focus on local on-site or hybrid roles</span>
            </button>
          </div>
        </div>
      </div>

      <div className="search-row-panel search-row-panel-sources">
        <div className="search-sources-head">
          <span className="search-row-label">Sources</span>
          <button className="source-all-btn" type="button" onClick={toggleAll}>
            {sources.every(s => entry.sources.includes(s)) ? 'Clear all' : 'Select all'}
          </button>
        </div>
        <div className="search-sources">
          {sources.map(src => (
            <button
              key={src}
              type="button"
              className={`source-chip${entry.sources.includes(src) ? ' checked' : ''}`}
              aria-pressed={entry.sources.includes(src)}
              onClick={() => toggleSource(src)}
            >
              {src}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// Converts flat SearchEntry[] (one per source) to grouped rows
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

// Expands grouped rows back to flat SearchEntry[]
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
