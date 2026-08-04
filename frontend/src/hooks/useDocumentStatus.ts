import { useCallback } from 'react';
import { usePolling } from './usePolling';
import { documents } from '../api/client';
import type { DocumentStatus } from '../api/types';

export function useDocumentStatus(
  jobId: string,
  type: 'resume' | 'cover-letter',
  enabled: boolean
) {
  const fetcher = useCallback(
    () => type === 'resume' ? documents.resumeStatus(jobId) : documents.coverLetterStatus(jobId),
    [jobId, type]
  );

  const { data, loading, error } = usePolling<DocumentStatus>(
    fetcher,
    2000,
    enabled,
    d => d.status === 'done' || d.status === 'error'
  );

  return {
    status: data?.status ?? 'idle',
    stage: data?.stage ?? '',
    pdfUrl: data?.pdf_url ?? null,
    error: data?.error ?? error,
    rateLimit: data?.rate_limit ?? null,
    preview: data?.preview ?? null,
    loading,
    isBuilding: data?.status === 'building',
  };
}
