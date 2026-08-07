import '@testing-library/jest-dom'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './mocks/server'
import { resetDb } from './mocks/handlers'

// Node ≥25 can expose a non-functional localStorage; provide an in-memory stub
// so Auth/Profile providers and Dashboard recent-searches work in tests.
if (typeof globalThis.localStorage === 'undefined' || typeof globalThis.localStorage?.clear !== 'function') {
  const store = new Map<string, string>()
  const mem = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => { store.set(k, String(v)) },
    removeItem: (k: string) => { store.delete(k) },
    clear: () => { store.clear() },
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() { return store.size },
  }
  Object.defineProperty(globalThis, 'localStorage', { value: mem, configurable: true })
}

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
