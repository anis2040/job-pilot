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
          <span className="app-logo-icon" aria-hidden="true">
            <svg width="32" height="32" viewBox="0 0 20 20" fill="none">
              <defs>
                <linearGradient id="logo-g" x1="0" y1="0" x2="20" y2="20" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#6ea8ff"/>
                  <stop offset="100%" stopColor="#2dd4bf"/>
                </linearGradient>
              </defs>
              <path d="M10 1 L12.1 7.9 L19 10 L12.1 12.1 L10 19 L7.9 12.1 L1 10 L7.9 7.9 Z" fill="url(#logo-g)"/>
            </svg>
          </span>
          <span className="app-logo-text">JobPilot <em>AI</em></span>
        </Link>

        <div className="app-header-right">
          {showFetchButton && (
            <button
              className={`header-nav-btn fetch-btn${fetchRunning ? ' fetching' : ''}`}
              onClick={onFetch}
              disabled={fetchRunning}
              aria-label={fetchRunning ? 'Fetching jobs' : 'Fetch jobs'}
            >
              <Icon name="refresh" size={16} className={fetchRunning ? 'spin' : ''} />
              <span>{fetchRunning ? 'Fetching…' : 'Fetch'}</span>
            </button>
          )}

          <Link
            to="/ai-settings"
            state={backState}
            className={`header-nav-btn nav-ai${location.pathname === '/ai-settings' ? ' active' : ''}`}
            aria-label="AI Models"
          >
            <Icon name="zap" size={16} />
            <span>AI Models</span>
          </Link>

          {active && (
            <Link
              to={`/profile-settings/${active.slug}`}
              state={backState}
              className={`header-nav-btn nav-settings${location.pathname.startsWith('/profile-settings') ? ' active' : ''}`}
              aria-label="Settings"
            >
              <Icon name="settings" size={16} />
              <span>Settings</span>
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
