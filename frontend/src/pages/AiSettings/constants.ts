import { setup } from '../../api/client';

export const MASKED_KEY = '••••••••••••••••';

export const PROVIDER_META: Record<string, {
  label: string;
  sub: string;
  badge: string;
  badgeClass: string;
  placeholder: string;
  noKey?: string;
  keyUrl?: string;
}> = {
  groq: { label: 'Groq', sub: 'Free API key · fast LLaMA models', badge: 'Free tier', badgeClass: 'badge badge-green', placeholder: 'gsk_…', keyUrl: 'https://console.groq.com/keys' },
  anthropic: { label: 'Claude (API)', sub: 'Anthropic API key · Claude models', badge: 'API key', badgeClass: 'badge', placeholder: 'sk-ant-…', keyUrl: 'https://console.anthropic.com/settings/keys' },
  gemini: { label: 'Gemini', sub: 'Google AI Studio key · Gemini models', badge: 'Free tier', badgeClass: 'badge badge-green', placeholder: 'AIza…', keyUrl: 'https://aistudio.google.com/app/apikey' },
  openrouter: { label: 'OpenRouter', sub: 'One key, many models · incl. free-tier', badge: 'Free tier', badgeClass: 'badge badge-green', placeholder: 'sk-or-…', keyUrl: 'https://openrouter.ai/keys' },
  claude: { label: 'Claude Pro', sub: 'Uses local Claude CLI (claude.ai subscription)', badge: 'CLI', badgeClass: 'badge', placeholder: '', noKey: 'No CLI' },
};

export const KEY_SAVE: Record<string, (key: string) => Promise<{ ok: boolean }>> = {
  groq: k => setup.saveGroqKey(k),
  anthropic: k => setup.saveAnthropicKey(k),
  gemini: k => setup.saveGeminiKey(k),
  openrouter: k => setup.saveOpenrouterKey(k),
};
