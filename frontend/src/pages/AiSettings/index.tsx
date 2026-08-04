import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { aiSettings as aiSettingsApi, setup } from '../../api/client';
import { useToast } from '../../components/ui/Toast';
import { Icon } from '../../components/ui/Icon';
import { fmtK } from '../../utils/format';
import type { AiSettings, ProviderInfo } from '../../api/types';

const PROVIDER_META: Record<string, { label: string; sub: string; badge: string; badgeClass: string; placeholder: string; noKey?: string }> = {
  groq:      { label: 'Groq', sub: 'Free API key · fast LLaMA models', badge: 'Free tier', badgeClass: 'badge badge-green', placeholder: 'gsk_…' },
  anthropic: { label: 'Claude (API)', sub: 'Anthropic API key · Claude models', badge: 'API key', badgeClass: 'badge', placeholder: 'sk-ant-…' },
  gemini:    { label: 'Gemini', sub: 'Google AI Studio key · Gemini models', badge: 'Free tier', badgeClass: 'badge badge-green', placeholder: 'AIza…' },
  claude:    { label: 'Claude Pro', sub: 'Uses local Claude CLI (claude.ai subscription)', badge: 'CLI', badgeClass: 'badge', placeholder: '', noKey: 'No CLI' },
};

const KEY_SAVE: Record<string, (key: string) => Promise<{ ok: boolean }>> = {
  groq:      k => setup.saveGroqKey(k),
  anthropic: k => setup.saveAnthropicKey(k),
  gemini:    k => setup.saveGeminiKey(k),
};

function UsageStrip({ info }: { info: ProviderInfo }) {
  if (!info.usage || !info.key_set) return null;
  const used = info.usage.last_24h_tokens || 0;
  const limit = info.usage.limit_tpd || 0;
  const pct = limit ? Math.min(100, Math.round(used / limit * 100)) : 0;
  const fillClass = pct >= 100 ? 'full' : pct >= 80 ? 'warn' : '';
  return (
    <div className="usage-strip">
      <div className="usage-head">
        <span className="usage-label">Last 24h</span>
        <span className="usage-count">{fmtK(used)} / {info.usage.approx ? `≈ ${fmtK(limit)}` : fmtK(limit)} tokens</span>
      </div>
      <div className="usage-bar"><div className={`usage-fill ${fillClass}`} style={{ width: `${pct}%` }} /></div>
      <div className="usage-foot">Today: {fmtK(info.usage.today_tokens)} · resets {info.usage.resets || '—'} · this app's usage only</div>
    </div>
  );
}

function ProviderCard({
  pid, info, isPreferred, onSelect,
  onSaveKey, onSaveModel, onTest,
}: {
  pid: string; info: ProviderInfo; isPreferred: boolean;
  onSelect: (pid: string) => void;
  onSaveKey: (pid: string, key: string) => void;
  onSaveModel: (pid: string, model: string) => void;
  onTest: (pid: string) => void;
}) {
  const meta = PROVIDER_META[pid] ?? { label: pid, sub: '', badge: '', badgeClass: 'badge', placeholder: '' };
  const [expanded, setExpanded] = useState(false);
  const [keyVal, setKeyVal] = useState(info.key || (info.key_set ? '••••••••••••••••' : ''));
  const [showKey, setShowKey] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    const res = await onTest(pid) as unknown as { ok: boolean; model?: string; latency_ms?: number; error?: string };
    if (res.ok) setTestResult({ ok: true, msg: `OK · ${res.model} · ${res.latency_ms}ms` });
    else setTestResult({ ok: false, msg: res.error || 'Failed' });
    setTesting(false);
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
        <Icon name={expanded ? 'chevronDown' : 'chevronRight'} size={16} style={{ transform: expanded ? 'rotate(180deg)' : undefined } as React.CSSProperties} />
      </div>

      {expanded && (
        <div className="card-body is-expanded">
          {!meta.noKey && (
            <>
              <div className="input-group">
                <label>API Key</label>
                <div className="input-row">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={keyVal}
                    placeholder={meta.placeholder}
                    autoComplete="off"
                    onChange={e => setKeyVal(e.target.value)}
                    onClick={e => e.stopPropagation()}
                  />
                  <button className="btn btn-ghost btn-sm" type="button" onClick={e => { e.stopPropagation(); setShowKey(s => !s); }}>
                    {showKey ? '🙈' : '👁'}
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={e => { e.stopPropagation(); onSaveKey(pid, keyVal); }}>
                    Save
                  </button>
                </div>
              </div>
              <div className="model-row">
                <label>Model</label>
                <select
                  value={info.model}
                  disabled={!info.key_set}
                  onChange={e => onSaveModel(pid, e.target.value)}
                  onClick={e => e.stopPropagation()}
                >
                  {(info.models || []).map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
            </>
          )}
          <div className="test-row">
            <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); handleTest(); }} disabled={testing}>
              {testing ? 'Testing…' : 'Test connection'}
            </button>
            {testResult && <span className={`test-result ${testResult.ok ? 'ok' : 'err'}`}>{testResult.msg}</span>}
          </div>
          <UsageStrip info={info} />
        </div>
      )}
    </div>
  );
}

