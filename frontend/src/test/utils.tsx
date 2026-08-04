import { type ReactElement } from 'react'
import { render } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from '@/components/ui/Toast'
import { ProfileProvider } from '@/hooks/useProfile'
import DashboardPage from '@/pages/Dashboard/index'
import JobDetailPage from '@/pages/JobDetail/index'
import ProfileSettingsPage from '@/pages/ProfileSettings/index'
import ManageProfilesPage from '@/pages/ManageProfiles/index'
import ProfilesPage from '@/pages/Profiles/index'
import AiSettingsPage from '@/pages/AiSettings/index'
import SetupPage from '@/pages/Setup/index'

/**
 * Render the real application at a given route with real providers, real
 * routing, and real components.  Only the network boundary is mocked (MSW).
 *
 * Use this for integration tests that exercise complete user workflows.
 */
export function renderApp(route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <ProfileProvider>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/job/:jobId" element={<JobDetailPage />} />
            <Route path="/profile-settings/:slug" element={<ProfileSettingsPage />} />
            <Route path="/manage-profiles" element={<ManageProfilesPage />} />
            <Route path="/profiles" element={<ProfilesPage />} />
            <Route path="/ai-settings" element={<AiSettingsPage />} />
            <Route path="/setup" element={<SetupPage />} />
          </Routes>
        </ProfileProvider>
      </ToastProvider>
    </MemoryRouter>
  )
}

/** Render an arbitrary element inside the app providers (Toast + Profile + Router). */
export function renderWithProviders(ui: ReactElement, route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <ProfileProvider>{ui}</ProfileProvider>
      </ToastProvider>
    </MemoryRouter>
  )
}
