import type { Filters } from '../../../utils/filters';

interface FilterBarProps {
  filters: Filters;
  sourceOptions: string[];
  resultCount: number;
  isSaved: boolean;
  hasFilters: boolean;
  onToggleRemote: (value: string) => void;
  onFilterChange: (key: keyof Filters, value: string) => void;
  onFilterCapture: (filters: Filters) => void;
  onSaveSearch: () => void;
  onClearFilters: () => void;
}

export function FilterBar({
  filters,
  sourceOptions,
  resultCount,
  isSaved,
  hasFilters,
  onToggleRemote,
  onFilterChange,
  onFilterCapture,
  onSaveSearch,
  onClearFilters,
}: FilterBarProps) {
  return (
    <div className="filter-bar">
      <div className="filter-group">
        <span className="filter-label">Work type</span>
        {[{ val: 'Remote' }, { val: 'Hybrid' }, { val: 'On-site' }].map(({ val }) => (
          <button key={val}
            className={`filter-chip remote-${val.toLowerCase()}${filters.remote.includes(val) ? ' active' : ''}`}
            aria-pressed={filters.remote.includes(val)}
            onClick={() => onToggleRemote(val)}>
            {val}
          </button>
        ))}
      </div>
      <div className="filter-divider" />
      <div className="filter-group">
        <span className="filter-label">Source</span>
        <select className="filter-select" value={filters.source} aria-label="Filter by source"
          onChange={e => { onFilterChange('source', e.target.value); onFilterCapture({ ...filters, source: e.target.value, sources: [] }); }}>
          <option value="">All sources</option>
          {sourceOptions.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div className="filter-divider" />
      <div className="filter-group">
        <span className="filter-label">Posted</span>
        <select className="filter-select" value={filters.posted} aria-label="Filter by posting date"
          onChange={e => { onFilterChange('posted', e.target.value); onFilterCapture({ ...filters, posted: e.target.value }); }}>
          <option value="">Any time</option>
          <option value="1">Past 24 hours</option>
          <option value="7">Past week</option>
          <option value="30">Past month</option>
        </select>
      </div>
      <div className="filter-divider" />
      <div className="filter-group">
        <span className="filter-label">CV</span>
        <select className="filter-select" value={filters.cv} aria-label="Filter by CV status"
          onChange={e => { onFilterChange('cv', e.target.value); onFilterCapture({ ...filters, cv: e.target.value }); }}>
          <option value="">All jobs</option>
          <option value="created">CV created</option>
        </select>
      </div>
      <div className="filter-divider" />
      <div className="filter-group">
        <span className="filter-label">Sort</span>
        <select className="filter-select" value={filters.sort} aria-label="Sort jobs"
          onChange={e => onFilterChange('sort', e.target.value)}>
          <option value="posted">Posted date</option>
          <option value="match">Best match</option>
          <option value="newest">Recently fetched</option>
          <option value="oldest">Oldest fetched</option>
          <option value="title">Title A–Z</option>
          <option value="company">Company A–Z</option>
        </select>
      </div>
      <div className="filter-spacer" />
      <span className="filter-results" data-testid="filter-result-count">{resultCount} jobs</span>
      <button
        className={`filter-save${isSaved ? ' is-saved' : ''}`}
        onClick={onSaveSearch}
        disabled={!hasFilters}
        aria-label={isSaved ? 'Search saved' : 'Save this search'}
        aria-pressed={isSaved}
        title={!hasFilters ? 'Set a filter to save this search' : isSaved ? 'Remove saved search' : 'Save this search'}
      >
        {isSaved ? '★' : '☆'} Save
      </button>
      {hasFilters && <button className="filter-clear" onClick={onClearFilters} aria-label="Clear filters">Clear</button>}
    </div>
  );
}
