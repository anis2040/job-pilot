import { render, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, it, expect, beforeEach } from 'vitest'
import App from '../App'
import { db } from './mocks/handlers'
import { server } from './mocks/server'

// SetupPage fetches its own status on mount; stub it so a redirect there
// doesn't hit an unmocked endpoint. resetDb() in setup.ts restores db before
// each test, so mutations here don't leak.
function stubSetupStatus() {
  server.use(
    http.get('/api/setup/status', () =>
      HttpResponse.json({ python: true, node: true, pdflatex: true, cli: false, providers: {} }),
    ),
  )
}

describe('first-run gate', () => {
  beforeEach(() => {
    // App uses BrowserRouter (real window.location), which persists across
    // tests in jsdom — reset to "/" so each test starts from the root.
    window.history.pushState({}, '', '/')
  })

  it('redirects to the setup wizard when no profiles exist', async () => {
    db.profiles = []
    db.activeSlug = null
    stubSetupStatus()
    render(<App />)
    await waitFor(() => {
      expect(window.location.pathname).toBe('/setup')
    })
  })

  it('does not redirect to setup when at least one profile exists', async () => {
    // db defaults to one profile (resetDb in setup.ts). The gate must let the
    // requested route render instead of bouncing to /setup.
    stubSetupStatus()
    render(<App />)
    // Give the profile fetch time to resolve; the gate must NOT redirect.
    await new Promise(r => setTimeout(r, 50))
    expect(window.location.pathname).not.toBe('/setup')
  })
})

