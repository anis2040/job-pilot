import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { jobs as jobsApi, documents, config as configApi, fetcher as fetcherApi, constants } from '../../api/client';
import { useProfile } from '../../hooks/useProfile';
import { SourceBadge } from '../../components/ui/SourceBadge';
import { consumeProfileFetchSignal } from '../../hooks/profileFetchSignal';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { useToast } from '../../components/ui/useToast';
import { AppShell } from '../../components/layout/AppShell';
import { Icon } from '../../components/ui/Icon';
import { TagInput } from '../../components/ui/TagInput';
import { useDocumentStatus } from '../../hooks/useDocumentStatus';
import { SearchRow } from '../../components/ui/SearchRow';
import { createSearchRow, deriveTitleFilters, groupSearchEntries, expandSearchRows, WORK_STYLES, type SearchRowEntry } from '../../components/ui/searchRowModel';
import { formatDescription, isLongDescription } from '../../utils/descriptionRenderer';
import { shouldFetchFullDescription } from '../../utils/jobDescription';
import { safeUrl } from '../../utils/format';
import { applyFilters, filtersToKey, DEFAULT_FILTERS } from '../../utils/filters';
import type { Filters } from '../../utils/filters';
import type { Job, JobDetail, SearchConfig, AppConstants, SaveConfigResult } from '../../api/types';

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

