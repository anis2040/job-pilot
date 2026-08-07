import { useState, useCallback, useEffect, useContext, type ReactNode } from 'react';
import { profiles as profilesApi } from '../api/client';
import type { Profile } from '../api/types';
import { ProfileContext } from './profileContext';
import { AuthContext } from './authContext';

export function ProfileProvider({ children }: { children: ReactNode }) {
  // AuthProvider is optional in unit tests; when present, wait for session.
  const auth = useContext(AuthContext);
  const user = auth?.user ?? null;
  const authLoading = auth?.loading ?? false;
  const [active, setActive] = useState<Profile | null>(null);
  const [profileList, setProfileList] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    if (auth && !user) {
      setProfileList([]);
      setActive(null);
      return;
    }
    try {
      const { profiles, active_slug } = await profilesApi.list();
      setProfileList(profiles);
      setActive(profiles.find(p => p.slug === active_slug) ?? null);
    } catch {
      // non-fatal - app still works
    }
  }, [auth, user]);

  useEffect(() => {
    if (authLoading) return;
    setLoading(true);
    refetch().finally(() => setLoading(false));
  }, [refetch, authLoading]);

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