export default function AiSettingsPage() {
  const [data, setData] = useState<AiSettings | null>(null);
  const [preferred, setPreferred] = useState<string | null>(null);
  const { showToast } = useToast();

  useEffect(() => {
    aiSettingsApi.get().then(d => {
      setData(d);
      setPreferred(d.preferred_provider || d.active_provider || null);
    });
  }, []);

  const handleSelect = async (pid: string) => {
    setPreferred(pid);
    try {
      await aiSettingsApi.save({ preferred_provider: pid });
      const updated = await aiSettingsApi.get();
      setData(updated);
      setPreferred(updated.preferred_provider || updated.active_provider || null);
    } catch {
      showToast('Failed to save preference', 'err');
    }
  };

  const handleSaveKey = async (pid: string, key: string) => {
    const saveFn = KEY_SAVE[pid];
    if (!saveFn) return;
    try {
      const res = await saveFn(key);
      if (res.ok) {
        showToast('Key saved');
        setData(await aiSettingsApi.get());
      } else showToast('Failed to save key', 'err');
    } catch { showToast('Failed to save key', 'err'); }
  };

  const handleSaveModel = async (pid: string, model: string) => {
    // claude uses CLI — no model key to save
    if (pid === 'claude') return;
    try {
      await aiSettingsApi.save({ [`${pid}_model`]: model });
      setData(await aiSettingsApi.get());
      showToast('Model saved');
    } catch { showToast('Failed to save model', 'err'); }
  };

  const handleTest = async (pid: string) => {
    return aiSettingsApi.test(pid);
  };

  const handleSemanticToggle = async (checked: boolean) => {
    try {
      await aiSettingsApi.save({ semantic_match: checked });
      setData(d => d ? { ...d, semantic_match: checked } : d);
      showToast(checked ? 'Smart matching on' : 'Smart matching off');
    } catch { showToast('Failed to update', 'err'); }
  };

  if (!data) return <div className="page-loading"><span className="spinner" /></div>;

  const active = data.active_provider;

  return (
    <>
      <header style={{ padding: 'var(--space-4) var(--space-8)', borderBottom: '1px solid var(--border-faint)', display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
        <Link to="/" style={{ color: 'var(--blue-light)', textDecoration: 'none', fontSize: 'var(--text-base)' }}>← Back</Link>
        <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-white)' }}>⚡ AI Settings</h1>
      </header>

      <main className="page page-enter" id="main-content">
        <div className="page-header">
          <h2>AI Model Settings</h2>
          <p>Click a provider card to switch. Configure API keys and models per provider below.</p>
        </div>

        <div className="active-banner">
          <span className="label">Currently using:</span>
          <span className="provider-name">{active ? (PROVIDER_META[active]?.label ?? active) : 'None configured'}</span>
          {active && data.providers[active]?.model && (
            <span className="model-name">— {data.providers[active].model}</span>
          )}
        </div>

        {Object.entries(data.providers).map(([pid, info]) => (
          <ProviderCard
            key={pid}
            pid={pid}
            info={info}
            isPreferred={preferred === pid}
            onSelect={handleSelect}
            onSaveKey={handleSaveKey}
            onSaveModel={handleSaveModel}
            onTest={handleTest}
          />
        ))}

        <div className="provider-card" id="semantic-card">
          <div className="card-header" style={{ cursor: 'default' }}>
            <div className="card-header-text">
              <h3>Smart job matching</h3>
              <div className="sub">Ranks jobs by overall fit using embeddings</div>
            </div>
            <label className="switch">
              <input
                type="checkbox"
                checked={data.semantic_match && data.embeddings_available}
                disabled={!data.embeddings_available}
                onChange={e => handleSemanticToggle(e.target.checked)}
              />
              <span className="switch-slider" />
            </label>
          </div>
          <div className="card-body is-expanded">
            <p className="semantic-note">
              {!data.embeddings_available
                ? 'Requires a Gemini API key (the only provider here that offers embeddings). Without it, jobs are still matched by skill keywords.'
                : 'Ranks jobs by overall fit (semantic similarity between the job and your profile), on top of the skill-match chips. Cost: a fraction of a cent per job on a paid Gemini key, or free (rate-limited) on a free-tier key — computed once per job and cached.'}
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