function sameFilterValue(a: string, b: string) {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

function addUniqueFilterValue(list: string[], raw: string) {
  const next = raw.trim();
  if (!next || list.some(item => sameFilterValue(item, next))) return list;
  return [...list, next];
}

function resolveSourceValue(source: string, options: string[]) {
  return options.find(option => sameFilterValue(option, source)) ?? source;
}

function deriveFiltersFromSearchRows(rows: SearchRowEntry[], current: Filters, sourceOptions: string[]): Filters {
  const titles = rows.reduce<string[]>((list, row) => {
    let next = list;
    for (const title of row.titles) next = addUniqueFilterValue(next, title);
    return next;
  }, []);
  const remote = WORK_STYLES.filter(style => rows.some(row => row.workStyles.includes(style)));
  const sources = rows.reduce<string[]>((list, row) => {
    let next = list;
    for (const source of row.sources) next = addUniqueFilterValue(next, source);
    return next;
  }, []);

  return {
    ...current,
    search: titles.join(', '),
    remote,
    source: sources.length === 1 ? resolveSourceValue(sources[0], sourceOptions) : '',
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

  const topSkills = match?.matched?.slice(0, 3) ?? [];

  return (
    <div
      className={`job-row${selected ? ' selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onClick(); }}
    >
      {/* Left: main content */}
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

        {topSkills.length > 0 && (
          <div className="job-row-skills">
            {topSkills.map(s => <span key={s} className="skill-chip matched">{s}</span>)}
            {(match?.missing?.length ?? 0) > 0 && (
              <span className="skill-chip missing">+{match!.missing.length} missing</span>
            )}
          </div>
        )}
      </div>

      {/* Right: score + source + actions */}
      <div className="job-row-right" onClick={e => e.stopPropagation()}>
        <div className="job-row-score-row">
          {matchPct !== null && (
            <span className={`match-badge ${badgeCls}`}>{matchPct}%</span>
          )}
          {matchPct === null && skillCount > 0 && (
            <span className={`match-badge ${badgeCls}`}>{skillCount} skills</span>
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

// ── ProviderIcon ─────────────────────────────────────────────────────────────

const SOURCE_DOMAINS: Record<string, string> = {
  linkedin:          'linkedin.com',
  stepstone:         'stepstone.de',
  greenhouse:        'greenhouse.io',
  himalayas:         'himalayas.app',
  jobicy:            'jobicy.com',
  germantechjobs:    'germantechjobs.de',
  berlinstartupjobs: 'berlinstartupjobs.com',
  heyjobs:           'heyjobs.eu',
};

function ProviderIcon({ source, company }: { source?: string; company?: string }) {
  const [imgOk, setImgOk] = useState(true);
  const domain = source ? SOURCE_DOMAINS[source.toLowerCase()] : null;
  const initial = company?.[0]?.toUpperCase() ?? '?';

  if (domain && imgOk) {
    return (
      <span className="panel-provider-icon">
        <img
          src={`https://www.google.com/s2/favicons?domain=${domain}&sz=64`}
          alt={source}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          onError={() => setImgOk(false)}
        />
      </span>
    );
  }
  return <span className="panel-company-initial">{initial}</span>;
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
      if (shouldFetchFullDescription(data)) {
        try {
          const desc = await jobsApi.description(jobId);
          const enriched: JobDetail = {
            ...data,
            description: desc.description || data.description,
            remote: desc.remote || data.remote,
            match: desc.match ?? data.match,
          };
          setJob(enriched);
          onJobUpdated(enriched);
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
        <div className="panel-header-info">
          <ProviderIcon source={job.source} company={job.company} />
          <div className="panel-header-text">
            {job.url
              ? <a href={safeUrl(job.url)} target="_blank" rel="noreferrer" className="panel-header-title">{job.title}</a>
              : <span className="panel-header-title" style={{ cursor: 'default' }}>{job.title}</span>
            }
            <div className="panel-header-meta">
              <span className="panel-header-company">{job.company}</span>
              {job.location && <><span className="dot">·</span><span className="panel-meta-item"><Icon name="mapPin" size={10} />{job.location}</span></>}
              {job.remote && job.remote !== 'Unknown' && <><span className="dot">·</span><span className={`remote-badge panel-meta-item ${REMOTE_CSS[job.remote] || ''}`}><Icon name={job.remote === 'Remote' ? 'globe' : 'building'} size={10} />{job.remote}</span></>}
              {job.posted && <><span className="dot">·</span><span className="panel-meta-item"><Icon name="clock" size={10} />{job.posted}</span></>}
            </div>
          </div>
        </div>
        <div className="panel-header-actions">
          <button className="panel-action-btn" title="Open full detail" onClick={() => navigate(`/job/${jobId}`)}>
            <Icon name="maximize" size={14} />
          </button>
          <button className="panel-action-btn panel-action-close" onClick={onClose} aria-label="Close panel">
            <Icon name="x" size={15} />
          </button>
        </div>
      </div>
      {job.match && (
        <div className="panel-match">
          {job.match.matched?.slice(0, 6).map(s => <span key={s} className="skill-tag">{s}</span>)}
          {job.match.missing?.slice(0, 3).map(s => <span key={s} className="skill-tag-missing">{s}</span>)}
        </div>
      )}
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
          <p style={{ fontStyle: 'italic', color: 'var(--text-faint)', fontSize: 'var(--text-sm)' }}>No description available.</p>
        )}
        <div className="panel-cv-row">
          {job.resume_status === 'idle' && (
            <button className="btn btn-ai btn-sm" onClick={handleBuildResume} disabled={buildingResume}>✦ Build CV</button>
          )}
          {(job.resume_status === 'building' || buildingResume) && (
            <span className="panel-building"><span className="spinner spinner-xs" /> Building…</span>
          )}
          {job.resume_status === 'done' && job.pdf_url && (
            <a href={safeUrl(job.pdf_url)} target="_blank" rel="noreferrer" className="btn btn-success btn-sm">📄 Open CV</a>
          )}
          {job.resume_status === 'error' && (
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--red)' }}>{job.resume_error?.slice(0, 60) || 'Build failed'}</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Settings modal ────────────────────────────────────────────────────────────

function SettingsModal({ open, onClose, onSaved, allSources }: { open: boolean; onClose: () => void; onSaved: (rows: SearchRowEntry[], result: SaveConfigResult) => void; allSources: string[] }) {
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
    const next = { ...cfg, searches, title_filter: deriveTitleFilters(rows) };
    setSaving(true);
    try {
      const result = await configApi.save(next);
      showToast(result.fetch_required ? 'Settings saved. Fetching uncovered searches…' : 'Settings saved. Updated local filters.');
      onClose();
      onSaved(rows, result);
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
            <button className="btn-add" onClick={() => setRows([...rows, createSearchRow(allSources)])}>+ Add search</button>
          </div>
          <div className="settings-section">
            <h3>Exclude keywords <small>(drop jobs containing these words)</small></h3>
            <TagInput value={cfg.blacklist} onChange={v => setCfg(c => ({ ...c, blacklist: v }))} placeholder="add keyword, Enter" />
          </div>
          <div className="settings-section">
            <h3>Exclude companies</h3>
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
  const syncedSettingsProfileRef = useRef<string | null>(null);

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
    () => [...new Set([
      ...allJobs.map(j => j.source).filter(Boolean),
      ...(appConstants?.sources ?? []),
      filters.source,
    ].filter(Boolean))].sort(),
    [allJobs, appConstants?.sources, filters.source]
  );

  const syncFiltersWithSearchRows = useCallback((rows: SearchRowEntry[]) => {
    setFilters(current => deriveFiltersFromSearchRows(rows, current, sourceOptions));
    setPage(1);
  }, [sourceOptions]);

  useEffect(() => {
    const profileKey = activeProfile?.slug ?? '';
    if (syncedSettingsProfileRef.current === profileKey) return;
    syncedSettingsProfileRef.current = profileKey;
    let cancelled = false;
    configApi.get()
      .then(data => {
        if (cancelled) return;
        const rows = groupSearchEntries(data.searches || []);
        if (rows.length) setFilters(current => deriveFiltersFromSearchRows(rows, current, sourceOptions));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [activeProfile?.slug, sourceOptions]);

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
      remote: updated.remote,
      match: updated.match,
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

  const handleSettingsSaved = async (rows: SearchRowEntry[], result: SaveConfigResult) => {
    syncFiltersWithSearchRows(rows);
    if (result.fetch_required) handleFetch();
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

      {/* Search bar row — tabs + search + fetch merged */}
      <div className="search-bar-row">
        <div className="tab-pill-group">
          {(['pending', 'applied', 'skipped'] as Tab[]).map(t => (
            <button key={t} className={`tab-pill${tab === t ? ' active' : ''}`}
              onClick={() => { setTab(t); setPage(1); setSelectedJobId(null); }}>
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

        {fetchMessage && (
          <span className="fetch-progress-msg">
            {fetchRunning && <span className="spinner spinner-fetch" style={{ marginRight: 6 }} />}
            {fetchMessage}
          </span>
        )}

        <button
          className={`search-action-btn search-action-fetch${fetchRunning ? ' fetching' : ''}`}
          onClick={handleFetch}
          disabled={fetchRunning}
        >
          <Icon name="refresh" size={15} className={fetchRunning ? 'spin' : ''} />
          {fetchRunning ? 'Fetching…' : 'Fetch jobs'}
        </button>

        <button className="search-action-btn search-action-settings" onClick={() => setSettingsOpen(true)}>
          <Icon name="settings" size={15} /> Search settings
        </button>
      </div>

      {/* Filter bar */}
      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Work type</span>
          {[{ val: 'Remote' }, { val: 'Hybrid' }, { val: 'On-site' }].map(({ val }) => (
            <button key={val}
              className={`filter-chip remote-${val.toLowerCase()}${filters.remote.includes(val) ? ' active' : ''}`}
              aria-pressed={filters.remote.includes(val)}
              onClick={() => toggleRemote(val)}>
              {val}
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
        {hasFilters && <button className="filter-clear" onClick={clearFilters}>Clear</button>}
      </div>

      {/* Saved / recent search chips */}
      {showChips && (
        <div className="search-chips">
          {savedSearches.length > 0 && savedSearches.map((s, i) => (
            <button key={i} className="search-chip saved" onClick={() => applyChip(s)}>
              <span className="search-chip-icon">★</span>
              {searchLabel(s)}
              <span className="chip-x" onClick={e => { e.stopPropagation(); removeSaved(s); }}>✕</span>
            </button>
          ))}
          {recentSearches.length > 0 && (
            <span className="search-chips-divider" />
          )}
          {recentSearches.length > 0 && recentSearches.map((s, i) => (
            <button key={i} className="search-chip recent" onClick={() => applyChip(s)}>
              <span className="search-chip-icon">↺</span>
              {searchLabel(s)}
            </button>
          ))}
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
                onChange={setPage} />
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
