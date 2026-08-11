import { useCallback, useEffect, useState } from 'react'
import { profiles as profilesApi } from '../api/client'
import type { BuildCvConfig, SearchConfig } from '../api/types'

export const BUILD_CV_INSTRUCTIONS_MAX_LENGTH = 500

export const DEFAULT_BUILD_CV_CONFIG: BuildCvConfig = {
  experience_positioning: 'balanced',
  additional_instructions: '',
}

function normalizeInstructions(value: string) {
  return value.trim().slice(0, BUILD_CV_INSTRUCTIONS_MAX_LENGTH)
}

export function useBuildCvPositioning(slug: string) {
  const [cfg, setCfg] = useState<SearchConfig | null>(null)
  const [positioning, setPositioning] = useState<BuildCvConfig['experience_positioning']>('balanced')
  const [instructions, setInstructions] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false

    profilesApi.getConfig(slug).then((c: SearchConfig) => {
      if (cancelled) return
      setCfg(c)
      const bc = c.build_cv || DEFAULT_BUILD_CV_CONFIG
      setPositioning(bc.experience_positioning || DEFAULT_BUILD_CV_CONFIG.experience_positioning)
      setInstructions(bc.additional_instructions || '')
    })

    return () => { cancelled = true }
  }, [slug])

  const persist = useCallback(async (
    nextPositioning: BuildCvConfig['experience_positioning'],
    nextInstructions: string,
  ) => {
    if (!cfg || saving) return false

    setSaving(true)
    const normalizedInstructions = normalizeInstructions(nextInstructions)
    const merged: SearchConfig = {
      ...cfg,
      build_cv: {
        experience_positioning: nextPositioning,
        additional_instructions: normalizedInstructions,
      },
    }

    try {
      const res = await profilesApi.saveConfig(slug, merged)
      if (!res.ok) return false
      setCfg(merged)
      setPositioning(nextPositioning)
      setInstructions(normalizedInstructions)
      return true
    } finally {
      setSaving(false)
    }
  }, [cfg, saving, slug])

  const savePositioning = useCallback(async (next: BuildCvConfig['experience_positioning']) => {
    if (next === positioning) return true

    const previous = positioning
    setPositioning(next)
    const ok = await persist(next, instructions)
    if (!ok) setPositioning(previous)
    return ok
  }, [instructions, persist, positioning])

  const saveInstructions = useCallback(() => (
    persist(positioning, instructions)
  ), [instructions, persist, positioning])

  return {
    positioning,
    instructions,
    saving,
    ready: !!cfg,
    setInstructions,
    savePositioning,
    saveInstructions,
  }
}
