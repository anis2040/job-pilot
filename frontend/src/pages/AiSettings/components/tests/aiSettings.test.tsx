import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderApp } from '@/test/utils'
import { server } from '@/test/mocks/server'
import type { AiSettings } from '@/api/types'
import { baseAiSettings, provider } from './aiSettingsFixtures'

function setupAiSettingsHandlers(
  initial: AiSettings,
  options?: {
    onSave?: (payload: Record<string, unknown>) => void
    onSaveKey?: (provider: string, key: string) => void
    onTest?: (provider: string) => { ok: boolean; model?: string; latency_ms?: number; error?: string }
  },
) {
  let settings = { ...initial, providers: { ...initial.providers } }
  server.use(
    http.get('/api/ai-settings', () => HttpResponse.json(settings)),
    http.post('/api/ai-settings', async ({ request }) => {
      const payload = await request.json() as Record<string, unknown>
      options?.onSave?.(payload)
      if (payload.gemini_model) {
        settings = {
          ...settings,
          active_provider: payload.preferred_provider as string,
          preferred_provider: payload.preferred_provider as string,
          providers: {
            ...settings.providers,
            gemini: { ...settings.providers.gemini, model: payload.gemini_model as string },
          },
        }
      } else if (payload.openrouter_model) {
        settings = {
          ...settings,
          providers: {
            ...settings.providers,
            openrouter: { ...settings.providers.openrouter, model: payload.openrouter_model as string },
          },
        }
      } else if (payload.preferred_provider) {
        settings = {
          ...settings,
          active_provider: payload.preferred_provider as string,
          preferred_provider: payload.preferred_provider as string,
        }
      } else if (typeof payload.semantic_match === 'boolean') {
        settings = { ...settings, semantic_match: payload.semantic_match }
      }
      return HttpResponse.json({ ok: true, updated: Object.keys(payload) })
    }),
    http.post('/api/setup/save-groq-key', async ({ request }) => {
      const { key } = await request.json() as { key: string }
      options?.onSaveKey?.('groq', key)
      settings = {
        ...settings,
        providers: {
          ...settings.providers,
          groq: { ...settings.providers.groq, key_set: true, key: '' },
        },
      }
      return HttpResponse.json({ ok: true })
    }),
    http.post('/api/setup/save-anthropic-key', async ({ request }) => {
      const { key } = await request.json() as { key: string }
      options?.onSaveKey?.('anthropic', key)
      settings = {
        ...settings,
        providers: {
          ...settings.providers,
          anthropic: { ...settings.providers.anthropic, key_set: true, key: '' },
        },
      }
      return HttpResponse.json({ ok: true })
    }),
    http.post('/api/ai-settings/test', async ({ request }) => {
      const { provider: pid } = await request.json() as { provider: string }
      const res = options?.onTest?.(pid) ?? { ok: true, model: 'test-model', latency_ms: 100 }
      return HttpResponse.json(res)
    }),
  )
  return () => settings
}

