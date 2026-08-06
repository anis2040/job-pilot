import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { ToastProvider } from './components/ui/Toast';
import { ProfileProvider } from './hooks/ProfileProvider';
import { AuthProvider } from './hooks/AuthProvider';
import { useAuth } from './hooks/useAuth';
import { useProfile } from './hooks/useProfile';
import { MatrixBackground } from './components/ui/MatrixBackground';
import { AppHeader } from './components/layout/AppShell';
import { Spinner } from './components/ui/Spinner';
import DashboardPage from './pages/Dashboard';
import JobDetailPage from './pages/JobDetail';
import SetupPage from './pages/Setup';
import ProfilesPage from './pages/Profiles';
import ManageProfilesPage from './pages/ManageProfiles';
import ProfileSettingsPage from './pages/ProfileSettings';
import AiSettingsPage from './pages/AiSettings';
import LoginPage from './pages/Login';

function AuthGate({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="login-page">
        <Spinner />
      </div>
    );
  }
  if (!user && location.pathname !== '/login') {
    return <Navigate to="/login" replace />;
  }
  if (user && location.pathname === '/login') {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

// First-run gate: with no profiles yet, send the user to the setup wizard
// instead of an empty dashboard (mirrors the Flask "/" redirect). Waits for the
// profile list to load so we don't redirect on a transient empty state.
function FirstRunGate({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { profiles, loading } = useProfile();
  const location = useLocation();
  if (!user || location.pathname === '/login') return <>{children}</>;
  if (!loading && profiles.length === 0 && location.pathname !== '/setup') {
    return <Navigate to="/setup" replace />;
  }
  return <>{children}</>;
}

function AppChrome({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (location.pathname === '/login') return <>{children}</>;
  return (
    <>
      <AppHeader />
      {children}
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <MatrixBackground />
      <ToastProvider>
        <AuthProvider>
          <AuthGate>
            <ProfileProvider>
              <AppChrome>
                <FirstRunGate>
                  <Routes>
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/job/:jobId" element={<JobDetailPage />} />
                    <Route path="/setup" element={<SetupPage />} />
                    <Route path="/profiles" element={<ProfilesPage />} />
                    <Route path="/manage-profiles" element={<ManageProfilesPage />} />
                    <Route path="/profile-settings/:slug" element={<ProfileSettingsPage />} />
                    <Route path="/ai-settings" element={<AiSettingsPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </FirstRunGate>
              </AppChrome>
            </ProfileProvider>
          </AuthGate>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
