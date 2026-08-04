import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link, useLocation, useNavigate } from 'react-router-dom';
import { jobs as jobsApi, documents } from '../../api/client';
import { useToast } from '../../components/ui/Toast';
import { useDocumentStatus } from '../../hooks/useDocumentStatus';
import { Icon } from '../../components/ui/Icon';
import { Spinner } from '../../components/ui/Spinner';
import { AppShell } from '../../components/layout/AppShell';
import { BackButton } from '../../components/layout/BackButton';
import { safeUrl, fmtDate } from '../../utils/format';
import { formatDescription, isLongDescription } from '../../utils/descriptionRenderer';
import { buildBackState } from '../../utils/backNavigation';
import type { JobDetail, Job } from '../../api/types';

// ── Job description with show-more ────────────────────────────────────────────

function JobDescription({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = isLongDescription(text);
  const html = formatDescription(text);
  return (
    <div>
      <div
        className={`description-body${long && !expanded ? ' desc-clamped' : ''}`}
        dangerouslySetInnerHTML={{ __html: html }}
      />
      {long && (
        <button className="desc-toggle" type="button" onClick={() => setExpanded(e => !e)}>
          {expanded ? 'Show less ▴' : 'Show more ▾'}
        </button>
      )}
    </div>
  );
}

// ── Document slot (resume / cover letter) ─────────────────────────────────────

function DocSlot({ jobId, type, job, onRefresh }: {
  jobId: string; type: 'resume' | 'cover-letter'; job: JobDetail; onRefresh: () => void;
}) {
  const { showToast } = useToast();
  const isResume = type === 'resume';
  const status = isResume ? job.resume_status : job.cl_status;
  const stage = isResume ? job.resume_stage : job.cl_stage;
  const pdfUrl = isResume ? job.pdf_url : job.cl_pdf_url;
  const err = isResume ? job.resume_error : job.cl_error;

  const [building, setBuilding] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const docStatus = useDocumentStatus(jobId, type, building || status === 'building');
  const location = useLocation();
  const backState = buildBackState(location);

  useEffect(() => {
    if (docStatus.status === 'done' || docStatus.status === 'error') {
      setBuilding(false);
      onRefresh();
    }
  }, [docStatus.status, onRefresh]);

  const handleBuild = async () => {
    if (submitting || building) return;   // guard against duplicate submission
    setSubmitting(true);
    try {
      if (isResume) await documents.buildResume(jobId);
      else await documents.buildCoverLetter(jobId);
      setBuilding(true);
    } catch {
      showToast('Failed to start build', 'err');
    } finally {
      setSubmitting(false);
    }
  };

  const effectiveStatus = building ? docStatus.status || status : status;
  const effectiveStage = building ? docStatus.stage || stage : stage;
  const effectivePdfUrl = building ? docStatus.pdfUrl || pdfUrl : pdfUrl;
  const rateLimit = docStatus.rateLimit;

  // While a build is in flight (POST sent, or backend reports building) show the
  // building state immediately so the user gets feedback and can't re-submit.
  if (effectiveStatus === 'building' || (building && effectiveStatus !== 'error' && effectiveStatus !== 'done')) {
    return (
      <div className="doc-building">
        <Spinner className={isResume ? 'spinner-resume' : 'spinner-cl'} />
        {effectiveStage || 'Building…'}
      </div>
    );
  }
  if (effectiveStatus === 'done' && effectivePdfUrl) {
    return (
      <>
        <a href={safeUrl(effectivePdfUrl)} target="_blank" rel="noreferrer" className="btn btn-success btn-sm">
          {isResume ? '📄 Open CV' : '✉ Open Letter'}
        </a>
        <button className="btn btn-ghost btn-sm" onClick={handleBuild}>Rebuild</button>
      </>
    );
  }
  if (effectiveStatus === 'error') {
    if (rateLimit) {
      const provider = rateLimit.provider ? rateLimit.provider.charAt(0).toUpperCase() + rateLimit.provider.slice(1) : 'Provider';
      const scope = rateLimit.scope === 'TPD' ? 'daily' : rateLimit.scope === 'TPM' ? 'per-minute' : '';
      const retry = rateLimit.retry_seconds && rateLimit.retry_seconds > 0
        ? (rateLimit.retry_seconds < 90 ? `~${rateLimit.retry_seconds}s` : `~${Math.round(rateLimit.retry_seconds / 60)} min`)
        : '';
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '100%' }}>
          <div className="doc-error-msg">
            ⚠ {provider} {scope} limit reached
            {typeof rateLimit.used === 'number' && typeof rateLimit.limit === 'number' && ` — ${rateLimit.used} / ${rateLimit.limit} tokens`}
            {retry && ` · resets in ${retry}`}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <Link to="/ai-settings" state={backState} className="btn btn-ghost btn-sm">Switch provider</Link>
            <button className="btn btn-ghost btn-sm" onClick={handleBuild}>Retry</button>
          </div>
        </div>
      );
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '100%' }}>
        <div className="doc-error-msg">{err ? err.slice(0, 80) : 'Build failed'}</div>
        <button className="btn btn-ghost btn-sm" onClick={handleBuild}>Retry</button>
      </div>
    );
  }
  // idle
  if (!isResume && job.resume_status !== 'done') {
    return <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-faint)' }}>🔒 Build CV first</span>;
  }
  return (
    <button
      className="btn btn-sm"
      style={isResume
        ? { background: '#2e1f6e', color: '#c4b5fd', border: '1px solid #4c2ea8' }
        : { background: '#0c2d42', color: '#7dd3fc', border: '1px solid #0e4a72' }}
      onClick={handleBuild}
    >
      {isResume ? '▶ Build CV' : '✉ Write Cover Letter'}
    </button>
  );
}

