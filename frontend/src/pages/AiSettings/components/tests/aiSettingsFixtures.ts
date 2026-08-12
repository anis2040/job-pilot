import type { AiSettings, ProviderInfo } from '@/api/types';

export function provider(model: string, models: string[], overrides: Partial<ProviderInfo> = {}): ProviderInfo {
  return {
    configured: true,
    model,
    key_set: true,
    key: '',
    models,
    usage: null,
    ...overrides,
  };
}

export function baseAiSettings(overrides: Partial<AiSettings> = {}): AiSettings {
  return {
    active_provider: 'groq',
    preferred_provider: 'groq',
    semantic_match: false,
    embeddings_available: true,
    providers: {
      groq: provider('llama-3.3-70b-versatile', ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b']),
      anthropic: provider('claude-haiku-4-5', ['claude-haiku-4-5']),
      gemini: provider('gemini-3.5-flash-lite', ['gemini-3.5-flash-lite', 'gemini-3.5-flash']),
      openrouter: provider('meta-llama/llama-3.3-70b-instruct:free', [
        'meta-llama/llama-3.3-70b-instruct:free',
        'openai/gpt-4o',
      ]),
      claude: { configured: false, model: 'claude-cli', key_set: false, key: '', models: [], usage: null },
    },
    ...overrides,
  };
}