describe('AI Settings model saves', () => {
  it('saving the Gemini model posts gemini_model and selects Gemini, not Groq', async () => {
    const payloads: unknown[] = []
    setupAiSettingsHandlers(baseAiSettings(), {
      onSave: p => payloads.push(p),
    })

    renderApp('/ai-settings')
    const geminiHeader = await screen.findByRole('button', { name: /Gemini/i })
    fireEvent.click(geminiHeader)

    const geminiCard = geminiHeader.closest('.provider-card') as HTMLElement
    const select = within(geminiCard).getByDisplayValue('gemini-3.5-flash-lite') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'gemini-3.5-flash' } })

    await waitFor(() => expect(payloads.some(p => Boolean((p as Record<string, string>).gemini_model))).toBe(true))
    const modelPayload = payloads.find(p => Boolean((p as Record<string, string>).gemini_model)) as Record<string, string>
    expect(modelPayload).toEqual({ gemini_model: 'gemini-3.5-flash', preferred_provider: 'gemini' })
    expect(modelPayload).not.toHaveProperty('groq_model')
    const banner = await waitFor(() => document.querySelector('.active-banner') as HTMLElement)
    expect(within(banner).getByText('Gemini')).toBeInTheDocument()
    expect(within(banner).getByText(/gemini-3.5-flash/)).toBeInTheDocument()
  })

  it('OpenRouter card groups models into Free and Paid optgroups in one dropdown', async () => {
    const payloads: unknown[] = []
    const settings = baseAiSettings({
      providers: {
        ...baseAiSettings().providers,
        openrouter: provider('google/gemma-4-31b-it:free', [
          'google/gemma-4-31b-it:free',
          'nvidia/nemotron-3-super-120b-a12b:free',
          'anthropic/claude-sonnet-4.5',
          'openai/gpt-4o',
        ]),
      },
    })
    setupAiSettingsHandlers(settings, { onSave: p => payloads.push(p) })

    renderApp('/ai-settings')
    const header = await screen.findByRole('button', { name: /OpenRouter/i })
    fireEvent.click(header)
    const card = header.closest('.provider-card') as HTMLElement

    const select = within(card).getByDisplayValue('google/gemma-4-31b-it:free') as HTMLSelectElement
    const groups = select.querySelectorAll('optgroup')
    expect(Array.from(groups).map(g => g.label)).toEqual(['Free', 'Paid'])
    const optValues = (g: Element) => Array.from(g.querySelectorAll('option')).map(o => (o as HTMLOptionElement).value)
    expect(optValues(groups[0])).toEqual(['google/gemma-4-31b-it:free', 'nvidia/nemotron-3-super-120b-a12b:free'])
    expect(optValues(groups[1])).toEqual(['anthropic/claude-sonnet-4.5', 'openai/gpt-4o'])

    fireEvent.change(select, { target: { value: 'openai/gpt-4o' } })
    await waitFor(() => expect(payloads.some(p => (p as Record<string, string>).openrouter_model === 'openai/gpt-4o')).toBe(true))
  })
})

describe('AI Settings provider selection', () => {
  it('clicking a provider card saves preferred_provider', async () => {
    const payloads: unknown[] = []
    setupAiSettingsHandlers(baseAiSettings(), { onSave: p => payloads.push(p) })

    renderApp('/ai-settings')
    const geminiHeader = await screen.findByRole('button', { name: /Gemini/i })
    fireEvent.click(geminiHeader)

    await waitFor(() => expect(payloads.some(p => (p as Record<string, string>).preferred_provider === 'gemini')).toBe(true))
    expect(geminiHeader.closest('.provider-card')).toHaveClass('is-preferred')
  })
})

describe('AI Settings key save', () => {
  it('saves key on blur with a new value', async () => {
    const savedKeys: { provider: string; key: string }[] = []
    setupAiSettingsHandlers(baseAiSettings(), {
      onSaveKey: (p, k) => savedKeys.push({ provider: p, key: k }),
    })

    renderApp('/ai-settings')
    const anthropicHeader = await screen.findByRole('button', { name: /Claude \(API\)/i })
    fireEvent.click(anthropicHeader)
    const card = anthropicHeader.closest('.provider-card') as HTMLElement
    const input = within(card).getByLabelText('API Key') as HTMLInputElement

    fireEvent.change(input, { target: { value: 'sk-ant-new_test_key' } })
    fireEvent.blur(input)

    await waitFor(() => expect(savedKeys).toEqual([{ provider: 'anthropic', key: 'sk-ant-new_test_key' }]))
    await waitFor(() => expect(within(card).getByText('Key saved')).toBeInTheDocument())
  })

  it('does not save masked placeholder key on blur', async () => {
    const savedKeys: { provider: string; key: string }[] = []
    setupAiSettingsHandlers(baseAiSettings(), {
      onSaveKey: (p, k) => savedKeys.push({ provider: p, key: k }),
    })

    renderApp('/ai-settings')
    const anthropicHeader = await screen.findByRole('button', { name: /Claude \(API\)/i })
    fireEvent.click(anthropicHeader)
    const card = anthropicHeader.closest('.provider-card') as HTMLElement
    const input = within(card).getByLabelText('API Key') as HTMLInputElement

    fireEvent.blur(input)
    await waitFor(() => expect(savedKeys).toHaveLength(0))
  })
})