// ── Sidebar cards ─────────────────────────────────────────────────────────────

function SidebarCard({ title, id, children }: { title: string; id?: string; children: React.ReactNode }) {
  return (
    <div className="sidebar-card">
      <div className="sidebar-card-header"><h3>{title}</h3></div>
      <div className="sidebar-card-body" id={id}>{children}</div>
    </div>
  );
}

function SkillsCard({ job }: { job: JobDetail }) {
  const m = job.match;
  if (!m || (!m.matched?.length && !m.missing?.length && typeof m.semantic_score !== 'number')) return null;
  const total = (m.matched?.length ?? 0) + (m.missing?.length ?? 0);
  return (
    <SidebarCard title="Skills Match">
      {typeof m.semantic_score === 'number' && (
        <div className="skills-fit" title="Overall semantic similarity between this job and your profile">
          Overall fit: {m.semantic_score}%
        </div>
      )}
      <div className="skills-summary">{m.matched?.length ?? 0} of {total} required skills match</div>
      {!!m.matched?.length && (
        <>
          <div className="skills-group-label">✓ Your matching skills</div>
          <div className="skills-wrap">{m.matched.map(s => <span key={s} className="skill-tag">{s}</span>)}</div>
        </>
      )}
      {!!m.missing?.length && (
        <>
          <div className="skills-group-label">Not in your profile</div>
          <div className="skills-wrap">{m.missing.map(s => <span key={s} className="skill-tag-missing">{s}</span>)}</div>
          <div className="skills-gap-hint">Add any you actually have to your profile so future matches count them.</div>
        </>
      )}
    </SidebarCard>
  );
}

function DetailsCard({ job }: { job: JobDetail }) {
  const rows = [
    job.salary_range    && { label: 'Salary',     value: job.salary_range },
    job.employment_type && { label: 'Employment', value: job.employment_type },
    job.company         && { label: 'Company',    value: job.company },
    job.location        && { label: 'Location',   value: job.location },
    job.remote && job.remote !== 'Unknown' && { label: 'Work type', value: job.remote },
    job.experience      && { label: 'Experience', value: job.experience },
    job.source          && { label: 'Source',     value: job.source },
  ].filter(Boolean) as { label: string; value: string }[];

  return (
    <SidebarCard title="Details">
      {rows.map(r => (
        <div key={r.label} className="detail-row">
          <span className="detail-row-label">{r.label}</span>
          <span className="detail-row-value">{r.value}</span>
        </div>
      ))}
    </SidebarCard>
  );
}

