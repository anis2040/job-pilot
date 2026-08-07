import { useState, useEffect } from 'react';
import { SPLIT_MIN } from '../constants';

export function useIsWide() {
  const [wide, setWide] = useState(() => window.innerWidth >= SPLIT_MIN);
  useEffect(() => {
    const handler = () => setWide(window.innerWidth >= SPLIT_MIN);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return wide;
}
