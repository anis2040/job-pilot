import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './components/ui/Toast';
import { ProfileProvider } from './hooks/ProfileProvider';
import { MatrixBackground } from './components/ui/MatrixBackground';
import DashboardPage from './pages/Dashboard';
import JobDetailPage from './pages/JobDetail';
import SetupPage from './pages/Setup';
import ProfilesPage from './pages/Profiles';
import ManageProfilesPage from './pages/ManageProfiles';
import ProfileSettingsPage from './pages/ProfileSettings';
import AiSettingsPage from './pages/AiSettings';

export default function App() {
  return (
    <BrowserRouter>
      <MatrixBackground />
      <ToastProvider>
        <ProfileProvider>
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
        </ProfileProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
