import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderApp } from './utils'
import { server } from './mocks/server'
import type { AiSettings } from '@/api/types'

function provider(model: string, models: string[]) {
  return {
    configured: true,
    model,
    key_set: true,
    key: '',
    models,
    usage: null,
  }
}

describe('AI Settings model saves', () => {
  it('saving the Gemini model posts gemini_model and selects Gemini, not Groq', async () => {
    const payloads: unknown[] = []
    let settings: AiSettings = {
      active_provider: 'groq',
      preferred_provider: 'groq',
      semantic_match: false,
      embeddings_available: true,
      providers: {
        groq: provider('llama-3.3-70b-versatile', ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b']),
        anthropic: provider('claude-haiku-4-5', ['claude-haiku-4-5']),
        gemini: provider('gemini-3.5-flash-lite', ['gemini-3.5-flash-lite', 'gemini-3.5-flash']),
        openrouter: provider('meta-llama/llama-3.3-70b-instruct:free', ['meta-llama/llama-3.3-70b-instruct:free', 'openai/gpt-4o']),
        claude: { configured: false, model: 'claude-cli', key_set: false, key: '', models: [], usage: null },
      },
    }
    server.use(
      http.get('/api/ai-settings', () => HttpResponse.json(settings)),
      http.post('/api/ai-settings', async ({ request }) => {
        const payload = await request.json() as Record<string, string>
        payloads.push(payload)
        if (payload.gemini_model) {
          settings = {
            ...settings,
            active_provider: payload.preferred_provider,
            preferred_provider: payload.preferred_provider,
            providers: {
              ...settings.providers,
              gemini: { ...settings.providers.gemini, model: payload.gemini_model },
            },
          }
        } else if (payload.preferred_provider) {
          settings = { ...settings, active_provider: payload.preferred_provider, preferred_provider: payload.preferred_provider }
        }
        return HttpResponse.json({ ok: true, updated: Object.keys(payload) })
      }),
    )

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
    const settings: AiSettings = {
      active_provider: 'groq',
      preferred_provider: 'groq',
      semantic_match: false,
      embeddings_available: true,
      providers: {
        groq: provider('llama-3.3-70b-versatile', ['llama-3.3-70b-versatile']),
        anthropic: provider('claude-haiku-4-5', ['claude-haiku-4-5']),
        gemini: provider('gemini-3.5-flash-lite', ['gemini-3.5-flash-lite']),
        openrouter: provider('google/gemma-4-31b-it:free', [
          'google/gemma-4-31b-it:free',
          'nvidia/nemotron-3-super-120b-a12b:free',
          'anthropic/claude-sonnet-4.5',
          'openai/gpt-4o',
        ]),
        claude: { configured: false, model: 'claude-cli', key_set: false, key: '', models: [], usage: null },
      },
    }
    server.use(
      http.get('/api/ai-settings', () => HttpResponse.json(settings)),
      http.post('/api/ai-settings', async ({ request }) => {
        payloads.push(await request.json())
        return HttpResponse.json({ ok: true, updated: [] })
      }),
    )

    renderApp('/ai-settings')
    const header = await screen.findByRole('button', { name: /OpenRouter/i })
    fireEvent.click(header)
    const card = header.closest('.provider-card') as HTMLElement

    // One dropdown, value is the single active model.
    const select = within(card).getByDisplayValue('google/gemma-4-31b-it:free') as HTMLSelectElement

    // Free/Paid optgroups partition the options.
    const groups = select.querySelectorAll('optgroup')
    expect(Array.from(groups).map(g => g.label)).toEqual(['Free', 'Paid'])
    const optValues = (g: Element) => Array.from(g.querySelectorAll('option')).map(o => (o as HTMLOptionElement).value)
    expect(optValues(groups[0])).toEqual(['google/gemma-4-31b-it:free', 'nvidia/nemotron-3-super-120b-a12b:free'])
    expect(optValues(groups[1])).toEqual(['anthropic/claude-sonnet-4.5', 'openai/gpt-4o'])

    // Choosing a paid model persists it as the openrouter model.
    fireEvent.change(select, { target: { value: 'openai/gpt-4o' } })
    await waitFor(() => expect(payloads.some(p => (p as Record<string, string>).openrouter_model === 'openai/gpt-4o')).toBe(true))
  })
})
