import '@testing-library/jest-dom'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './mocks/server'
import { resetDb } from './mocks/handlers'

// Start the MSW server once for the whole suite.
// onUnhandledRequest: 'error' surfaces any API call the app makes that we
// haven't modelled — catching URL regressions in client.ts.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

afterEach(() => {
  server.resetHandlers()
  resetDb()
  localStorage.clear()
})

afterAll(() => server.close())
