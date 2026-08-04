import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { jobs as jobsApi, documents, config as configApi, fetcher as fetcherApi, constants } from '../../api/client';
import { useProfile } from '../../hooks/useProfile';
import { consumeProfileFetchSignal } from '../../hooks/profileFetchSignal';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { useToast } from '../../components/ui/useToast';
import { AppShell } from '../../components/layout/AppShell';
import { Icon } from '../../components/ui/Icon';
import { TagInput } from '../../components/ui/TagInput';
import { useDocumentStatus } from '../../hooks/useDocumentStatus';
import { SearchRow } from '../../components/ui/SearchRow';
import { groupSearchEntries, expandSearchRows, type SearchRowEntry } from '../../components/ui/searchRowModel';
import { formatDescription, isLongDescription } from '../../utils/descriptionRenderer';
import { safeUrl } from '../../utils/format';
import { applyFilters, filtersToKey, DEFAULT_FILTERS } from '../../utils/filters';
import type { Filters } from '../../utils/filters';
import type { Job, JobDetail, SearchConfig, AppConstants } from '../../api/types';

const PAGE_SIZE = 25;
const SPLIT_MIN = 1200;
const LS_SAVED = 'jobpilot_saved_searches';
const LS_RECENT = 'jobpilot_recent_searches';
type PanelState = 'closed' | 'opening' | 'open';

function normalizeFilters(value?: Partial<Filters> | null): Filters {
  return {
    ...DEFAULT_FILTERS,
    ...value,
    remote: Array.isArray(value?.remote) ? value.remote : DEFAULT_FILTERS.remote,
  };
}

// ── useWindowWidth ────────────────────────────────────────────────────────────

