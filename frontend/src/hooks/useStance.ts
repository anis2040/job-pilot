import { useState, useEffect } from 'react';
import { profiles as profilesApi } from '../api/client';
import { useProfile } from './useProfile';
import type { BuildCvConfig, SearchConfig } from '../api/types';

export function useStance() {
  const { active } = useProfile();
  const slug = active?.slug ?? null;
  const [fullCfg, setFullCfg] = useState<SearchConfig | null>(null);
  const [stance, setStance] = useState<BuildCvConfig['experience_positioning']>('balanced');

  useEffect(() => {
    if (!slug) return;
    profilesApi.getConfig(slug).then(c => {
      setFullCfg(c);
      setStance(c.build_cv?.experience_positioning ?? 'balanced');
    });
  }, [slug]);

  const saveStance = async (next: BuildCvConfig['experience_positioning']) => {
    if (!slug || !fullCfg) return;
    setStance(next);
    const merged: SearchConfig = {
      ...fullCfg,
      build_cv: {
        experience_positioning: next,
        additional_instructions: fullCfg.build_cv?.additional_instructions ?? '',
      },
    };
    const res = await profilesApi.saveConfig(slug, merged);
    if (res.ok) setFullCfg(merged);
  };

  return { stance, saveStance, ready: !!fullCfg };
}
