import { Icon } from '../../../components/ui/Icon';
import { SourceBadge } from '../../../components/ui/SourceBadge';
import { safeUrl } from '../../../utils/format';
import type { Job } from '../../../api/types';
import { REMOTE_CSS } from '../../../constants/jobMeta';

interface JobRowProps {
  job: Job;
  selected: boolean;
  onClick: () => void;
  onStatusChange: (id: string, status: string) => void;
}

export function JobRow({ job, selected, onClick, onStatusChange }: JobRowProps) {
  const match = job.match;
  const skillCount = match?.matched_count ?? 0;
  const fitScore = match?.score_kind === 'fit' ? (match.semantic_score ?? match.score) : null;
  const badgeValue = fitScore ?? skillCount;
  const badgeCls = badgeValue >= 75 ? 'high' : badgeValue >= 45 ? 'mid' : 'low';
  const badgeLabel = fitScore != null ? `${fitScore}% fit` : `${skillCount} skills`;

  return (
    <div
      className={`job-row${selected ? ' selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-label={job.title}
      aria-pressed={selected}
      data-testid={`job-row-${job.job_id}`}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onClick(); }}
    >
      <div className="job-row-main">
        <div className="job-row-title">{job.title}</div>

        <div className="job-row-meta">
          <span className="job-row-company">{job.company}</span>
          {job.location && (
            <><span className="dot">·</span><span className="job-meta-item"><Icon name="mapPin" size={11} />{job.location}</span></>
          )}
          {job.remote && job.remote !== 'Unknown' && (
            <><span className="dot">·</span><span className={`remote-badge ${REMOTE_CSS[job.remote] || ''}`}>
              <Icon name={job.remote === 'Remote' ? 'globe' : 'building'} size={11} />{job.remote}
            </span></>
          )}
          {job.experience && job.experience !== 'Unknown' && (
            <><span className="dot">·</span><span className="exp-badge"><Icon name="briefcase" size={11} />{job.experience}</span></>
          )}
          <><span className="dot">·</span><span className="age-label"><Icon name="clock" size={11} />{job.posted || job.age}</span></>
        </div>
      </div>

      <div className="job-row-right" onClick={e => e.stopPropagation()}>
        <div className="job-row-score-row">
          {match && badgeValue > 0 && (
            <span className={`match-badge ${badgeCls}`}>{badgeLabel}</span>
          )}
          {job.source && <SourceBadge source={job.source} />}
        </div>

        <div className="job-row-actions">
          {job.status === 'pending' ? (
            <>
              <button className="btn-row-action apply" title="Mark applied" onClick={() => onStatusChange(job.job_id, 'applied')}><Icon name="check" size={12} /></button>
              <button className="btn-row-action skip" title="Skip" onClick={() => onStatusChange(job.job_id, 'skipped')}><Icon name="x" size={12} /></button>
            </>
          ) : (
            <button className="btn-row-action restore" title="Restore to pending" onClick={() => onStatusChange(job.job_id, 'pending')}>↩</button>
          )}
          {job.resume_status === 'building' && <span className="spinner spinner-xs" />}
          {job.resume_status === 'done' && job.pdf_url && (
            <a href={safeUrl(job.pdf_url)} target="_blank" rel="noreferrer" title="Open CV" className="doc-micro-badge cv" onClick={e => e.stopPropagation()}>CV</a>
          )}
          {job.cl_status === 'building' && <span className="spinner spinner-xs" />}
          {job.cl_status === 'done' && job.cl_pdf_url && (
            <a href={safeUrl(job.cl_pdf_url)} target="_blank" rel="noreferrer" title="Open cover letter" className="doc-micro-badge cl" onClick={e => e.stopPropagation()}>CL</a>
          )}
          {job.cl_status === 'done' && !job.cl_pdf_url && <span className="doc-micro-badge cl" title="Cover letter ready">CL</span>}
        </div>
      </div>
    </div>
  );
}
