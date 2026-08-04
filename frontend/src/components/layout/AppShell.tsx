import { type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useProfile } from '../../hooks/useProfile';
import { Icon } from '../ui/Icon';
import { ProfileDropdown } from './ProfileDropdown';
import { buildBackState } from '../../utils/backNavigation';

interface AppShellProps {
  children: ReactNode;
  showFetchButton?: boolean;
  onFetch?: () => void;
  fetchRunning?: boolean;
}

export function AppShell({ children, showFetchButton, onFetch, fetchRunning }: AppShellProps) {
  const { active } = useProfile();
  const location = useLocation();
  const backState = buildBackState(location);

  return (
    <>
      <header className="app-header">
        <Link to="/" className="app-logo" aria-label="JobPilot AI home">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4Z"/>
          </svg>
          <span>JobPilot AI</span>
        </Link>

        <div className="app-header-right">
          {showFetchButton && (
            <button
              className={`header-icon-btn fetch-btn${fetchRunning ? ' fetching' : ''}`}
              onClick={onFetch}
              disabled={fetchRunning}
              title={fetchRunning ? 'Fetching…' : 'Fetch Jobs'}
              aria-label={fetchRunning ? 'Fetching jobs' : 'Fetch jobs'}
            >
              <Icon name="refresh" size={17} className={fetchRunning ? 'spin' : ''} />
            </button>
          )}

          <Link
            to="/ai-settings"
            state={backState}
            className={`header-icon-btn${location.pathname === '/ai-settings' ? ' active' : ''}`}
            title="AI Models"
            aria-label="AI Models"
          >
            <Icon name="zap" size={17} />
          </Link>

          {active && (
            <Link
              to={`/profile-settings/${active.slug}`}
              state={backState}
              className={`header-icon-btn${location.pathname.startsWith('/profile-settings') ? ' active' : ''}`}
              title="Settings"
              aria-label="Settings"
            >
              <Icon name="settings" size={17} />
            </Link>
          )}

          <ProfileDropdown />
        </div>
      </header>
      <main className="page-enter" id="main-content">
        {children}
      </main>
    </>
  );
}
