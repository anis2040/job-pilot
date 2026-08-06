import { useState } from 'react';
import { SOURCE_DOMAINS } from '../constants';

interface ProviderIconProps {
  source?: string;
  company?: string;
}

export function ProviderIcon({ source, company }: ProviderIconProps) {
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
