import { useState, useEffect, useRef, Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import { setup as setupApi, fetcher as fetcherApi } from '../../api/client';
import { useProfile } from '../../hooks/useProfile';
import { useToast } from '../../components/ui/Toast';
import type { SetupStatus } from '../../api/types';
import {
  buildProfileMd, DEFAULT_FORM, EMPTY_EXP,
  type ProfileFormData,
} from '../../utils/profileForm';

// ── Step indicator ─────────────────────────────────────────────────────────────

function StepIndicator({ current, onStepClick }: { current: 1 | 2 | 3; onStepClick?: (n: 1 | 2 | 3) => void }) {
  return (
    <div className="steps" id="steps-indicator">
      {([1, 2, 3] as const).map((n, i) => (
        <Fragment key={n}>
          <div
            className={`step-dot${current === n ? ' active' : current > n ? ' done' : ''}`}
            onClick={() => onStepClick?.(n)}
            style={{ cursor: onStepClick && n !== current ? 'pointer' : 'default' }}
          >
            {n}
          </div>
          {i < 2 && <div className={`step-line${current > n ? ' done' : ''}`} />}
        </Fragment>
      ))}
    </div>
  );
}

// ── Step 1: Prerequisites ──────────────────────────────────────────────────────

function CheckRow({ ok, label, detail, children }: { ok: boolean | null; label: string; detail: string; children?: React.ReactNode }) {
  const icon = ok === null ? '…' : ok ? '✓' : '✗';
  const cls = ok === null ? 'loading' : ok ? 'ok' : 'err';
  return (
    <div className="check-row">
      <div className={`check-icon ${cls}`}>{icon}</div>
      <div className="check-label"><strong>{label}</strong><span>{detail}</span></div>
      {children}
    </div>
  );
}

type ProviderChoice = 'groq' | 'claude' | 'gemini' | null;

function Step1({ onNext }: { onNext: () => void }) {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [provider, setProvider] = useState<ProviderChoice>(null);
  const [keyInput, setKeyInput] = useState('');
  const [actionStatus, setActionStatus] = useState('');
  const [pdfStatus, setPdfStatus] = useState('');
  const [nodeInstallLog, setNodeInstallLog] = useState('');

  useEffect(() => { setupApi.status().then(setStatus); }, []);

  const ready = status && (status.has_claude || status.has_gemini || status.groq_key_set) && status.has_node;

  const handleInstallNode = async () => {
    setNodeInstallLog('Installing…');
    const res = await setupApi.installNode();
    setNodeInstallLog(res.output || (res.ok ? 'Done' : 'Failed'));
    if (res.ok) setStatus(s => s ? { ...s, has_node: true } : s);
  };

  const handleInstallCli = async () => {
    if (!provider) return;
    setActionStatus('Installing…');
    const res = await setupApi.installCli(provider);
    setActionStatus(res.output || (res.ok ? 'Done' : 'Failed'));
    if (res.ok) setStatus(s => s ? { ...s, has_claude: provider === 'claude' || s.has_claude, has_gemini: provider === 'gemini' || s.has_gemini } : s);
  };

  const handleSaveKey = async () => {
    if (!provider || !keyInput.trim()) return;
    setActionStatus('Saving…');
    let res: { ok: boolean };
    if (provider === 'groq') res = await setupApi.saveGroqKey(keyInput.trim());
    else if (provider === 'gemini') res = await setupApi.saveGeminiKey(keyInput.trim());
    else res = { ok: false };
    setActionStatus(res.ok ? '✓ Key saved' : '⚠ Failed to save key');
    if (res.ok) setStatus(s => s ? { ...s, groq_key_set: provider === 'groq' || s.groq_key_set, gemini_key_set: provider === 'gemini' || s.gemini_key_set } : s);
  };

  const handleClaudeLogin = async () => {
    setActionStatus('Opening login…');
    const res = await setupApi.claudeLogin();
    setActionStatus(res.ok ? '✓ Logged in' : '⚠ Failed');
    if (res.ok) setStatus(s => s ? { ...s, has_claude: true } : s);
  };

  const handleInstallPdflatex = async () => {
    setPdfStatus('Installing…');
    const res = await setupApi.installPdflatex();
    setPdfStatus(res.ok ? '✓ Installed' : `⚠ ${res.output}`);
    if (res.ok) setStatus(s => s ? { ...s, has_pdflatex: true } : s);
  };

  return (
    <div id="step-1" className="card">
      <h2>Prerequisites</h2>
      <p className="subtitle">Let's make sure everything needed is installed on your machine.</p>

      <div id="check-list" style={{ marginBottom: 20 }}>
        <CheckRow ok={true} label="Python" detail="Running — you're already here!" />
        <CheckRow ok={status?.has_node ?? null} label="Node.js" detail="Required to install the AI CLI">
          {status && !status.has_node && (
            <div style={{ marginTop: 8 }}>
              <div className="alert alert-error" style={{ marginBottom: 10 }}>
                ⚠ Node.js is not installed. Required to install the AI CLI.
              </div>
              <button className="btn btn-sm btn-ghost" onClick={handleInstallNode}>Install Node.js</button>
              {nodeInstallLog && <pre style={{ fontSize: '0.75rem', marginTop: 6, color: 'var(--text-muted)' }}>{nodeInstallLog}</pre>}
            </div>
          )}
        </CheckRow>
        <CheckRow ok={status ? (status.has_claude || status.has_gemini || status.groq_key_set) : null} label="AI CLI" detail="Claude Code, Gemini CLI, or API key" />
        <CheckRow ok={status?.has_pdflatex ?? null} label="pdflatex" detail="Required to compile resumes to PDF">
          {status && !status.has_pdflatex && (
            <div style={{ marginTop: 8 }}>
              <button className="btn btn-sm btn-ghost" onClick={handleInstallPdflatex}>Install pdflatex</button>
              {pdfStatus && (
                <div className={`alert ${pdfStatus.startsWith('✓') ? 'alert-ok' : 'alert-error'}`} style={{ marginTop: 8 }}>
                  {pdfStatus}
                </div>
              )}
            </div>
          )}
        </CheckRow>
      </div>

      <div style={{ borderTop: '1px solid var(--border-faint)', paddingTop: 'var(--space-5)', marginBottom: 'var(--space-5)' }}>
        <p style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>Choose Your AI</p>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', marginBottom: 'var(--space-3)' }}>The AI generates your tailored resumes and cover letters.</p>
        <div className="provider-grid cols-3">
          {(['groq', 'claude', 'gemini'] as const).map(p => (
            <div key={p} className={`provider-card${provider === p ? ' selected' : ''}`} onClick={() => { setProvider(p); setActionStatus(''); }}>
              <h3>{p === 'groq' ? 'Groq' : p === 'claude' ? 'Claude' : 'Gemini'}</h3>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
                {p === 'groq' && 'Free tier, very fast (~5s). API key from console.groq.com — no credit card.'}
                {p === 'claude' && 'By Anthropic. Free tier available. Login with your Anthropic account.'}
                {p === 'gemini' && 'By Google. Free API key from Google AI Studio. No credit card required.'}
              </p>
            </div>
          ))}
        </div>
        {provider && (
          <div id="provider-action" style={{ marginTop: 12 }}>
            {provider === 'claude' ? (
              <button className="btn btn-primary btn-sm" onClick={handleClaudeLogin}>Login with Claude</button>
            ) : (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="password" placeholder={provider === 'groq' ? 'gsk_…' : 'AIza…'} value={keyInput} onChange={e => setKeyInput(e.target.value)} style={{ flex: 1 }} />
                <button className="btn btn-primary btn-sm" onClick={handleSaveKey}>Save key</button>
                <button className="btn btn-ghost btn-sm" onClick={handleInstallCli}>Install CLI</button>
              </div>
            )}
            {actionStatus && (
              <div className={`alert ${actionStatus.startsWith('✓') ? 'alert-ok' : actionStatus === 'Opening login…' || actionStatus === 'Installing…' || actionStatus === 'Saving…' ? '' : 'alert-error'}`}
                style={{ marginTop: 8 }}>
                {actionStatus}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="footer-nav">
        <span className="step-hint">Step 1 of 3</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={onNext}>Skip →</button>
          <button className="btn btn-primary" onClick={onNext} disabled={!ready}>Continue →</button>
        </div>
      </div>
    </div>
  );
}

// ── Step 2: Profile ────────────────────────────────────────────────────────────

function DynamicList({ items, onChange, placeholder }: { items: string[]; onChange: (items: string[]) => void; placeholder: string }) {
  const set = (i: number, val: string) => { const n = [...items]; n[i] = val; onChange(n); };
  return (
    <div>
      <div className="dynamic-list">
        {items.map((v, i) => (
          <div key={i} className="dynamic-row">
            <input type="text" placeholder={placeholder} value={v} onChange={e => set(i, e.target.value)} />
            <button className="btn-icon" type="button" onClick={() => onChange(items.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
      </div>
      <button className="btn-add-row" type="button" onClick={() => onChange([...items, ''])}>+ Add</button>
    </div>
  );
}

function Step2({ onBack, onNext }: { onBack: () => void; onNext: () => void }) {
  const [form, setForm] = useState<ProfileFormData>(DEFAULT_FORM());
  const [saving, setSaving] = useState(false);
  const [autofillMsg, setAutofillMsg] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  const set = <K extends keyof ProfileFormData>(k: K, v: ProfileFormData[K]) => setForm(f => ({ ...f, [k]: v }));

  const handleAutofill = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setAutofillMsg('Extracting…');
    try {
      const res = await setupApi.parseResume(file) as { ok: boolean; data: Partial<ProfileFormData>; error?: string };
      if (!res.ok) { setAutofillMsg(`⚠ ${res.error}`); return; }
      setForm(f => ({ ...f, ...res.data }));
      setAutofillMsg(`✓ Filled from ${file.name}`);
    } catch { setAutofillMsg('⚠ Upload failed'); }
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleSave = async () => {
    if (!form.name) { showToast('Please enter your full name', 'err'); return; }
    if (!form.email) { showToast('Please enter your email', 'err'); return; }
    setSaving(true);
    const res = await setupApi.saveProfile(buildProfileMd(form));
    setSaving(false);
    if (res.ok) onNext();
    else showToast('Failed to save profile', 'err');
  };

  const AUTH_OPTIONS = ['', 'US Citizen — no sponsorship required', 'Green Card holder — legally authorized to work in the U.S.', 'Authorized to work in the US · No sponsorship required', 'Requires H-1B sponsorship'];

  return (
    <div id="step-2" className="card">
      <h2>Your Profile</h2>
      <p className="subtitle">Fill in your details below, or upload your existing resume to autofill the form.</p>

      <div className="autofill-bar">
        <label className="btn btn-ghost btn-sm" style={{ cursor: 'pointer' }}>
          📎 Autofill from resume
          <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" style={{ display: 'none' }} onChange={handleAutofill} />
        </label>
        {autofillMsg && (
          <div className={`alert ${autofillMsg.startsWith('✓') ? 'alert-ok' : autofillMsg === 'Extracting…' ? '' : 'alert-error'}`}
            style={{ marginTop: 0 }}>
            {autofillMsg}
          </div>
        )}
      </div>

      <div className="field-row cols-2">
        <div className="field"><label>Full Name *</label><input placeholder="Jane Smith" value={form.name} onChange={e => set('name', e.target.value)} /></div>
        <div className="field"><label>Location</label><input placeholder="City, Country" value={form.location} onChange={e => set('location', e.target.value)} /></div>
      </div>
      <div className="field-row cols-2">
        <div className="field"><label>Email *</label><input type="email" placeholder="jane@example.com" value={form.email} onChange={e => set('email', e.target.value)} /></div>
        <div className="field"><label>Phone</label><input placeholder="+1 555 000 0000" value={form.phone} onChange={e => set('phone', e.target.value)} /></div>
      </div>
      <div className="field-row cols-2">
        <div className="field"><label>LinkedIn</label><input placeholder="linkedin.com/in/jane" value={form.linkedin} onChange={e => set('linkedin', e.target.value)} /></div>
        <div className="field">
          <label>Work Authorization</label>
          <select value={form.auth} onChange={e => set('auth', e.target.value)}>
            {AUTH_OPTIONS.map(o => <option key={o} value={o}>{o || '— select —'}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Professional Summary</label>
        <textarea rows={3} placeholder="2–3 sentence professional summary" value={form.summary} onChange={e => set('summary', e.target.value)} />
      </div>

      <div className="sublabel" style={{ marginTop: 12 }}>Core Competencies</div>
      <DynamicList items={form.competencies} onChange={v => set('competencies', v)} placeholder="e.g. Agile / SAFe" />

      <div className="sublabel" style={{ marginTop: 12 }}>Experience</div>
      {form.experience.map((exp, i) => (
        <div key={i} className="exp-block">
          <div className="exp-block-header">
            <span>Role {i + 1}</span>
            <button className="btn-icon" type="button" onClick={() => set('experience', form.experience.filter((_, j) => j !== i))}>✕</button>
          </div>
          <div className="field-row cols-2">
            <div className="field"><label>Job Title</label><input placeholder="Product Owner" value={exp.title} onChange={e => { const n = [...form.experience]; n[i] = { ...exp, title: e.target.value }; set('experience', n); }} /></div>
            <div className="field"><label>Company</label><input placeholder="Acme Corp" value={exp.company} onChange={e => { const n = [...form.experience]; n[i] = { ...exp, company: e.target.value }; set('experience', n); }} /></div>
          </div>
        </div>
      ))}
      <button className="btn-add-row" type="button" onClick={() => set('experience', [...form.experience, EMPTY_EXP()])}>+ Add role</button>

      <div className="footer-nav" style={{ marginTop: 14 }}>
        <button className="btn btn-ghost" onClick={onBack}>← Back</button>
        <span className="step-hint">Step 2 of 3</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={onNext}>Skip →</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save & Continue →'}</button>
        </div>
      </div>
    </div>
  );
}

// ── Step 3: Done ───────────────────────────────────────────────────────────────

function Step3({ onBack }: { onBack: () => void }) {
  const navigate = useNavigate();
  const { refetch } = useProfile();
  const [fetching, setFetching] = useState(false);
  const [fetchMsg, setFetchMsg] = useState('');

  const handleFetch = async () => {
    setFetching(true);
    setFetchMsg('Starting fetch…');
    await fetcherApi.trigger();
    setFetchMsg('Fetch started! Redirecting…');
    await refetch();
    setTimeout(() => navigate('/'), 1500);
  };

  return (
    <div id="step-3" className="card" style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '3rem', marginBottom: 12 }}>🎉</div>
      <h2>You're all set!</h2>
      <p className="subtitle">Your profile is saved. Ready to find your next role.</p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 24 }}>
        <button className="btn btn-primary" onClick={handleFetch} disabled={fetching}>
          {fetching ? 'Starting…' : '⚡ Quick Fetch Jobs'}
        </button>
        <button className="btn btn-ghost" onClick={() => { refetch(); navigate('/'); }}>
          Go to Dashboard →
        </button>
      </div>
      {fetchMsg && <p style={{ marginTop: 12, fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>{fetchMsg}</p>}
      <div className="footer-nav" style={{ marginTop: 24 }}>
        <button className="btn btn-ghost" onClick={onBack}>← Back</button>
        <span className="step-hint">Step 3 of 3</span>
      </div>
    </div>
  );
}

// ── Main Setup page ────────────────────────────────────────────────────────────

export default function SetupPage() {
  const [step, setStep] = useState<1 | 2 | 3>(1);

  return (
    <main className="setup-page page-enter" id="main-content">
      <div className="setup-header">
        <h1>Welcome to <strong>JobPilot AI</strong></h1>
        <p>Let's get you set up in a few steps.</p>
      </div>
      <StepIndicator current={step} onStepClick={setStep} />
      {step === 1 && <Step1 onNext={() => setStep(2)} />}
      {step === 2 && <Step2 onBack={() => setStep(1)} onNext={() => setStep(3)} />}
      {step === 3 && <Step3 onBack={() => setStep(2)} />}
    </main>
  );
}
