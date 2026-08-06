import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { jobs as jobsApi, documents } from '../../../api/client';
import { useDocumentStatus } from '../../../hooks/useDocumentStatus';
import { useToast } from '../../../components/ui/useToast';
import { Icon } from '../../../components/ui/Icon';
import { formatDescription, isLongDescription } from '../../../utils/descriptionRenderer';
import { shouldFetchFullDescription } from '../../../utils/jobDescription';
import { safeUrl } from '../../../utils/format';
import type { Job, JobDetail } from '../../../api/types';
import { REMOTE_CSS } from '../constants';
import { ProviderIcon } from './ProviderIcon';

interface DetailPanelProps {
  jobId: string;
  initialJob: Job;
  onClose: () => void;
  onJobUpdated: (job: JobDetail) => void;
}

export function DetailPanel({ jobId, initialJob, onClose, onJobUpdated }: DetailPanelProps) {
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

  const handleBuildResume = async () => {
    if (buildingResume) return;
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
