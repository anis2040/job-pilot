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
})
