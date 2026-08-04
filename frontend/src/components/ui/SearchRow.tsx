import { useState } from 'react';
import { addUniqueLocation, addUniqueTitle, sameLocation, WORK_STYLES, type SearchRowEntry, type WorkStyle } from './searchRowModel';

// Compatibility for stale Vite HMR modules that imported model helpers here.
// eslint-disable-next-line react-refresh/only-export-components
export { groupSearchEntries, expandSearchRows } from './searchRowModel';
export type { SearchRowEntry } from './searchRowModel';

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

const WORK_STYLE_LABELS: Record<WorkStyle, string> = {
  Remote: 'Remote-first roles',
  Hybrid: 'Office and remote mix',
  'On-site': 'Office-based roles',
};

export function SearchRow({ entry, sources, onRemove, onChange }: SearchRowProps) {
  const [titleInput, setTitleInput] = useState('');
  const [customLocationInput, setCustomLocationInput] = useState('');

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

  const commitTitle = (raw = titleInput) => {
    const next = addUniqueTitle(entry.titles, raw);
    if (next !== entry.titles) onChange({ ...entry, titles: next });
    setTitleInput('');
  };

  const removeTitle = (title: string) => {
    const target = title.trim().toLowerCase();
    onChange({ ...entry, titles: entry.titles.filter(item => item.trim().toLowerCase() !== target) });
  };

  const commitLocation = (raw = customLocationInput) => {
    const next = addUniqueLocation(entry.locations, raw);
    if (next !== entry.locations) onChange({ ...entry, locations: next });
    setCustomLocationInput('');
  };

  const removeLocation = (location: string) => {
    onChange({ ...entry, locations: entry.locations.filter(item => !sameLocation(item, location)) });
  };

  const toggleWorkStyle = (style: WorkStyle) => {
    const selected = entry.workStyles.includes(style);
    const next = selected
      ? entry.workStyles.filter(item => item !== style)
      : [...entry.workStyles, style];
    if (!next.length) return;
    onChange({ ...entry, workStyles: next });
  };

  return (
    <div className="search-row">
      <div className="search-row-head">
        <div className="search-row-panel search-row-title-panel">
          <div className="search-row-label">Job titles</div>
          <input
            type="text"
            placeholder="Add a job title"
            value={titleInput}
            onChange={e => setTitleInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                commitTitle();
              }
            }}
            onBlur={() => { if (titleInput.trim()) commitTitle(); }}
          />
          <div className="search-title-tags">
            {entry.titles.map(title => (
              <button
                key={title}
                type="button"
                className="search-chip title-chip"
                onClick={() => removeTitle(title)}
                aria-label={`Remove ${title}`}
              >
                {title}
                <span aria-hidden="true">✕</span>
              </button>
            ))}
            {!entry.titles.length && <span className="search-row-hint">Add at least one title.</span>}
          </div>
        </div>
        <button className="btn-icon" type="button" title="Remove" onClick={onRemove}>✕</button>
      </div>

      <div className="search-row-grid">
        <div className="search-row-panel">
          <div className="search-row-label">Countries / locations</div>
          <div className="search-location-add">
            <select
              aria-label="Add country or location"
              value=""
              onChange={e => {
                if (e.target.value) commitLocation(e.target.value);
              }}
            >
              <option value="">Add country or location</option>
              {LOCATION_SUGGESTIONS.map(option => (
                <option key={option} value={option} disabled={entry.locations.some(location => sameLocation(location, option))}>
                  {option}
                </option>
              ))}
            </select>
            <input
              type="text"
              placeholder="Custom location"
              value={customLocationInput}
              onChange={e => setCustomLocationInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ',') {
                  e.preventDefault();
                  commitLocation();
                }
              }}
              onBlur={() => { if (customLocationInput.trim()) commitLocation(); }}
            />
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
          <div className="remote-choice-group" role="group" aria-label="Work style preferences">
            {WORK_STYLES.map(style => {
              const checked = entry.workStyles.includes(style);
              return (
                <button
                  key={style}
                  type="button"
                  className={`remote-choice${checked ? ' active' : ''}`}
                  aria-pressed={checked}
                  onClick={() => toggleWorkStyle(style)}
                >
                  <strong>{style}</strong>
                  <span>{WORK_STYLE_LABELS[style]}</span>
                </button>
              );
            })}
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
