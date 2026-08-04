const STEPSTONE_SNIPPET_LIMIT = 500;

export function shouldFetchFullDescription(job: { job_id: string; description?: string | null }): boolean {
  const description = (job.description || '').trim();
  if (!description) return true;
  return job.job_id.startsWith('ss_') && description.length < STEPSTONE_SNIPPET_LIMIT;
}