function TimelineCard({ job }: { job: JobDetail }) {
  const statusColors: Record<string, string> = { applied: 'green', skipped: 'red', pending: 'active' };
  const statusLabels: Record<string, string> = { applied: '✓ Applied', skipped: '✗ Skipped', pending: 'Pending review' };
  const items = [
    job.posted_at     && { dot: '',       label: 'Posted by employer',  date: fmtDate(job.posted_at), icon: 'clock' as const },
    job.first_seen_at && { dot: 'active', label: 'Found by scraper',    date: fmtDate(job.first_seen_at), icon: 'search' as const },
    job.status !== 'pending' && { dot: statusColors[job.status] || 'active', label: statusLabels[job.status] || job.status, date: '' },
  ].filter(Boolean) as { dot: string; label: string; date: string; icon?: 'clock' | 'search' }[];

  return (
    <SidebarCard title="Timeline">
      <div className="timeline">
        {items.map((item, i) => (
          <div key={i} className="timeline-item">
            <div className={`timeline-dot ${item.dot}`} />
            <div>
              <div className="timeline-label timeline-label-with-icon">
                {item.icon && <Icon name={item.icon} size={13} />}
                <span>{item.label}</span>
              </div>
              {item.date && <div className="timeline-date">{item.date}</div>}
            </div>
          </div>
        ))}
      </div>
    </SidebarCard>
  );
}

// ── Similar jobs ──────────────────────────────────────────────────────────────

