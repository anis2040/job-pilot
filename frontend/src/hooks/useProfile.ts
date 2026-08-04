import { useContext } from 'react';
import { ProfileContext } from './profileContext';

export function useProfile() {
  return useContext(ProfileContext);
}
