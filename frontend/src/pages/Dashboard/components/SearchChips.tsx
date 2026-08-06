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
    <div className="search-chips" data-testid="search-chips" aria-label="Saved and recent searches">
      {savedSearches.length > 0 && savedSearches.map((s, i) => {
        const label = searchLabel(s);
        return (
          <div key={`saved-${i}`} className="search-chip saved">
            <button
              type="button"
              className="search-chip-apply"
              aria-label={`Apply saved search: ${label}`}
              onClick={() => onApply(s)}
            >
              <span className="search-chip-icon" aria-hidden="true">★</span>
              {label}
            </button>
            <button
              type="button"
              className="chip-x"
              aria-label={`Remove saved search: ${label}`}
              onClick={() => onRemoveSaved(s)}
            >
              ✕
            </button>
          </div>
        );
      })}
      {recentSearches.length > 0 && (
        <span className="search-chips-divider" aria-hidden="true" />
      )}
      {recentSearches.length > 0 && recentSearches.map((s, i) => {
        const label = searchLabel(s);
        return (
          <button
            key={`recent-${i}`}
            type="button"
            className="search-chip recent"
            aria-label={`Apply recent search: ${label}`}
            onClick={() => onApply(s)}
          >
            <span className="search-chip-icon" aria-hidden="true">↺</span>
            {label}
          </button>
        );
      })}
    </div>
  );
}
