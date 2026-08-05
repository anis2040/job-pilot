import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { ToastProvider } from './components/ui/Toast';
import { ProfileProvider } from './hooks/ProfileProvider';
import { useProfile } from './hooks/useProfile';
import { MatrixBackground } from './components/ui/MatrixBackground';
import { AppHeader } from './components/layout/AppShell';
import DashboardPage from './pages/Dashboard';
import JobDetailPage from './pages/JobDetail';
import SetupPage from './pages/Setup';
import ProfilesPage from './pages/Profiles';
import ManageProfilesPage from './pages/ManageProfiles';
import ProfileSettingsPage from './pages/ProfileSettings';
import AiSettingsPage from './pages/AiSettings';

// First-run gate: with no profiles yet, send the user to the setup wizard
// instead of an empty dashboard (mirrors the Flask "/" redirect). Waits for the
// profile list to load so we don't redirect on a transient empty state.
function FirstRunGate({ children }: { children: ReactNode }) {
  const { profiles, loading } = useProfile();
  const location = useLocation();
  if (!loading && profiles.length === 0 && location.pathname !== '/setup') {
    return <Navigate to="/setup" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <MatrixBackground />
      <ToastProvider>
        <ProfileProvider>
          <AppHeader />
          <FirstRunGate>
            <Routes>
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
        </ProfileProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
