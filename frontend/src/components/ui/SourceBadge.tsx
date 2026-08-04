import { useState } from 'react';

const SOURCE_META: Record<string, { label: string; domain: string }> = {
  linkedin:          { label: 'LinkedIn',           domain: 'linkedin.com' },
  stepstone:         { label: 'StepStone',          domain: 'stepstone.de' },
  greenhouse:        { label: 'Greenhouse',         domain: 'greenhouse.io' },
  himalayas:         { label: 'Himalayas',          domain: 'himalayas.app' },
  jobicy:            { label: 'Jobicy',             domain: 'jobicy.com' },
  germantechjobs:    { label: 'German Tech Jobs',   domain: 'germantechjobs.de' },
  berlinstartupjobs: { label: 'Berlin Startup Jobs',domain: 'berlinstartupjobs.com' },
  heyjobs:           { label: 'HeyJobs',            domain: 'heyjobs.eu' },
};

function FaviconImg({ domain, label }: { domain: string; label: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <span className="source-badge-initial">{label[0]}</span>;
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=16`}
      alt=""
      width={13}
      height={13}
      className="source-badge-favicon"
      onError={() => setFailed(true)}
    />
  );
}

export function SourceBadge({ source }: { source: string }) {
  const meta = SOURCE_META[source.toLowerCase()];
  const label = meta?.label ?? source;
  const domain = meta?.domain;

  return (
    <span className="source-badge-pill">
      {domain && <FaviconImg domain={domain} label={label} />}
      {label}
    </span>
  );
}