function SimilarJobs({ jobId }: { jobId: string }) {
  const [similar, setSimilar] = useState<Job[]>([]);
  const navigate = useNavigate();
  const sliderRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    jobsApi.similar(jobId).then(setSimilar);
  }, [jobId]);

  if (!similar.length) return null;

  const scroll = (dir: 'left' | 'right') => {
    if (!sliderRef.current) return;
    sliderRef.current.scrollBy({ left: dir === 'right' ? 260 : -260, behavior: 'smooth' });
  };

  return (
    <div className="similar-section">
      <div className="similar-head">
        <h2 className="similar-heading">Similar jobs</h2>
        <div className="similar-nav">
          <button className="similar-arrow" onClick={() => scroll('left')} aria-label="Scroll left">‹</button>
          <button className="similar-arrow" onClick={() => scroll('right')} aria-label="Scroll right">›</button>
        </div>
      </div>
      <div className="similar-slider" ref={sliderRef}>
        {similar.map((j, i) => (
          <a
            key={j.job_id}
            className="similar-card-item"
            href="#"
            style={{ animationDelay: `${i * 60}ms` }}
            onClick={e => { e.preventDefault(); navigate(`/job/${j.job_id}`); }}
          >
            <div className="similar-title">{j.title}</div>
            <div className="similar-company">{j.company}</div>
            {j.location && <div className="similar-location">{j.location}</div>}
            {j.match && typeof j.match.semantic_score === 'number' && (
              <span className={`similar-match ${j.match.semantic_score >= 70 ? 'high' : j.match.semantic_score >= 45 ? 'mid' : 'low'}`}>
                {j.match.semantic_score}% fit
              </span>
            )}
          </a>
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const loadJob = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await jobsApi.get(jobId);
      setJob(data);
    } catch {
      showToast('Failed to load job', 'err');
    }
  }, [jobId, showToast]);

  useEffect(() => {
    setLoading(true);
    loadJob().finally(() => setLoading(false));
  }, [loadJob]);

  const setStatus = async (status: 'applied' | 'skipped' | 'pending') => {
    if (!jobId) return;
    try {
      await jobsApi.setStatus(jobId, status);
      await loadJob();
      showToast(status === 'applied' ? 'Marked as applied' : status === 'skipped' ? 'Skipped' : 'Restored to pending');
    } catch {
      showToast('Could not update job status — please try again', 'err');
    }
  };

  if (loading) return (
    <AppShell>
      <div className="detail-loading">
        <BackButton fallbackTo="/" className="detail-back" />
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><Spinner /></div>
      </div>
    </AppShell>
  );

  if (!job) return (
    <AppShell>
      <div className="detail-loading">
        <BackButton fallbackTo="/" className="detail-back" />
        <p style={{ padding: '2rem', color: 'var(--text-muted)' }}>Job not found.</p>
      </div>
    </AppShell>
  );

  const remoteCss: Record<string, string> = { Remote: 'remote', Hybrid: 'hybrid', 'On-site': 'onsite', 'On-Site': 'onsite' };

  return (
    <AppShell>
      <div className="detail-header">
        <BackButton fallbackTo="/" className="detail-back" />
        <span className="detail-header-title">{job.title}</span>
      </div>

      <div className="detail-layout">
        <main className="detail-main" id="main-content">
          {/* Hero */}
          <div className="job-hero">
            <h1 className="job-hero-title">
              {job.url ? (
                <a href={safeUrl(job.url)} target="_blank" rel="noreferrer" className="job-hero-title-link">
                  {job.title}
                </a>
              ) : job.title}
            </h1>
            <div className="job-hero-company">{job.company}</div>
            <div className="job-hero-meta">
              {job.location && <span className="meta-pill"><Icon name="mapPin" size={13} /> {job.location}</span>}
              {job.remote && job.remote !== 'Unknown' && (
                <span className={`meta-pill remote-pill ${remoteCss[job.remote] || ''}`}>
                  <Icon name="globe" size={13} /> {job.remote}
                </span>
              )}
              {job.source && <span className="meta-pill source-badge"><Icon name="external" size={13} /> {job.source}</span>}
              {job.posted && <span className="meta-pill"><Icon name="clock" size={13} /> {job.posted}</span>}
            </div>
            <div className="job-hero-actions">
              {job.status === 'pending' ? (
                <>
                  <button className="btn btn-success" onClick={() => setStatus('applied')}><Icon name="check" size={15} /> Mark as Applied</button>
                  <button className="btn btn-ghost" onClick={() => setStatus('skipped')}><Icon name="x" size={15} /> Skip</button>
                </>
              ) : (
                <>
                  <span className={`status-pill ${job.status}`}>
                    {job.status === 'applied' ? 'Applied' : 'Skipped'}
                  </span>
                  <button className="btn btn-ghost btn-sm" onClick={() => setStatus('pending')}>↩ Restore to pending</button>
                </>
              )}
            </div>
          </div>

          {/* Description */}
          <div className="job-description" id="description-content">
            {job.description
              ? <JobDescription text={job.description} />
              : <p className="description-empty">No description available.</p>
            }
          </div>

          <SimilarJobs jobId={job.job_id} />
        </main>

        <aside className="detail-sidebar">
          {/* Documents */}
          <SidebarCard title="Documents" id="docs-card-body">
            <div className="doc-row">
              <span className="doc-row-label">CV / Resume</span>
              <div className="doc-row-content">
                <DocSlot jobId={job.job_id} type="resume" job={job} onRefresh={loadJob} />
              </div>
            </div>
            <div className="doc-row">
              <span className="doc-row-label">Cover Letter</span>
              <div className="doc-row-content">
                <DocSlot jobId={job.job_id} type="cover-letter" job={job} onRefresh={loadJob} />
              </div>
            </div>
          </SidebarCard>

          <SkillsCard job={job} />
          <DetailsCard job={job} />
          <TimelineCard job={job} />
        </aside>
      </div>
    </AppShell>
  );
}
