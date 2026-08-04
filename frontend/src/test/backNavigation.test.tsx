import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { Topbar } from '@/components/layout/Topbar'

describe('settings back navigation', () => {
  it('goes back in history when there is a previous route', async () => {
    render(
      <MemoryRouter initialEntries={['/job/job-1', '/profile-settings/anis']} initialIndex={1}>
        <Routes>
          <Route path="/job/:jobId" element={<div>Job page</div>} />
          <Route path="/profile-settings/:slug" element={<Topbar backTo="/manage-profiles" backLabel="Profiles" title="Anis" />} />
        </Routes>
      </MemoryRouter>
    )

    await userEvent.click(screen.getByRole('button', { name: /profiles/i }))

    expect(screen.getByText('Job page')).toBeInTheDocument()
  })

  it('falls back to the stored route when there is no prior history entry', async () => {
    render(
      <MemoryRouter
        initialEntries={[
          { pathname: '/profile-settings/anis', state: { from: '/job/job-1', fromLabel: 'Job' } },
        ]}
      >
        <Routes>
          <Route path="/job/:jobId" element={<div>Job page</div>} />
          <Route path="/profile-settings/:slug" element={<Topbar backTo="/manage-profiles" backLabel="Profiles" title="Anis" />} />
        </Routes>
      </MemoryRouter>
    )

    await userEvent.click(screen.getByRole('button', { name: /job/i }))

    expect(screen.getByText('Job page')).toBeInTheDocument()
  })
})
