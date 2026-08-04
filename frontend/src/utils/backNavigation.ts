export interface BackLinkState {
  from: string;
  fromLabel: string;
}

function labelForPath(pathname: string): string {
  if (pathname === '/') return 'Home';
  if (pathname === '/manage-profiles' || pathname === '/profiles') return 'Profiles';
  if (pathname.startsWith('/job/')) return 'Job';
  if (pathname.startsWith('/profile-settings/')) return 'Settings';
  if (pathname === '/ai-settings') return 'AI';
  return 'Back';
}

export function buildBackState(location: { pathname: string; search?: string; hash?: string }): BackLinkState {
  return {
    from: `${location.pathname}${location.search || ''}${location.hash || ''}`,
    fromLabel: labelForPath(location.pathname),
  };
}

export function getBackFallback(state: unknown, fallbackTo: string, fallbackLabel: string) {
  const backState = state as Partial<BackLinkState> | null;
  return {
    to: typeof backState?.from === 'string' && backState.from ? backState.from : fallbackTo,
    label: typeof backState?.fromLabel === 'string' && backState.fromLabel ? backState.fromLabel : fallbackLabel,
  };
}

export function hasPriorHistoryEntry(locationKey?: string) {
  if (typeof window !== 'undefined') {
    const idx = window.history.state?.idx;
    if (typeof idx === 'number') return idx > 0;
  }
  return Boolean(locationKey && locationKey !== 'default');
}
