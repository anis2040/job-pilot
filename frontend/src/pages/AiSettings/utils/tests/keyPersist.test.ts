import { describe, expect, it } from 'vitest';
import { shouldPersistKey, isMaskedKey, initialKeyValue } from '@/pages/AiSettings/utils/keyPersist';
import { MASKED_KEY } from '@/pages/AiSettings/constants';

describe('keyPersist', () => {
  it('detects masked keys', () => {
    expect(isMaskedKey('••••••••••••••••')).toBe(true);
    expect(isMaskedKey('gsk_real_key')).toBe(false);
  });

  it('returns masked placeholder when key is set but empty', () => {
    expect(initialKeyValue('', true)).toBe(MASKED_KEY);
    expect(initialKeyValue('', false)).toBe('');
    expect(initialKeyValue('gsk_abc', true)).toBe('gsk_abc');
  });

  it('shouldPersistKey rejects empty, masked, unchanged, and while saving', () => {
    expect(shouldPersistKey('', 'existing')).toBe(false);
    expect(shouldPersistKey('  ', 'existing')).toBe(false);
    expect(shouldPersistKey(MASKED_KEY, '')).toBe(false);
    expect(shouldPersistKey('same-key', 'same-key')).toBe(false);
    expect(shouldPersistKey('new-key', 'old-key', { saving: true })).toBe(false);
  });

  it('shouldPersistKey accepts a new trimmed key', () => {
    expect(shouldPersistKey('  gsk_new  ', 'old-key')).toBe(true);
  });
});
