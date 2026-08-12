import { describe, expect, it } from 'vitest';
import { usageBarStats } from '@/pages/AiSettings/utils/usageBar';

describe('usageBarStats', () => {
  const base = {
    last_24h_tokens: 0,
    today_tokens: 0,
    limit_tpd: 1000,
    approx: false,
    resets: 'midnight',
  };

  it('computes pct and empty fillClass below 80%', () => {
    expect(usageBarStats({ ...base, last_24h_tokens: 500 })).toEqual({
      used: 500,
      limit: 1000,
      pct: 50,
      fillClass: '',
    });
  });

  it('uses warn fillClass at 80%+', () => {
    expect(usageBarStats({ ...base, last_24h_tokens: 800 }).fillClass).toBe('warn');
  });

  it('uses full fillClass at 100%+', () => {
    expect(usageBarStats({ ...base, last_24h_tokens: 1000 }).fillClass).toBe('full');
    expect(usageBarStats({ ...base, last_24h_tokens: 1500 }).pct).toBe(100);
  });

  it('handles zero limit', () => {
    expect(usageBarStats({ ...base, limit_tpd: 0, last_24h_tokens: 500 })).toEqual({
      used: 500,
      limit: 0,
      pct: 0,
      fillClass: '',
    });
  });
});
