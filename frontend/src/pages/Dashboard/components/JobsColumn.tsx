import type { Job } from '../../../api/types';
import type { Tab } from '../types';
import { PAGE_SIZE } from '../constants';
import { JobRow } from './JobRow';
import { Pagination } from '../../../components/ui/Pagination';

interface JobsColumnProps {
  loading: boolean;
  loadError: boolean;
  tab: Tab;
  hasFilters: boolean;
  fetchRunning: boolean;
  jobs: Job[];
  totalFiltered: number;
  page: number;
  selectedJobId: string | null;
  onRetry: () => void;
  onFetch: () => void;
  onClearFilters: () => void;
  onPageChange: (page: number) => void;
  onJobClick: (jobId: string) => void;
  onStatusChange: (jobId: string, status: string) => void;
}

export function JobsColumn({
  loading,
  loadError,
  tab,
  hasFilters,
  fetchRunning,
  jobs,
  totalFiltered,
  page,
  selectedJobId,
  onRetry,
  onFetch,
  onClearFilters,
  onPageChange,
  onJobClick,
  onStatusChange,
}: JobsColumnProps) {
  if (loading) {
    return (
      <div className="jobs-skeleton">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="skel-row">
            <div className="skel-line skel-title skeleton" />
            <div className="skel-line skel-company skeleton" />
            <div className="skel-line skel-meta skeleton" />
          </div>
        ))}
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="empty-state" role="alert">
        <div className="empty-state-icon">⚠️</div>
        <div className="empty-state-title">Couldn't load jobs</div>
        <div className="empty-state-desc">Something went wrong reaching the server.</div>
        <button className="btn btn-primary" style={{ marginTop: 'var(--space-2)' }} onClick={onRetry}>
          Retry
        </button>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">{hasFilters ? '🔍' : '📭'}</div>
        <div className="empty-state-title">{hasFilters ? 'No jobs match your filters' : `No ${tab} jobs`}</div>
        <div className="empty-state-desc">
          {hasFilters ? 'Try clearing your filters.' : tab === 'pending' ? 'Click "Fetch Jobs" to pull the latest listings.' : ''}
        </div>
        {!hasFilters && tab === 'pending' && (
          <button className="btn btn-primary" style={{ marginTop: 'var(--space-2)' }} onClick={onFetch} disabled={fetchRunning}>
            Fetch jobs now
          </button>
        )}
        {hasFilters && <button className="btn btn-ghost" style={{ marginTop: 'var(--space-2)' }} onClick={onClearFilters}>Clear filters</button>}
      </div>
    );
  }

  return (
    <>
      <div className="jobs-list">
        {jobs.map(job => (
          <JobRow
            key={job.job_id}
            job={job}
            selected={selectedJobId === job.job_id}
            onClick={() => onJobClick(job.job_id)}
            onStatusChange={onStatusChange}
          />
        ))}
      </div>
      <Pagination page={page} total={totalFiltered} pageSize={PAGE_SIZE} onChange={onPageChange} />
    </>
  );
}
