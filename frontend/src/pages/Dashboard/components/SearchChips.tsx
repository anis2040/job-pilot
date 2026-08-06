import type { Filters } from '../../../utils/filters';

interface SearchChipsProps {
  savedSearches: Filters[];
  recentSearches: Filters[];
  searchLabel: (f: Filters) => string;
  onApply: (f: Filters) => void;
  onRemoveSaved: (f: Filters) => void;
}

export function SearchChips({ savedSearches, recentSearches, searchLabel, onApply, onRemoveSaved }: SearchChipsProps) {
  return (
    <div className="search-chips">
      {savedSearches.length > 0 && savedSearches.map((s, i) => (
        <button key={i} className="search-chip saved" onClick={() => onApply(s)}>
          <span className="search-chip-icon">★</span>
          {searchLabel(s)}
          <span className="chip-x" onClick={e => { e.stopPropagation(); onRemoveSaved(s); }}>✕</span>
        </button>
      ))}
      {recentSearches.length > 0 && (
        <span className="search-chips-divider" />
      )}
      {recentSearches.length > 0 && recentSearches.map((s, i) => (
        <button key={i} className="search-chip recent" onClick={() => onApply(s)}>
          <span className="search-chip-icon">↺</span>
          {searchLabel(s)}
        </button>
      ))}
    </div>
  );
}
