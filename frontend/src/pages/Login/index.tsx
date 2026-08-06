import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { auth as authApi } from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { Spinner } from '../../components/ui/Spinner';

export default function LoginPage() {
  const { user, loading } = useAuth();
  const [googleConfigured, setGoogleConfigured] = useState<boolean | null>(null);
  const [authDisabled, setAuthDisabled] = useState(false);

  useEffect(() => {
    authApi.status()
      .then(s => {
        setGoogleConfigured(s.google_configured);
        setAuthDisabled(s.auth_disabled);
      })
      .catch(() => setGoogleConfigured(false));
  }, []);

  if (loading) {
    return (
      <div className="login-page">
        <Spinner />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <span className="app-logo-icon" aria-hidden="true">
            <svg width="40" height="40" viewBox="0 0 20 20" fill="none">
              <defs>
                <linearGradient id="login-logo-g" x1="0" y1="0" x2="20" y2="20" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#6ea8ff" />
                  <stop offset="100%" stopColor="#2dd4bf" />
                </linearGradient>
              </defs>
              <path d="M10 1 L12.1 7.9 L19 10 L12.1 12.1 L10 19 L7.9 12.1 L1 10 L7.9 7.9 Z" fill="url(#login-logo-g)" />
            </svg>
          </span>
          <h1>JobPilot <em>AI</em></h1>
          <p>Sign in to manage your job search, profiles, and tailored documents.</p>
        </div>

        {authDisabled ? (
          <p className="login-hint">
            Auth is disabled for local development. Restart with Google OAuth
            credentials configured to require sign-in.
          </p>
        ) : googleConfigured === false ? (
          <p className="login-hint login-error">
            Google sign-in is not configured on this server. Set{' '}
            <code>GOOGLE_CLIENT_ID</code> and <code>GOOGLE_CLIENT_SECRET</code>.
          </p>
        ) : (
          <a className="btn btn-google" href="/auth/login/google">
            <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3l5.7-5.7C34.2 6.1 29.4 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z" />
              <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.8 1.2 8 3l5.7-5.7C34.2 6.1 29.4 4 24 4 16.3 4 9.6 8.3 6.3 14.7z" />
              <path fill="#4CAF50" d="M24 44c5.2 0 10-2 13.6-5.2l-6.3-5.3C29.3 35.3 26.8 36 24 36c-5.3 0-9.7-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
              <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.3 4.1-4.2 5.5l.1.1 6.3 5.3C39.3 37.3 44 33 44 24c0-1.2-.1-2.3-.4-3.5z" />
            </svg>
            Continue with Google
          </a>
        )}
      </div>
    </div>
  );
}
