import { useState, useEffect } from 'react';
import { profiles as profilesApi } from '../api/client';
import { useProfile } from './useProfile';
import type { BuildCvConfig, SearchConfig } from '../api/types';
import { DEFAULT_RESUME_TEMPLATE_ID } from '../constants/resumeTemplates';

export function useStance() {
  const { active } = useProfile();
  const slug = active?.slug ?? null;
  const [fullCfg, setFullCfg] = useState<SearchConfig | null>(null);
  const [stance, setStance] = useState<BuildCvConfig['experience_positioning']>('balanced');
  const [resumeTemplateId, setResumeTemplateId] = useState(DEFAULT_RESUME_TEMPLATE_ID);

  useEffect(() => {
    if (!slug) return;
    profilesApi.getConfig(slug).then(c => {
      setFullCfg(c);
      setStance(c.build_cv?.experience_positioning ?? 'balanced');
      setResumeTemplateId(c.build_cv?.resume_template_id ?? DEFAULT_RESUME_TEMPLATE_ID);
    });
  }, [slug]);

  const saveStance = async (next: BuildCvConfig['experience_positioning']) => {
    if (!slug || !fullCfg) return false;
    const previous = stance;
    setStance(next);
    const merged: SearchConfig = {
      ...fullCfg,
      build_cv: {
        ...(fullCfg.build_cv || {}),
        experience_positioning: next,
        additional_instructions: fullCfg.build_cv?.additional_instructions ?? '',
        resume_template_id: resumeTemplateId,
      },
    };
    const res = await profilesApi.saveConfig(slug, merged);
    if (res.ok) {
      setFullCfg(merged);
      return true;
    }
    setStance(previous);
    return false;
  };

  const saveResumeTemplate = async (next: string) => {
    if (!slug || !fullCfg) return false;
    const previous = resumeTemplateId;
    setResumeTemplateId(next);
    const merged: SearchConfig = {
      ...fullCfg,
      build_cv: {
        ...(fullCfg.build_cv || {}),
        experience_positioning: fullCfg.build_cv?.experience_positioning ?? stance,
        additional_instructions: fullCfg.build_cv?.additional_instructions ?? '',
        resume_template_id: next || DEFAULT_RESUME_TEMPLATE_ID,
      },
    };
    const res = await profilesApi.saveConfig(slug, merged);
    if (res.ok) {
      setFullCfg(merged);
      return true;
    }
    setResumeTemplateId(previous);
    return false;
  };

  return { stance, saveStance, resumeTemplateId, saveResumeTemplate, ready: !!fullCfg };
}
