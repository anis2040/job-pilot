import { Icon } from '../../../components/ui/Icon';
import type { Tab } from '../types';

interface SearchBarRowProps {
  tab: Tab;
  counts: Record<Tab, number>;
  search: string;
  fetchRunning: boolean;
  fetchMessage: string;
  onTabChange: (tab: Tab) => void;
  onSearchChange: (value: string) => void;
  onSearchBlur: () => void;
  onFetch: () => void;
  onOpenSettings: () => void;
}

export function SearchBarRow({
  tab,
  counts,
  search,
  fetchRunning,
  fetchMessage,
  onTabChange,
  onSearchChange,
  onSearchBlur,
  onFetch,
  onOpenSettings,
}: SearchBarRowProps) {
  return (
    <div className="search-bar-row">
      <div className="tab-pill-group">
        {(['pending', 'applied', 'skipped'] as Tab[]).map(t => (
          <button key={t} className={`tab-pill${tab === t ? ' active' : ''}`}
            onClick={() => onTabChange(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
            <span className="tab-pill-count">{counts[t]}</span>
          </button>
        ))}
      </div>

      <div className="search-bar-wrap">
        <Icon name="search" size={15} className="search-bar-icon" />
        <input
          type="text"
          className="search-bar-input"
          placeholder="Search by title, company, location or source…"
          value={search}
          aria-label="Search jobs"
          onChange={e => onSearchChange(e.target.value)}
          onBlur={onSearchBlur}
        />
        {search && (
          <button className="search-bar-clear" onClick={() => onSearchChange('')} aria-label="Clear search">
            <Icon name="x" size={13} />
          </button>
        )}
      </div>

      {fetchMessage && (
        <span className="fetch-progress-msg">
          {fetchRunning && <span className="spinner spinner-fetch" style={{ marginRight: 6 }} />}
          {fetchMessage}
        </span>
      )}

      <button
        className={`search-action-btn search-action-fetch${fetchRunning ? ' fetching' : ''}`}
        onClick={onFetch}
        disabled={fetchRunning}
      >
        <Icon name="refresh" size={15} className={fetchRunning ? 'spin' : ''} />
        {fetchRunning ? 'Fetching…' : 'Fetch jobs'}
      </button>

      <button className="search-action-btn search-action-settings" onClick={onOpenSettings}>
        <Icon name="settings" size={15} /> Search settings
      </button>
    </div>
  );
}
