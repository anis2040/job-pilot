import { useEffect, useState } from 'react';
import type { ProviderInfo } from '../../../api/types';
import { PROVIDER_META } from '../constants';
import { initialKeyValue, shouldPersistKey } from '../utils/keyPersist';
import { useTransientAlert } from '../hooks/useTransientAlert';

export function ApiKeyField({
  pid,
  info,
  onSaveKey,
}: {
  pid: string;
  info: ProviderInfo;
  onSaveKey: (pid: string, key: string) => Promise<boolean>;
}) {
  const meta = PROVIDER_META[pid] ?? { label: pid, sub: '', badge: '', badgeClass: 'badge', placeholder: '' };
  const [keyVal, setKeyVal] = useState(() => initialKeyValue(info.key, info.key_set));
  const [showKey, setShowKey] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const { alert, fading, setAlert } = useTransientAlert();

  useEffect(() => {
    setKeyVal(initialKeyValue(info.key, info.key_set));
  }, [info.key, info.key_set]);

  useEffect(() => {
    setAlert(null);
  }, [pid, setAlert]);

  const persistKey = async (raw: string) => {
    if (!shouldPersistKey(raw, info.key, { saving: savingKey })) return;
    const next = raw.trim();
    setSavingKey(true);
    setAlert({ kind: 'neutral', text: 'Saving key…' });
    try {
      const ok = await onSaveKey(pid, next);
      setAlert(ok
        ? { kind: 'ok', text: 'Key saved' }
        : { kind: 'err', text: 'Failed to save key' });
    } finally {
      setSavingKey(false);
    }
  };

  return (
    <div className="input-group">
      <label htmlFor={`api-key-${pid}`}>API Key</label>
      <div className="input-row">
        <input
          id={`api-key-${pid}`}
          type={showKey ? 'text' : 'password'}
          value={keyVal}
          placeholder={meta.placeholder}
          autoComplete="off"
          onChange={e => {
            setKeyVal(e.target.value);
            if (alert && alert.kind !== 'neutral') setAlert(null);
          }}
          onPaste={e => {
            const pasted = e.clipboardData.getData('text');
            setKeyVal(pasted);
            queueMicrotask(() => { void persistKey(pasted); });
          }}
          onBlur={() => { void persistKey(keyVal); }}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              void persistKey(keyVal);
            }
          }}
          onClick={e => e.stopPropagation()}
        />
        <button
          className="btn btn-ghost btn-sm"
          type="button"
          onClick={e => { e.stopPropagation(); setShowKey(s => !s); }}
        >
          {showKey ? '🙈' : '👁'}
        </button>
      </div>
      <div className="sub text-xs" style={{ marginTop: 6 }}>
        Paste to save instantly, or type and click away.
        {meta.keyUrl && (
          <> · <a href={meta.keyUrl} target="_blank" rel="noopener noreferrer">Get API key ↗</a></>
        )}
      </div>
      <div
        className={`alert-slot${alert ? ' is-visible' : ''}${fading ? ' is-fading' : ''}`}
        aria-live="polite"
      >
        {alert && (
          <div
            className={`alert${alert.kind === 'ok' ? ' alert-ok' : alert.kind === 'err' ? ' alert-error' : ''}${fading ? ' is-fading' : ''}`}
            role="status"
          >
            {alert.text}
          </div>
        )}
      </div>
    </div>
  );
}