describe('AI Settings test connection', () => {
  it('shows success result after test', async () => {
    setupAiSettingsHandlers(baseAiSettings(), {
      onTest: () => ({ ok: true, model: 'llama-3.3-70b-versatile', latency_ms: 250 }),
    })

    renderApp('/ai-settings')
    const anthropicHeader = await screen.findByRole('button', { name: /Claude \(API\)/i })
    fireEvent.click(anthropicHeader)
    const card = anthropicHeader.closest('.provider-card') as HTMLElement
    fireEvent.click(within(card).getByRole('button', { name: 'Test connection' }))

    await waitFor(() => expect(within(card).getByText(/OK · llama-3\.3-70b-versatile · 250ms/)).toBeInTheDocument())
  })

  it('shows error result when test fails', async () => {
    setupAiSettingsHandlers(baseAiSettings(), {
      onTest: () => ({ ok: false, error: 'Invalid API key' }),
    })

    renderApp('/ai-settings')
    const anthropicHeader = await screen.findByRole('button', { name: /Claude \(API\)/i })
    fireEvent.click(anthropicHeader)
    const card = anthropicHeader.closest('.provider-card') as HTMLElement
    fireEvent.click(within(card).getByRole('button', { name: 'Test connection' }))

    await waitFor(() => expect(within(card).getByText('Invalid API key')).toBeInTheDocument())
  })

  it('shows error result when test throws', async () => {
    setupAiSettingsHandlers(baseAiSettings())
    server.use(
      http.post('/api/ai-settings/test', () => HttpResponse.error()),
    )

    renderApp('/ai-settings')
    const anthropicHeader = await screen.findByRole('button', { name: /Claude \(API\)/i })
    fireEvent.click(anthropicHeader)
    const card = anthropicHeader.closest('.provider-card') as HTMLElement
    fireEvent.click(within(card).getByRole('button', { name: 'Test connection' }))

    await waitFor(() => expect(within(card).getByText('Connection test failed')).toBeInTheDocument())
    expect(within(card).getByRole('button', { name: 'Test connection' })).not.toBeDisabled()
  })
})

describe('AI Settings semantic matching', () => {
  it('toggles semantic matching when embeddings are available', async () => {
    const payloads: unknown[] = []
    setupAiSettingsHandlers(baseAiSettings(), { onSave: p => payloads.push(p) })

    renderApp('/ai-settings')
    const toggle = await screen.findByRole('checkbox') as HTMLInputElement
    expect(toggle.disabled).toBe(false)
    expect(toggle.checked).toBe(false)

    fireEvent.click(toggle)
    await waitFor(() => expect(payloads.some(p => (p as Record<string, boolean>).semantic_match === true)).toBe(true))
    await waitFor(() => expect(toggle.checked).toBe(true))
  })

  it('disables semantic toggle when embeddings are unavailable', async () => {
    setupAiSettingsHandlers(baseAiSettings({ embeddings_available: false }))

    renderApp('/ai-settings')
    const toggle = await screen.findByRole('checkbox') as HTMLInputElement
    expect(toggle.disabled).toBe(true)
    expect(toggle.checked).toBe(false)
    expect(screen.getByText(/Requires a Gemini API key/)).toBeInTheDocument()
  })
})

describe('AI Settings usage strip', () => {
  it('renders usage strip when usage data is present', async () => {
    setupAiSettingsHandlers(baseAiSettings({
      providers: {
        ...baseAiSettings().providers,
        groq: provider('llama-3.3-70b-versatile', ['llama-3.3-70b-versatile'], {
          usage: {
            last_24h_tokens: 50000,
            today_tokens: 12000,
            limit_tpd: 100000,
            approx: false,
            resets: 'midnight UTC',
          },
        }),
      },
    }))

    renderApp('/ai-settings')
    const groqHeader = await screen.findByRole('button', { name: /Groq/i })
    const card = groqHeader.closest('.provider-card') as HTMLElement

    await waitFor(() => expect(within(card).getByText('Last 24h')).toBeInTheDocument())
    expect(within(card).getByText(/50k \/ 100k tokens/i)).toBeInTheDocument()
    expect(within(card).getByText(/resets midnight UTC/)).toBeInTheDocument()
  })
})
