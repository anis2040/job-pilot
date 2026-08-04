import type {
  Job, JobCounts, JobDetail, Profile, SearchConfig, AiSettings,
  SetupStatus, DocumentStatus, FetchStatus, AppConstants,
} from './types';

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
  return res.json();
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`POST ${url} → ${res.status}`);
  return res.json();
}

// ── Jobs ─────────────────────────────────────────────────────────────────────

const jobListRequests = new Map<string, Promise<Job[]>>();

function listJobs(status: string): Promise<Job[]> {
  const existing = jobListRequests.get(status);
  if (existing) return existing;

  const request = get<Job[]>(`/api/jobs?status=${encodeURIComponent(status)}`)
    .finally(() => jobListRequests.delete(status));
  jobListRequests.set(status, request);
  return request;
}

export const jobs = {
  list: listJobs,
  counts: () => get<JobCounts>('/api/job-counts'),
  get: (jobId: string) => get<JobDetail>(`/api/job/${jobId}`),
  description: (jobId: string) => get<{ description: string; remote: string; match: unknown }>(`/api/job/${jobId}/description`),
  similar: (jobId: string) => get<Job[]>(`/api/jobs/similar/${jobId}`),
  setStatus: (jobId: string, status: string) => post<{ ok: boolean }>(`/api/job-status/${jobId}/${status}`),
  clear: () => post<{ ok: boolean }>('/api/jobs/clear'),
};

// ── Documents ─────────────────────────────────────────────────────────────────

export const documents = {
  buildResume: (jobId: string) => post<{ status: string }>(`/api/resume/${jobId}`),
  resumeStatus: (jobId: string) => get<DocumentStatus>(`/api/resume-status/${jobId}`),
  buildCoverLetter: (jobId: string) => post<{ status: string }>(`/api/cover-letter/${jobId}`),
  coverLetterStatus: (jobId: string) => get<DocumentStatus>(`/api/cover-letter-status/${jobId}`),
};

// ── Fetch (scraping) ──────────────────────────────────────────────────────────

export const fetcher = {
  trigger: () => post<{ status: string }>('/api/fetch'),
  status: () => get<FetchStatus>('/api/fetch-status'),
};

// ── Profiles ──────────────────────────────────────────────────────────────────

export const profiles = {
  list: () => get<{ profiles: Profile[]; active_slug: string | null }>('/api/profiles'),
  active: () => get<{ active: Profile | null }>('/api/profiles/active'),
  create: () => post<{ ok: boolean; slug: string }>('/api/profiles/new'),
  switch: (slug: string) => post<{ ok: boolean; slug: string; empty: boolean }>(`/api/profiles/switch/${slug}`),
  delete: (slug: string) => post<{ ok: boolean }>(`/api/profiles/delete/${slug}`),
  setLabel: (slug: string, label: string) => post<{ ok: boolean }>(`/api/profiles/${slug}/label`, { label }),
  getMarkdown: (slug: string) => get<{ content: string }>(`/api/profiles/${slug}/profile-md`),
  saveMarkdown: (slug: string, content: string) => post<{ ok: boolean }>(`/api/profiles/${slug}/profile-md`, { content }),
  getConfig: (slug: string) => get<SearchConfig>(`/api/profiles/${slug}/config`),
  saveConfig: (slug: string, config: SearchConfig) => post<{ ok: boolean }>(`/api/profiles/${slug}/config`, config),
  clearJobs: (slug: string) => post<{ ok: boolean }>(`/api/profiles/${slug}/clear-jobs`),
};

// ── Config (active profile) ───────────────────────────────────────────────────

export const config = {
  get: () => get<SearchConfig>('/api/config'),
  save: (cfg: SearchConfig) => post<{ ok: boolean }>('/api/config', cfg),
};

// ── AI Settings ───────────────────────────────────────────────────────────────

export const aiSettings = {
  get: () => get<AiSettings>('/api/ai-settings'),
  save: (settings: unknown) => post<{ ok: boolean; updated: string[] }>('/api/ai-settings', settings),
  test: (provider: string) => post<{ ok: boolean; model?: string; latency_ms?: number; backend?: string; response?: string; error?: string }>('/api/ai-settings/test', { provider }),
};

// ── Setup ─────────────────────────────────────────────────────────────────────

export const setup = {
  status: () => get<SetupStatus>('/api/setup/status'),
  suggestConfig: () => post<{ ok: boolean; searches: unknown[]; title_filter: string[]; location: string }>('/api/setup/suggest-config'),
  claudeLogin: () => post<{ ok: boolean }>('/api/setup/claude-login'),
  installNode: () => post<{ ok: boolean; output: string }>('/api/setup/install-node'),
  installCli: (provider: string) => post<{ ok: boolean; output: string }>('/api/setup/install-cli', { provider }),
  installPdflatex: () => post<{ ok: boolean; output: string }>('/api/setup/install-pdflatex'),
  saveGroqKey: (key: string) => post<{ ok: boolean }>('/api/setup/save-groq-key', { key }),
  saveGeminiKey: (key: string) => post<{ ok: boolean }>('/api/setup/save-gemini-key', { key }),
  saveAnthropicKey: (key: string) => post<{ ok: boolean }>('/api/setup/save-anthropic-key', { key }),
  testProvider: (provider: string) => post<{ ok: boolean; model?: string; latency_ms?: number; error?: string }>('/api/ai-settings/test', { provider }),
  parseResume: async (file: File) => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 90000);
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch('/api/setup/parse-resume', { method: 'POST', body: form, signal: controller.signal });
      const payload = await res.json().catch(() => null) as { error?: string; ok?: boolean; data?: unknown } | null;
      if (!res.ok) throw new Error(payload?.error || `POST /api/setup/parse-resume → ${res.status}`);
      return (payload || { ok: true, data: {} }) as { ok: boolean; data: unknown };
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new Error('Resume extraction timed out. Try a smaller file or another provider.')
      }
      throw error
    } finally {
      window.clearTimeout(timeout);
    }
  },
  saveProfile: (content: string) => post<{ ok: boolean }>('/api/setup/save-profile', { content }),
};

// ── Constants ─────────────────────────────────────────────────────────────────

export const constants = {
  get: () => get<AppConstants>('/api/constants'),
  sources: () => get<string[]>('/api/sources'),
};
