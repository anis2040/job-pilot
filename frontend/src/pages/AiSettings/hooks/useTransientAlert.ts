import { useCallback, useEffect, useState } from 'react';
import type { KeyAlert } from '../types';

export const ALERT_FADE_MS = 2200;
export const ALERT_CLEAR_MS = 2600;

export function useTransientAlert() {
  const [alert, setAlertState] = useState<KeyAlert | null>(null);
  const [fading, setFading] = useState(false);

  const setAlert = useCallback((next: KeyAlert | null) => {
    setAlertState(next);
    if (!next) setFading(false);
  }, []);

  useEffect(() => {
    if (!alert || alert.kind === 'neutral') {
      setFading(false);
      return;
    }
    setFading(false);
    const fadeTimer = window.setTimeout(() => setFading(true), ALERT_FADE_MS);
    const clearTimer = window.setTimeout(() => {
      setAlertState(null);
      setFading(false);
    }, ALERT_CLEAR_MS);
    return () => {
      window.clearTimeout(fadeTimer);
      window.clearTimeout(clearTimer);
    };
  }, [alert]);

  return { alert, fading, setAlert };
}
