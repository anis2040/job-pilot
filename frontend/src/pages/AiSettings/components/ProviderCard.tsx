import { useEffect, useState } from 'react';
import type { ProviderInfo } from '../../../api/types';
import { Icon } from '../../../components/ui/Icon';
import { PROVIDER_META } from '../constants';
import type { ProviderTestResponse } from '../types';
import { ApiKeyField } from './ApiKeyField';
import { ModelSelect } from './ModelSelect';
import { UsageStrip } from './UsageStrip';

export function ProviderCard({
  pid,
  info,
  isPreferred,
  onSelect,
  onSaveKey,
  onSaveModel,
  onTest,
}: {
  pid: string;
  info: ProviderInfo;
  isPreferred: boolean;
  onSelect: (pid: string) => void;
  onSaveKey: (pid: string, key: string) => Promise<boolean>;
  onSaveModel: (pid: string, model: string) => void;
  onTest: (pid: string) => Promise<ProviderTestResponse>;
}) {
  const meta = PROVIDER_META[pid] ?? { label: pid, sub: '', badge: '', badgeClass: 'badge', placeholder: '' };
  const [expanded, setExpanded] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (isPreferred) setExpanded(true);
  }, [isPreferred]);

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await onTest(pid);
      if (res.ok) setTestResult({ ok: true, msg: `OK · ${res.model} · ${res.latency_ms}ms` });
      else setTestResult({ ok: false, msg: res.error || 'Failed' });
    } catch {
      setTestResult({ ok: false, msg: 'Connection test failed' });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className={`provider-card${isPreferred ? ' is-preferred' : ''}`}>
      <div
        className="card-header"
        role="button"
        aria-expanded={expanded}
        onClick={() => { setExpanded(e => !e); onSelect(pid); }}
      >
        <span className="select-indicator">{isPreferred ? '✓' : ''}</span>
        <div className="card-header-text">
          <h3>{meta.label}</h3>
          <div className="sub">{meta.sub}</div>
        </div>
        {!info.key_set && <span className="badge-no-key">{meta.noKey || 'No key'}</span>}
        <span className={meta.badgeClass}>{meta.badge}</span>
        <Icon
          name={expanded ? 'chevronDown' : 'chevronRight'}
          size={16}
          style={{ transform: expanded ? 'rotate(180deg)' : undefined } as React.CSSProperties}
        />
      </div>

      {expanded && (
        <div className="card-body is-expanded">
          {!meta.noKey && (
            <>
              <ApiKeyField pid={pid} info={info} onSaveKey={onSaveKey} />
              <ModelSelect pid={pid} info={info} onSaveModel={onSaveModel} />
            </>
          )}
          <div className="test-row">
            <button
              className="btn btn-ghost btn-sm"
              onClick={e => { e.stopPropagation(); void handleTest(); }}
              disabled={testing}
            >
              {testing ? 'Testing…' : 'Test connection'}
            </button>
            {testResult && (
              <span className={`test-result ${testResult.ok ? 'ok' : 'err'}`}>{testResult.msg}</span>
            )}
          </div>
          <UsageStrip info={info} />
        </div>
      )}
    </div>
  );
}