function useIsWide() {
  const [wide, setWide] = useState(() => window.innerWidth >= SPLIT_MIN);
  useEffect(() => {
    const handler = () => setWide(window.innerWidth >= SPLIT_MIN);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return wide;
}

// ── Job row ───────────────────────────────────────────────────────────────────

const REMOTE_CSS: Record<string, string> = { Remote: 'remote', Hybrid: 'hybrid', 'On-site': 'onsite', 'On-Site': 'onsite' };

function JobRow({ job, selected, onClick, onStatusChange }: {
  job: Job; selected: boolean; onClick: () => void;
  onStatusChange: (id: string, status: string) => void;
}) {
  const match = job.match;
  const matchPct = match
    ? (typeof match.semantic_score === 'number' ? match.semantic_score : null)
    : null;
  const skillCount = match?.matched_count ?? 0;
  const badgeCls = matchPct !== null
    ? (matchPct >= 70 ? 'high' : matchPct >= 45 ? 'mid' : 'low')
    : (skillCount >= 5 ? 'high' : skillCount >= 3 ? 'mid' : 'low');
  const badgeLabel = matchPct !== null
    ? `${matchPct}% fit`
    : skillCount > 0 ? `${skillCount} skill${skillCount !== 1 ? 's' : ''} match` : null;

  return (
    <div
      className={`job-row${selected ? ' selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onClick(); }}
    >
      <div className="job-row-main">
        <div className="job-row-title">{job.title}</div>
        <div className="job-row-meta">
          <span>{job.company}</span>
          {job.location && <><span className="dot">·</span><span>{job.location}</span></>}
          {job.remote && job.remote !== 'Unknown' && (
            <><span className="dot">·</span><span className={`remote-badge ${REMOTE_CSS[job.remote] || ''}`}>{job.remote}</span></>
          )}
          {job.source && <><span className="dot">·</span><span className="source-badge">{job.source}</span></>}
          <><span className="dot">·</span><span className="age-label">{job.posted || job.age}</span></>
        </div>
        {match && badgeLabel && (
          <div className="job-row-match">
            {match.matched?.slice(0, 4).map(s => <span key={s} className="skill-chip matched">{s}</span>)}
            {match.missing?.slice(0, 2).map(s => <span key={s} className="skill-chip missing">{s}</span>)}
            <span className={`match-badge ${badgeCls}`}>{badgeLabel}</span>
          </div>
        )}
      </div>
      <div className="job-row-actions" onClick={e => e.stopPropagation()}>
        {job.status === 'pending' ? (
          <>
            <button className="btn-row-action apply" title="Mark applied" onClick={() => onStatusChange(job.job_id, 'applied')}><Icon name="check" size={13} /></button>
            <button className="btn-row-action skip" title="Skip" onClick={() => onStatusChange(job.job_id, 'skipped')}><Icon name="x" size={13} /></button>
          </>
        ) : (
          <button className="btn-row-action restore" title="Restore to pending" onClick={() => onStatusChange(job.job_id, 'pending')}>↩</button>
        )}
        {job.resume_status === 'building' && <span className="spinner spinner-xs spinner-resume" />}
        {job.resume_status === 'done' && job.pdf_url && (
          <a
            href={safeUrl(job.pdf_url)}
            target="_blank"
            rel="noreferrer"
            title="Open CV"
            style={{ color: 'var(--green)', fontSize: '0.75rem', textDecoration: 'none' }}
            onClick={e => e.stopPropagation()}
          >
            CV
          </a>
        )}
        {job.cl_status === 'building' && <span className="spinner spinner-xs spinner-cl" />}
        {job.cl_status === 'done' && <span title="Cover letter ready" style={{ color: 'var(--blue-light)', fontSize: '0.75rem' }}>CL</span>}
      </div>
    </div>
  );
}

// ── Pagination ────────────────────────────────────────────────────────────────

function Pagination({ page, total, pageSize, onChange }: { page: number; total: number; pageSize: number; onChange: (p: number) => void }) {
  const pages = Math.ceil(total / pageSize);
  if (pages <= 1) return null;
  const items: (number | '…')[] = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - page) <= 1) items.push(i);
    else if (items[items.length - 1] !== '…') items.push('…');
  }
  return (
    <div className="pagination-bar">
      <button className="page-btn" disabled={page === 1} onClick={() => onChange(page - 1)}>‹</button>
      {items.map((item, i) =>
        item === '…'
          ? <span key={`e${i}`} className="page-ellipsis">…</span>
          : <button key={item} className={`page-btn${item === page ? ' active' : ''}`} onClick={() => onChange(item as number)}>{item}</button>
      )}
      <button className="page-btn" disabled={page === pages} onClick={() => onChange(page + 1)}>›</button>
    </div>
  );
}

// ── Detail panel (split view) ─────────────────────────────────────────────────

function DetailPanel({ jobId, initialJob, onClose, onJobUpdated }: { jobId: string; initialJob: Job; onClose: () => void; onJobUpdated: (job: JobDetail) => void }) {
  const [job, setJob] = useState<JobDetail>({ ...initialJob, description: '', employment_type: '', salary_range: '', status_updated_at: '' });
  const [descExpanded, setDescExpanded] = useState(false);
  const [buildingResume, setBuildingResume] = useState(false);
  const { showToast } = useToast();
  const navigate = useNavigate();
  const resumeDoc = useDocumentStatus(jobId, 'resume', buildingResume || job.resume_status === 'building');

  useEffect(() => {
    if (!jobId) return;
    setDescExpanded(false);
    jobsApi.get(jobId).then(async (data) => {
      setJob(data);
      onJobUpdated(data);
      if (!data.description) {
        try {
          const desc = await jobsApi.description(jobId);
          if (desc.description) setJob(j => j ? { ...j, description: desc.description } : j);
        } catch { /* non-fatal */ }
      }
    }).catch(() => {});
  }, [jobId, onJobUpdated]);

  const setStatus = async (status: 'applied' | 'skipped' | 'pending') => {
    try {
      await jobsApi.setStatus(jobId, status);
      const updated = await jobsApi.get(jobId);
      setJob(updated);
      onJobUpdated(updated);
    } catch {
      showToast('Could not update job status — please try again', 'err');
    }
  };

  const handleBuildResume = async () => {
    if (buildingResume) return;              // guard against duplicate submission
    setBuildingResume(true);
    setJob(current => ({ ...current, resume_status: 'building', resume_error: null }));
    try {
      await documents.buildResume(jobId);
      showToast('Building CV…');
    } catch {
      setJob(current => ({ ...current, resume_status: 'idle' }));
      showToast('Failed to start CV build', 'err');
      setBuildingResume(false);
    }
  };

  useEffect(() => {
    if (!resumeDoc.status || resumeDoc.status === 'idle') return;

    if (resumeDoc.status === 'building') {
      setJob(current => ({ ...current, resume_status: 'building' }));
      return;
    }

    if (resumeDoc.status === 'done' || resumeDoc.status === 'error') {
      setBuildingResume(false);
      jobsApi.get(jobId)
        .then(updated => {
          setJob(updated);
          onJobUpdated(updated);
        })
        .catch(() => {
          setJob(current => ({
            ...current,
            resume_status: resumeDoc.status,
            pdf_url: resumeDoc.pdfUrl ?? current.pdf_url,
            resume_error: resumeDoc.error ?? current.resume_error,
          }));
        });
    }
  }, [jobId, onJobUpdated, resumeDoc.error, resumeDoc.pdfUrl, resumeDoc.status]);

  if (!job) return <div className="detail-panel-loading"><span className="spinner" /></div>;

  const descHtml = job.description ? formatDescription(job.description) : null;
  const isLong = job.description ? isLongDescription(job.description) : false;

  return (
    <div className="detail-panel-content">
      <div className="panel-header">
        <button className="panel-close" onClick={onClose} aria-label="Close panel">
          <Icon name="x" size={16} />
        </button>
        <button className="panel-open-full" onClick={() => navigate(`/job/${jobId}`)}>
          <Icon name="external" size={14} /> Full view
        </button>
      </div>
      <div className="panel-hero">
        <h2 className="panel-title">
          {job.url ? (
            <a href={safeUrl(job.url)} target="_blank" rel="noreferrer" className="panel-title-link">
              {job.title}
            </a>
          ) : job.title}
        </h2>
        <div className="panel-company">{job.company}</div>
        <div className="panel-meta">
          {job.location && <span>{job.location}</span>}
          {job.remote && job.remote !== 'Unknown' && <span className={`remote-badge ${REMOTE_CSS[job.remote] || ''}`}>{job.remote}</span>}
          {job.source && <span className="source-badge">{job.source}</span>}
          {job.posted && <span>{job.posted}</span>}
        </div>
      </div>
      <div className="panel-actions">
        {job.status === 'pending' ? (
          <>
            <button className="btn btn-success btn-sm" onClick={() => setStatus('applied')}><Icon name="check" size={13} /> Applied</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setStatus('skipped')}><Icon name="x" size={13} /> Skip</button>
          </>
        ) : (
          <>
            <span className={`status-pill ${job.status}`}>{job.status === 'applied' ? 'Applied' : 'Skipped'}</span>
            <button className="btn btn-ghost btn-sm" onClick={() => setStatus('pending')}>↩ Restore</button>
          </>
        )}
        {job.url && (
          <a href={safeUrl(job.url)} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">
            <Icon name="external" size={13} /> Source
          </a>
        )}
      </div>
      <div className="panel-docs">
        {job.resume_status === 'idle' && (
          <button className="btn btn-sm" style={{ background: '#2e1f6e', color: '#c4b5fd', border: '1px solid #4c2ea8' }} onClick={handleBuildResume} disabled={buildingResume}>▶ Build CV</button>
        )}
        {(job.resume_status === 'building' || buildingResume) && <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}><span className="spinner spinner-xs spinner-resume" /> Building CV…</span>}
        {job.resume_status === 'done' && job.pdf_url && (
          <a href={safeUrl(job.pdf_url)} target="_blank" rel="noreferrer" className="btn btn-success btn-sm">📄 Open CV</a>
        )}
        {job.resume_status === 'error' && (
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--red)' }}>{job.resume_error || 'CV build failed'}</span>
        )}
      </div>
      {job.match && (
        <div className="panel-match">
          {job.match.matched?.slice(0, 6).map(s => <span key={s} className="skill-tag">{s}</span>)}
          {job.match.missing?.slice(0, 3).map(s => <span key={s} className="skill-tag-missing">{s}</span>)}
        </div>
      )}
      {/* Description */}
      <div className="panel-desc">
        {descHtml ? (
          <>
            <div
              className={`description-body${isLong && !descExpanded ? ' desc-clamped' : ''}`}
              dangerouslySetInnerHTML={{ __html: descHtml }}
            />
            {isLong && (
              <button className="desc-toggle" onClick={() => setDescExpanded(e => !e)}>
                {descExpanded ? 'Show less ▴' : 'Show more ▾'}
              </button>
            )}
          </>
        ) : (
          <p style={{ fontStyle: 'italic', color: 'var(--text-faint)', fontSize: 'var(--text-sm)' }}>
            {job.url
              ? <><span>No description — </span><a href={safeUrl(job.url)} target="_blank" rel="noreferrer" style={{ color: 'var(--blue-light)' }}>view on source ↗</a></>
              : 'No description available.'}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Settings modal ────────────────────────────────────────────────────────────

function SettingsModal({ open, onClose, onSaved, allSources }: { open: boolean; onClose: () => void; onSaved: () => void; allSources: string[] }) {
  const { showToast } = useToast();
  const [cfg, setCfg] = useState<SearchConfig>({ searches: [], title_filter: [], blacklist: [], company_blacklist: [] });
  const [rows, setRows] = useState<SearchRowEntry[]>([]);
  const [saving, setSaving] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  useFocusTrap(modalRef, open, onClose);

  useEffect(() => {
    if (open) {
      configApi.get()
        .then(data => {
          setCfg(data);
          setRows(groupSearchEntries(data.searches || []));
        })
        .catch(() => showToast('Could not load settings', 'err'));
    }
  }, [open, showToast]);

  const handleSave = async () => {
    const searches = expandSearchRows(rows);
    if (!searches.length) {
      showToast('Add at least one search source', 'err');
      return;
    }
    const next = { ...cfg, searches };
    setSaving(true);
    try {
      await configApi.save(next);
      showToast('Settings saved');
      onClose();
      onSaved();
    } catch {
      showToast('Could not save settings', 'err');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div
      ref={backdropRef}
      className="modal-backdrop open"
      onClick={e => { if (e.target === backdropRef.current) onClose(); }}
    >
      <div
        className="modal"
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="fetch-settings-title"
      >
        <div className="modal-header">
          <h2 id="fetch-settings-title">⚙ Fetch Settings</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close"><Icon name="x" size={18} /></button>
        </div>
        <div className="modal-body">
          <p className="settings-intro">Controls what gets scraped from job boards.</p>
          <div className="settings-section">
            <h3>Search Sources</h3>
            {rows.map((row, i) => (
              <SearchRow key={i} entry={row} sources={allSources}
                onChange={v => { const n = [...rows]; n[i] = v; setRows(n); }}
                onRemove={() => setRows(rows.filter((_, j) => j !== i))}
              />
            ))}
            <button className="btn-add" onClick={() => setRows([...rows, { query: '', locations: ['United States'], remote: true, sources: [...allSources] }])}>+ Add search</button>
          </div>
          <div className="settings-section">
            <h3>Title Filter <small>(keep jobs matching at least one)</small></h3>
            <TagInput value={cfg.title_filter} onChange={v => setCfg(c => ({ ...c, title_filter: v }))} placeholder="add keyword, Enter" />
          </div>
          <div className="settings-section">
            <h3>Blacklist <small>(drop jobs containing these words)</small></h3>
            <TagInput value={cfg.blacklist} onChange={v => setCfg(c => ({ ...c, blacklist: v }))} placeholder="add keyword, Enter" />
          </div>
          <div className="settings-section">
            <h3>Company Blacklist</h3>
            <TagInput value={cfg.company_blacklist} onChange={v => setCfg(c => ({ ...c, company_blacklist: v }))} placeholder="add company, Enter" />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save settings'}</button>
        </div>
      </div>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

type Tab = 'pending' | 'applied' | 'skipped';

export default function DashboardPage() {
  const [tab, setTab] = useState<Tab>('pending');
  const [allJobs, setAllJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [counts, setCounts] = useState({ pending: 0, applied: 0, skipped: 0 });
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [renderedPanelJobId, setRenderedPanelJobId] = useState<string | null>(null);
  const [renderedPanelJob, setRenderedPanelJob] = useState<Job | null>(null);
  const [panelState, setPanelState] = useState<PanelState>('closed');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [fetchRunning, setFetchRunning] = useState(false);
  const [fetchMessage, setFetchMessage] = useState('');
  const [appConstants, setAppConstants] = useState<AppConstants | null>(null);
  const [savedSearches, setSavedSearches] = useState<Filters[]>(() => {
    try { return JSON.parse(localStorage.getItem(LS_SAVED) || '[]').map((item: Partial<Filters>) => normalizeFilters(item)); } catch { return []; }
  });
  const [recentSearches, setRecentSearches] = useState<Filters[]>(() => {
    try { return JSON.parse(localStorage.getItem(LS_RECENT) || '[]').map((item: Partial<Filters>) => normalizeFilters(item)); } catch { return []; }
  });
  const { showToast } = useToast();
  const { active: activeProfile } = useProfile();
  const isWide = useIsWide();
  const navigate = useNavigate();
  const fetchPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fetchRefreshInFlightRef = useRef(false);
  const handleFetchRef = useRef<() => void>(() => {});

  // Clean up any in-flight fetch poll on unmount (prevents setState-after-unmount)
  useEffect(() => () => { if (fetchPollRef.current) clearInterval(fetchPollRef.current); }, []);

  const loadJobs = useCallback(async () => {
    try {
      const data = await jobsApi.list(tab);
      setAllJobs(data);
      setCounts(current => ({ ...current, [tab]: data.length }));
      setLoadError(false);
      return data;
    } catch (e) {
      console.error('[Dashboard] loadJobs failed:', e);
      setLoadError(true);
      return null;
    }
  }, [tab]);

  const loadCounts = useCallback(async () => {
    try {
      setCounts(await jobsApi.counts());
    } catch { /* counts are best-effort; job-load error is surfaced separately */ }
  }, []);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    loadJobs().finally(() => setLoading(false));
    loadCounts();
    // If we just switched to an empty profile, auto-trigger a fetch.
    if (consumeProfileFetchSignal()) handleFetchRef.current();
  }, [tab, loadJobs, loadCounts, activeProfile?.slug]);

  useEffect(() => {
    const id = setInterval(loadJobs, 30000);
    return () => clearInterval(id);
  }, [loadJobs]);

  useEffect(() => { constants.get().then(setAppConstants); }, []);

  const filteredJobs = useMemo(() => applyFilters(allJobs, filters), [allJobs, filters]);
  const pagedJobs = filteredJobs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const hasFilters = filters.remote.length > 0 || filters.source || filters.posted || filters.cv || filters.search;
  const selectedJob = useMemo(
    () => (selectedJobId ? allJobs.find(job => job.job_id === selectedJobId) ?? null : null),
    [allJobs, selectedJobId]
  );

  // Source options come from the labels actually present on loaded jobs, so the
  // option value matches each job's `source` exactly (the /api/sources list uses
  // lowercase ids that don't match the capitalised display labels).
  const sourceOptions = useMemo(
    () => [...new Set(allJobs.map(j => j.source).filter(Boolean))].sort(),
    [allJobs]
  );

  const closePanel = useCallback(() => {
    setSelectedJobId(null);
    setRenderedPanelJobId(null);
    setRenderedPanelJob(null);
    setPanelState('closed');
  }, []);

  useEffect(() => {
    if (!isWide) {
      setRenderedPanelJobId(null);
      setRenderedPanelJob(null);
      setPanelState('closed');
      return;
    }

    if (selectedJobId && selectedJob) {
      setRenderedPanelJobId(selectedJobId);
      setRenderedPanelJob(selectedJob);
      setPanelState(current => {
        if (renderedPanelJobId === selectedJobId) return current;
        return 'opening';
      });
      return;
    }

    if (!selectedJobId && renderedPanelJobId) {
      setRenderedPanelJobId(null);
      setRenderedPanelJob(null);
      setPanelState('closed');
    }
  }, [isWide, renderedPanelJobId, selectedJob, selectedJobId]);

  const handlePanelAnimationEnd = useCallback((event: React.AnimationEvent<HTMLElement>) => {
    if (event.target !== event.currentTarget) return;

    if (panelState === 'opening') {
      setPanelState('open');
      return;
    }

  }, [panelState]);

  const handleStatusChange = async (jobId: string, status: string) => {
    // Optimistic update: drop the row and adjust counts immediately so the UI
    // responds instantly, then persist in the background.
    const prevJobs = allJobs;
    const prevCounts = counts;
    const moved = allJobs.find(j => j.job_id === jobId);
    setAllJobs(js => js.filter(j => j.job_id !== jobId));
    setCounts(c => {
      const next = { ...c };
      if (moved && (moved.status in next)) next[moved.status as keyof typeof next] -= 1;
      if (status in next) next[status as keyof typeof next] += 1;
      return next;
    });
    if (selectedJobId === jobId) closePanel();

    try {
      await jobsApi.setStatus(jobId, status);
    } catch {
      // Roll back on failure
      setAllJobs(prevJobs);
      setCounts(prevCounts);
      showToast('Could not update job status — please try again', 'err');
    }
  };

  const handleJobUpdated = useCallback((updated: Job | JobDetail) => {
    setAllJobs(current => current.map(job => job.job_id === updated.job_id ? {
      ...job,
      status: updated.status,
      resume_status: updated.resume_status,
      resume_stage: updated.resume_stage,
      pdf_url: updated.pdf_url,
      resume_error: updated.resume_error,
      cl_status: updated.cl_status,
      cl_stage: updated.cl_stage,
      cl_pdf_url: updated.cl_pdf_url,
      cl_error: updated.cl_error,
    } : job));
  }, []);

  const handleFetch = async () => {
    setFetchRunning(true);
    setFetchMessage('Starting fetch…');
    try {
      await fetcherApi.trigger();
    } catch {
      setFetchRunning(false);
      showToast('Could not start fetch — please try again', 'err');
      return;
    }
    if (fetchPollRef.current) clearInterval(fetchPollRef.current);
    fetchPollRef.current = setInterval(async () => {
      try {
        const s = await fetcherApi.status();
        if (s.message) setFetchMessage(s.message);
        if (s.status === 'running' && !fetchRefreshInFlightRef.current) {
          fetchRefreshInFlightRef.current = true;
          Promise.all([loadJobs(), loadCounts()]).finally(() => {
            fetchRefreshInFlightRef.current = false;
          });
        }
        if (s.status !== 'running') {
          if (fetchPollRef.current) clearInterval(fetchPollRef.current);
          fetchPollRef.current = null;
          setFetchRunning(false);
          setLoading(true);
          await Promise.all([loadJobs(), loadCounts()]);
          setLoading(false);
          setTimeout(() => setFetchMessage(''), 3000);
        }
      } catch {
        if (fetchPollRef.current) clearInterval(fetchPollRef.current);
        fetchPollRef.current = null;
        setFetchRunning(false);
        showToast('Lost connection while fetching', 'err');
      }
    }, 1500);
  };
  handleFetchRef.current = handleFetch;

  // After saving fetch settings: the previously-fetched jobs no longer reflect
  // the new config, so clear them and re-fetch (matches the original app flow).
  const handleSettingsSaved = async () => {
    try {
      await jobsApi.clear();
      await Promise.all([loadJobs(), loadCounts()]);
    } catch { /* clear is best-effort */ }
    handleFetch();
  };

  const setFilter = (k: keyof Filters, v: unknown) => {
    setFilters(f => ({ ...f, [k]: v }));
    setPage(1);
  };

  const clearFilters = () => { setFilters(DEFAULT_FILTERS); setPage(1); };

  const toggleRemote = (value: string) => {
    setFilters(f => ({
      ...f,
      remote: f.remote.includes(value)
        ? f.remote.filter(r => r !== value)
        : [...f.remote, value],
    }));
    setPage(1);
  };

  // Save / apply search chips
  const saveSearch = () => {
    if (!hasFilters) return;
    const key = filtersToKey(filters);
    const next = [filters, ...savedSearches.filter(s => filtersToKey(s) !== key)].slice(0, 10);
    setSavedSearches(next);
    localStorage.setItem(LS_SAVED, JSON.stringify(next));
    showToast('Search saved ☆');
  };

  const captureRecent = (f: Filters) => {
    if (!f.search && !f.source && !f.posted && !f.cv && !f.remote.length) return;
    const key = filtersToKey(f);
    const next = [f, ...recentSearches.filter(s => filtersToKey(s) !== key)].slice(0, 5);
    setRecentSearches(next);
    localStorage.setItem(LS_RECENT, JSON.stringify(next));
  };

  const applyChip = (f: Filters) => {
    const next = normalizeFilters(f);
    setFilters(next);
    setPage(1);
    captureRecent(next);
  };

  const removeSaved = (f: Filters) => {
    const next = savedSearches.filter(s => filtersToKey(s) !== filtersToKey(f));
    setSavedSearches(next);
    localStorage.setItem(LS_SAVED, JSON.stringify(next));
  };

  const isSaved = hasFilters && savedSearches.some(s => filtersToKey(s) === filtersToKey(filters));

  const searchLabel = (f: Filters) => [f.search, f.source, f.remote.join('+'), f.posted ? `${f.posted}d` : '', f.cv === 'created' ? 'CV ready' : ''].filter(Boolean).join(' · ') || 'Search';

  const showChips = savedSearches.length > 0 || recentSearches.length > 0;

  return (
    <AppShell>
      <h1 className="visually-hidden">Job Listings</h1>

      {/* Tabs + toolbar */}
      <div className="toolbar-row">
        <div className="tabs">
          {(['pending', 'applied', 'skipped'] as Tab[]).map(t => (
            <button key={t} className={`tab${tab === t ? ' active' : ''}`}
              onClick={() => { setTab(t); setPage(1); setSelectedJobId(null); }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
              <span className="tab-count">{counts[t]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Search bar row */}
      <div className="search-bar-row">
        <div className="search-bar-wrap">
          <Icon name="search" size={15} className="search-bar-icon" />
          <input
            type="text"
            className="search-bar-input"
            placeholder="Search by title, company, location or source…"
            value={filters.search}
            aria-label="Search jobs"
            onChange={e => setFilter('search', e.target.value)}
            onBlur={() => captureRecent(filters)}
          />
          {filters.search && (
            <button className="search-bar-clear" onClick={() => setFilter('search', '')} aria-label="Clear search">
              <Icon name="x" size={13} />
            </button>
          )}
        </div>

        {/* Fetch progress message */}
        {fetchMessage && (
          <span className="fetch-progress-msg">
            {fetchRunning && <span className="spinner spinner-fetch" style={{ marginRight: 6 }} />}
            {fetchMessage}
          </span>
        )}

        <button
          className={`btn btn-primary btn-sm fetch-jobs-btn${fetchRunning ? ' fetching' : ''}`}
          onClick={handleFetch}
          disabled={fetchRunning}
        >
          <Icon name="refresh" size={14} className={fetchRunning ? 'spin' : ''} />
          {fetchRunning ? 'Fetching…' : 'Fetch jobs'}
        </button>

        <button className="btn btn-ghost btn-sm search-bar-settings" onClick={() => setSettingsOpen(true)}>
          <Icon name="settings" size={14} /> Search settings
        </button>
      </div>

      {/* Filter bar */}
      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Work type</span>
          {[{ val: 'Remote', icon: '🌐' }, { val: 'Hybrid', icon: '🏠' }, { val: 'On-site', icon: '🏢' }].map(({ val, icon }) => (
            <button key={val}
              className={`filter-chip remote-${val.toLowerCase()}${filters.remote.includes(val) ? ' active' : ''}`}
              aria-pressed={filters.remote.includes(val)}
              onClick={() => toggleRemote(val)}>
              {icon} {val}
            </button>
          ))}
        </div>
        <div className="filter-divider" />
        <div className="filter-group">
          <span className="filter-label">Source</span>
          <select className="filter-select" value={filters.source} aria-label="Filter by source"
            onChange={e => { setFilter('source', e.target.value); captureRecent({ ...filters, source: e.target.value }); }}>
            <option value="">All sources</option>
            {sourceOptions.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="filter-divider" />
        <div className="filter-group">
          <span className="filter-label">Posted</span>
          <select className="filter-select" value={filters.posted} aria-label="Filter by posting date"
            onChange={e => { setFilter('posted', e.target.value); captureRecent({ ...filters, posted: e.target.value }); }}>
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
            onChange={e => { setFilter('cv', e.target.value); captureRecent({ ...filters, cv: e.target.value }); }}>
            <option value="">All jobs</option>
            <option value="created">CV created</option>
          </select>
        </div>
        <div className="filter-divider" />
        <div className="filter-group">
          <span className="filter-label">Sort</span>
          <select className="filter-select" value={filters.sort} aria-label="Sort jobs"
            onChange={e => setFilter('sort', e.target.value)}>
            <option value="match">Best match</option>
            <option value="posted">Posted date</option>
            <option value="newest">Recently fetched</option>
            <option value="oldest">Oldest fetched</option>
            <option value="title">Title A–Z</option>
            <option value="company">Company A–Z</option>
          </select>
        </div>
        <div className="filter-spacer" />
        <span className="filter-results">{filteredJobs.length} jobs</span>
        <button
          className={`filter-save${isSaved ? ' is-saved' : ''}`}
          onClick={saveSearch}
          disabled={!hasFilters}
          title={!hasFilters ? 'Set a filter to save this search' : isSaved ? 'Remove saved search' : 'Save this search'}
        >
          {isSaved ? '★' : '☆'} Save
        </button>
        {hasFilters && <button className="filter-clear" onClick={clearFilters}>Clear filters</button>}
      </div>

      {/* Saved / recent search chips */}
      {showChips && (
        <div className="search-chips">
          {savedSearches.length > 0 && (
            <>
              <span className="search-chips-label">Saved</span>
              {savedSearches.map((s, i) => (
                <button key={i} className="search-chip saved" onClick={() => applyChip(s)}>
                  {searchLabel(s)}
                  <span className="chip-x" onClick={e => { e.stopPropagation(); removeSaved(s); }}>✕</span>
                </button>
              ))}
            </>
          )}
          {recentSearches.length > 0 && (
            <>
              <span className="search-chips-label" style={{ marginLeft: savedSearches.length ? 8 : 0 }}>Recent</span>
              {recentSearches.map((s, i) => (
                <button key={i} className="search-chip" onClick={() => applyChip(s)}>
                  {searchLabel(s)}
                </button>
              ))}
            </>
          )}
        </div>
      )}

      {/* Split view */}
      <div className="split-wrap">
        <div className="jobs-col">
          {loading ? (
            <div className="jobs-skeleton">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="skel-row">
                  <div className="skel-line skel-title skeleton" />
                  <div className="skel-line skel-company skeleton" />
                  <div className="skel-line skel-meta skeleton" />
                </div>
              ))}
            </div>
          ) : loadError ? (
            <div className="empty-state" role="alert">
              <div className="empty-state-icon">⚠️</div>
              <div className="empty-state-title">Couldn't load jobs</div>
              <div className="empty-state-desc">Something went wrong reaching the server.</div>
              <button className="btn btn-primary" style={{ marginTop: 'var(--space-2)' }} onClick={() => { setLoading(true); Promise.all([loadJobs(), loadCounts()]).finally(() => setLoading(false)); }}>
                Retry
              </button>
            </div>
          ) : pagedJobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">{hasFilters ? '🔍' : '📭'}</div>
              <div className="empty-state-title">{hasFilters ? 'No jobs match your filters' : `No ${tab} jobs`}</div>
              <div className="empty-state-desc">
                {hasFilters ? 'Try clearing your filters.' : tab === 'pending' ? 'Click "Fetch Jobs" to pull the latest listings.' : ''}
              </div>
              {!hasFilters && tab === 'pending' && (
                <button className="btn btn-primary" style={{ marginTop: 'var(--space-2)' }} onClick={handleFetch} disabled={fetchRunning}>
                  Fetch jobs now
                </button>
              )}
              {hasFilters && <button className="btn btn-ghost" style={{ marginTop: 'var(--space-2)' }} onClick={clearFilters}>Clear filters</button>}
            </div>
          ) : (
            <>
              <div className="jobs-list">
                {pagedJobs.map(job => (
                  <JobRow key={job.job_id} job={job} selected={selectedJobId === job.job_id}
                    onClick={() => {
                      if (isWide) {
                        if (selectedJobId === job.job_id) closePanel();
                        else setSelectedJobId(job.job_id);
                      } else navigate(`/job/${job.job_id}`);
                    }}
                    onStatusChange={handleStatusChange}
                  />
                ))}
              </div>
              <Pagination page={page} total={filteredJobs.length} pageSize={PAGE_SIZE}
                onChange={p => { setPage(p); window.scrollTo(0, 0); }} />
            </>
          )}
        </div>

        {isWide && renderedPanelJobId && renderedPanelJob && (
          <aside
            key={renderedPanelJobId}
            className={`detail-panel detail-panel-${panelState}`}
            aria-live="polite"
            onAnimationEnd={handlePanelAnimationEnd}
          >
          <DetailPanel jobId={renderedPanelJobId} initialJob={renderedPanelJob} onClose={closePanel} onJobUpdated={handleJobUpdated} />
        </aside>
      )}
      </div>

      {createPortal(
        <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} onSaved={handleSettingsSaved} allSources={appConstants?.sources ?? []} />,
        document.body
      )}
    </AppShell>
  );
}
