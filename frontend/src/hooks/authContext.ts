import { createContext } from 'react';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  picture: string;
  auth_disabled?: boolean;
}

export interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  logout: () => Promise<void>;
  refetch: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
