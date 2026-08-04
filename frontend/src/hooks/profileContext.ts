import { createContext } from 'react';
import type { Profile } from '../api/types';

export interface ProfileContextValue {
  active: Profile | null;
  profiles: Profile[];
  loading: boolean;
  switchProfile: (slug: string) => Promise<{ empty: boolean }>;
  refetch: () => Promise<void>;
}

export const ProfileContext = createContext<ProfileContextValue>({
  active: null,
  profiles: [],
  loading: true,
  switchProfile: async () => ({ empty: false }),
  refetch: async () => {},
});
