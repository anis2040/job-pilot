/**
 * Fixture builders — realistic API payloads aligned with the Flask response
 * schemas (see web.py `_serialize_job`, `/api/fetch-status`, `/api/profiles`).
 *
 * Every builder returns a full, valid object and accepts a partial override so
 * tests only specify the fields relevant to what they're asserting.
 */

import type {
  Job, JobDetail, MatchInfo, Profile, SearchConfig, FetchStatus, DocumentStatus,
} from '@/api/types'

let idCounter = 0
export function resetFixtureIds() { idCounter = 0 }
function nextId(prefix = 'job') { return `${prefix}-${++idCounter}` }

export function buildMatch(overrides: Partial<MatchInfo> = {}): MatchInfo {
  return {
    matched: ['TypeScript', 'React'],
    missing: ['Kubernetes'],
    matched_count: 2,
    keyword_score: 60,
    semantic_score: 72,
    score: 72,
    score_kind: 'fit',
    ...overrides,
  }
}

export function buildJob(overrides: Partial<Job> = {}): Job {
  const id = overrides.job_id ?? nextId()
  return {
    job_id: id,
    url: `https://jobs.example.com/${id}`,
    title: 'Software Engineer',
    company: 'Acme Corp',
    location: 'New York, NY',
    remote: 'Remote',
    experience: '3+ years',
    age: '2d',
    posted: '2 days ago',
    posted_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    first_seen_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    status: 'pending',
    source: 'LinkedIn',
    match: null,
    resume_status: 'idle',
    resume_stage: '',
    pdf_url: null,
    resume_error: null,
    cl_status: 'idle',
    cl_stage: '',
    cl_pdf_url: null,
    cl_error: null,
    ...overrides,
  }
}

export function buildJobDetail(overrides: Partial<JobDetail> = {}): JobDetail {
  return {
    ...buildJob(overrides),
    description: 'We are looking for a talented engineer to join our team.',
    salary_range: null,
    employment_type: null,
    status_updated_at: null,
    ...overrides,
  }
}

export function buildProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    slug: 'default',
    name: 'default',
    label: 'Default',
    initials: 'D',
    color: '#3b82f6',
    active: true,
    ...overrides,
  }
}

export function buildSearchConfig(overrides: Partial<SearchConfig> = {}): SearchConfig {
  return {
    searches: [],
    title_filter: [],
    blacklist: [],
    company_blacklist: [],
    ...overrides,
  }
}

export function buildFetchStatus(overrides: Partial<FetchStatus> = {}): FetchStatus {
  return {
    status: 'idle',
    message: '',
    ...overrides,
  }
}

export function buildDocumentStatus(overrides: Partial<DocumentStatus> = {}): DocumentStatus {
  return {
    status: 'idle',
    stage: '',
    pdf_url: null,
    error: null,
    rate_limit: null,
    ...overrides,
  }
}
