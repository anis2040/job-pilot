import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { jobs as jobsApi, config as configApi, constants } from '../../api/client';
import { useProfile } from '../../hooks/useProfile';
import { consumeProfileFetchSignal } from '../../hooks/profileFetchSignal';
import { useToast } from '../../components/ui/useToast';
import { AppShell } from '../../components/layout/AppShell';
import { groupSearchEntries, type SearchRowEntry } from '../../components/ui/searchRowModel';
import { applyFilters, DEFAULT_FILTERS } from '../../utils/filters';
import type { Filters } from '../../utils/filters';
import type { Job, JobDetail, AppConstants, SaveConfigResult } from '../../api/types';

import { PAGE_SIZE } from './constants';
import type { Tab, PanelState } from './types';
import { deriveFiltersFromSearchRows, normalizeFilters } from './utils/searchFilters';
import { useIsWide } from './hooks/useIsWide';
import { useSavedSearches } from './hooks/useSavedSearches';
import { useJobFetch } from './hooks/useJobFetch';
import { SearchBarRow } from './components/SearchBarRow';
import { FilterBar } from './components/FilterBar';
import { SearchChips } from './components/SearchChips';
import { JobsColumn } from './components/JobsColumn';
import { DetailPanel } from './components/DetailPanel';
import { SettingsModal } from './components/SettingsModal';

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
  const [appConstants, setAppConstants] = useState<AppConstants | null>(null);

  const { showToast } = useToast();
  const { active: activeProfile } = useProfile();
  const isWide = useIsWide();
  const navigate = useNavigate();
  const syncedSettingsProfileRef = useRef<string | null>(null);

  const {
    savedSearches,
    recentSearches,
    saveSearch,
    captureRecent,
    removeSaved,
    isSaved,
    searchLabel,
    showChips,
  } = useSavedSearches();

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

  const { fetchRunning, fetchMessage, handleFetch, handleFetchRef } = useJobFetch(loadJobs, loadCounts, setLoading);

  useEffect(() => {
    setLoading(true);
    setPage(1);
    loadJobs().finally(() => setLoading(false));
    loadCounts();
    if (consumeProfileFetchSignal()) handleFetchRef.current();
  }, [tab, loadJobs, loadCounts, activeProfile?.slug, handleFetchRef]);

  useEffect(() => {
    const id = setInterval(loadJobs, 30000);
    return () => clearInterval(id);
  }, [loadJobs]);

  useEffect(() => { constants.get().then(setAppConstants); }, []);

  const filteredJobs = useMemo(() => applyFilters(allJobs, filters), [allJobs, filters]);
  const pagedJobs = filteredJobs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const hasFilters = Boolean(
    filters.remote.length > 0 || filters.source || filters.posted || filters.cv || filters.search
  );
  const selectedJob = useMemo(
    () => (selectedJobId ? allJobs.find(job => job.job_id === selectedJobId) ?? null : null),
    [allJobs, selectedJobId]
  );

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
    if (panelState === 'opening') setPanelState('open');
  }, [panelState]);

  const handleStatusChange = async (jobId: string, status: string) => {
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

  const applyChip = (f: Filters) => {
    const next = normalizeFilters(f);
    setFilters(next);
    setPage(1);
    captureRecent(next);
  };

  const handleTabChange = (next: Tab) => {
    setTab(next);
    setPage(1);
    setSelectedJobId(null);
  };

  const handleJobClick = (jobId: string) => {
    if (isWide) {
      if (selectedJobId === jobId) closePanel();
      else setSelectedJobId(jobId);
    } else {
      navigate(`/job/${jobId}`);
    }
  };

  const handleRetry = () => {
    setLoading(true);
    Promise.all([loadJobs(), loadCounts()]).finally(() => setLoading(false));
  };

  return (
    <AppShell>
      <h1 className="visually-hidden">Job Listings</h1>

      <SearchBarRow
        tab={tab}
        counts={counts}
        search={filters.search}
        fetchRunning={fetchRunning}
        fetchMessage={fetchMessage}
        onTabChange={handleTabChange}
        onSearchChange={v => setFilter('search', v)}
        onSearchBlur={() => captureRecent(filters)}
        onFetch={handleFetch}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <FilterBar
        filters={filters}
        sourceOptions={sourceOptions}
        resultCount={filteredJobs.length}
        isSaved={isSaved(filters, hasFilters)}
        hasFilters={hasFilters}
        onToggleRemote={toggleRemote}
        onFilterChange={(key, value) => setFilter(key, value)}
        onFilterCapture={captureRecent}
        onSaveSearch={() => saveSearch(filters, hasFilters)}
        onClearFilters={clearFilters}
      />

      {showChips && (
        <SearchChips
          savedSearches={savedSearches}
          recentSearches={recentSearches}
          searchLabel={searchLabel}
          onApply={applyChip}
          onRemoveSaved={removeSaved}
        />
      )}

      <div className="split-wrap">
        <div className="jobs-col">
          <JobsColumn
            loading={loading}
            loadError={loadError}
            tab={tab}
            hasFilters={hasFilters}
            fetchRunning={fetchRunning}
            jobs={pagedJobs}
            totalFiltered={filteredJobs.length}
            page={page}
            selectedJobId={selectedJobId}
            onRetry={handleRetry}
            onFetch={handleFetch}
            onClearFilters={clearFilters}
            onPageChange={setPage}
            onJobClick={handleJobClick}
            onStatusChange={handleStatusChange}
          />
        </div>

        {isWide && renderedPanelJobId && renderedPanelJob && (
          <aside
            key={renderedPanelJobId}
            className={`detail-panel detail-panel-${panelState}`}
            aria-live="polite"
            onAnimationEnd={handlePanelAnimationEnd}
          >
            <DetailPanel
              jobId={renderedPanelJobId}
              initialJob={renderedPanelJob}
              onClose={closePanel}
              onJobUpdated={handleJobUpdated}
            />
          </aside>
        )}
      </div>

      {createPortal(
        <SettingsModal
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          onSaved={handleSettingsSaved}
          allSources={appConstants?.sources ?? []}
        />,
        document.body
      )}
    </AppShell>
  );
}
