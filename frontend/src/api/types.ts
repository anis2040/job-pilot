export interface MatchInfo {
  matched: string[];
  missing: string[];
  matched_count: number;
  keyword_score: number;   // 0-100 integer
  semantic_score: number;  // 0-100 integer
  score: number;           // 0-100 integer (semantic if available, else keyword)
  score_kind: 'fit' | 'skills';
}

export interface Job {
  job_id: string;
  url: string;
  title: string;
  company: string;
  location: string;
  remote: string;
  experience: string;
  age: string;
  posted: string;
  posted_at: string;
  first_seen_at: string;
  status: 'pending' | 'applied' | 'skipped';
  source: string;
  match: MatchInfo | null;
  resume_status: 'idle' | 'building' | 'done' | 'error';
  resume_stage: string;
  pdf_url: string | null;
  resume_error: string | null;
  cl_status: 'idle' | 'building' | 'done' | 'error';
  cl_stage: string;
  cl_pdf_url: string | null;
  cl_error: string | null;
}

export interface JobDetail extends Job {
  description: string;
  salary_range: string | null;
  employment_type: string | null;
  status_updated_at: string | null;
}

export interface JobCounts {
  pending: number;
  applied: number;
  skipped: number;
}

export interface Profile {
  slug: string;
  name: string;
  label: string;
  initials: string;
  color: string;
  active: boolean;
}

export interface SearchEntry {
  group_id?: string;
  name: string;
  source: string;
  query: string;
  location: string;
  max_pages: number;
  remote: boolean;
  work_styles?: ('Remote' | 'Hybrid' | 'On-site')[];
}

export interface SearchConfig {
  searches: SearchEntry[];
  title_filter: string[];
  blacklist: string[];
  company_blacklist: string[];
}

export interface SaveConfigResult {
  ok: boolean;
  fetch_required?: boolean;
}

export interface UsageInfo {
  last_24h_tokens: number;
  today_tokens: number;
  limit_tpd: number;
  approx: boolean;
  resets: string;
}

export interface ProviderInfo {
  configured: boolean;
  model: string;
  key_set: boolean;
  key: string;
  models: string[];
  usage: UsageInfo | null;
}

export interface AiSettings {
  active_provider: string | null;
  preferred_provider: string | null;
  semantic_match: boolean;
  embeddings_available: boolean;
  providers: Record<string, ProviderInfo>;
}

export interface SetupStatus {
  platform: string;
  /** True when FLASK_DEBUG — enables Node/CLI/pdflatex install UI on setup. */
  debug: boolean;
  has_claude: boolean;
  has_gemini: boolean;
  has_pdflatex: boolean;
  has_node: boolean;
  has_profile: boolean;
  gemini_key_set: boolean;
  groq_key_set: boolean;
  anthropic_key_set: boolean;
  openrouter_key_set: boolean;
  gemini_key: string;
  groq_key: string;
  anthropic_key: string;
  openrouter_key: string;
}

export interface RateLimitInfo {
  provider?: string;
  scope?: string;        // e.g. "TPD" | "TPM"
  used?: number;
  limit?: number;
  retry_seconds?: number;
}

export interface DocumentStatus {
  status: 'idle' | 'building' | 'done' | 'error';
  stage: string;
  pdf_url: string | null;
  error: string | null;
  rate_limit: RateLimitInfo | null;
  preview?: string;
}

export interface FetchStatus {
  status: 'idle' | 'running' | 'done' | 'error';
  message: string;
  source?: string;
  progress?: number;
  total?: number;
  error?: string;
}

export interface AppConstants {
  sources: string[];
  remote_types: string[];
  remote_css: Record<string, string>;
  job_statuses: string[];
  default_blacklist: string[];
}
