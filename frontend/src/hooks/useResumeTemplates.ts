import { useEffect, useState } from 'react';
import { documents } from '../api/client';
import type { ResumeTemplate } from '../api/types';
import { DEFAULT_RESUME_TEMPLATE_ID } from '../constants/resumeTemplates';

export function useResumeTemplates() {
  const [templates, setTemplates] = useState<ResumeTemplate[]>([]);
  const [defaultTemplateId, setDefaultTemplateId] = useState(DEFAULT_RESUME_TEMPLATE_ID);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.resolve(documents.templates())
      .then(data => {
        if (cancelled) return;
        const nextTemplates = data?.templates || [];
        setTemplates(nextTemplates);
        setDefaultTemplateId(data?.default_template_id || nextTemplates[0]?.id || DEFAULT_RESUME_TEMPLATE_ID);
      })
      .catch(() => {
        if (!cancelled) setTemplates([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  return { templates, defaultTemplateId, loading };
}
