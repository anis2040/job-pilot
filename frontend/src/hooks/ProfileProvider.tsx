import { useState, useCallback, useEffect, type ReactNode } from 'react';
import { profiles as profilesApi } from '../api/client';
import type { Profile } from '../api/types';
import { ProfileContext } from './profileContext';

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<Profile | null>(null);
  const [profileList, setProfileList] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const { profiles, active_slug } = await profilesApi.list();
      setProfileList(profiles);
      setActive(profiles.find(p => p.slug === active_slug) ?? null);
    } catch {
      // non-fatal - app still works
    }
  }, []);

  useEffect(() => {
    refetch().finally(() => setLoading(false));
  }, [refetch]);

  const switchProfile = useCallback(async (slug: string) => {
    const res = await profilesApi.switch(slug);
    await refetch();
    return { empty: !!res.empty };
  }, [refetch]);

  return (
    <ProfileContext.Provider value={{ active, profiles: profileList, loading, switchProfile, refetch }}>
      {children}
    </ProfileContext.Provider>
  );
}
