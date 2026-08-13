import type { UsageInfo } from '../../../api/types';

export function usageBarStats(usage: UsageInfo) {
  const used = usage.last_24h_tokens || 0;
  const limit = usage.limit_tpd || 0;
  const pct = limit ? Math.min(100, Math.round(used / limit * 100)) : 0;
  const fillClass = pct >= 100 ? 'full' : pct >= 80 ? 'warn' : '';
  return { used, limit, pct, fillClass };
}
