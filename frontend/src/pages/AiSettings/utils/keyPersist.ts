import { MASKED_KEY } from '../constants';

export function isMaskedKey(value: string): boolean {
  return value.startsWith('••••');
}

export function shouldPersistKey(
  raw: string,
  currentKey: string,
  options?: { saving?: boolean },
): boolean {
  const next = raw.trim();
  if (!next || isMaskedKey(next) || options?.saving) return false;
  if (next === currentKey) return false;
  return true;
}

export function initialKeyValue(key: string, keySet: boolean): string {
  return key || (keySet ? MASKED_KEY : '');
}
