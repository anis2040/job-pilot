import type { AiSettings } from '../../../api/types';
import { PROVIDER_META } from '../constants';

export function ActiveBanner({ data }: { data: AiSettings }) {
  const active = data.active_provider;
  return (
    <div className="active-banner">
      <span className="label">Currently using:</span>
      <span className="provider-name">
        {active ? (PROVIDER_META[active]?.label ?? active) : 'None configured'}
      </span>
      {active && data.providers[active]?.model && (
        <span className="model-name">— {data.providers[active].model}</span>
      )}
    </div>
  );
}
