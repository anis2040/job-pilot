import type { ProviderInfo } from '../../../api/types';
import { fmtK } from '../../../utils/format';
import { usageBarStats } from '../utils/usageBar';

export function UsageStrip({ info }: { info: ProviderInfo }) {
  if (!info.usage || !info.key_set) return null;
  const { used, limit, pct, fillClass } = usageBarStats(info.usage);
  return (
    <div className="usage-strip">
      <div className="usage-head">
        <span className="usage-label">Last 24h</span>
        <span className="usage-count">
          {fmtK(used)} / {info.usage.approx ? `≈ ${fmtK(limit)}` : fmtK(limit)} tokens
        </span>
      </div>
      <div className="usage-bar">
        <div className={`usage-fill ${fillClass}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="usage-foot">
        Today: {fmtK(info.usage.today_tokens)} · resets {info.usage.resets || '—'} · this app's usage only
      </div>
    </div>
  );
}
