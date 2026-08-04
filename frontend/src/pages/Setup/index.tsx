import { useState, useEffect, useRef, Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import { setup as setupApi, fetcher as fetcherApi } from '../../api/client';
import { useProfile } from '../../hooks/useProfile';
import { useToast } from '../../components/ui/useToast';
import type { SetupStatus } from '../../api/types';
import {
  buildProfileMd, DEFAULT_FORM, EMPTY_EXP, EMPTY_EDU,
  type ProfileFormData, type ExpEntry, type EduEntry,
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
  const [keyVisible, setKeyVisible] = useState(false);
  const [actionStatus, setActionStatus] = useState('');
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [testing, setTesting] = useState(false);
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
    setActionStatus(res.output || (res.ok ? '✓ Installed' : '⚠ Failed'));
    if (res.ok) setStatus(s => s ? { ...s, has_claude: provider === 'claude' || s.has_claude, has_gemini: provider === 'gemini' || s.has_gemini } : s);
  };

  const handleSaveKey = async () => {
    if (!provider) return;
    const trimmed = keyInput.trim();
    if (!trimmed || trimmed.startsWith('•')) {
      setActionStatus('✓ Using previously saved key');
      return;
    }
    setActionStatus('Saving…');
    let res: { ok: boolean };
    if (provider === 'groq') res = await setupApi.saveGroqKey(trimmed);
    else if (provider === 'gemini') res = await setupApi.saveGeminiKey(trimmed);
    else res = { ok: false };
    setActionStatus(res.ok ? '✓ Key saved' : '⚠ Failed to save key');
    if (res.ok) setStatus(s => s ? { ...s, groq_key_set: provider === 'groq' || s.groq_key_set, gemini_key_set: provider === 'gemini' || s.gemini_key_set } : s);
  };

  const handleClaudeLogin = async () => {
    setActionStatus('Opening login…');
    const res = await setupApi.claudeLogin();
    setActionStatus(res.ok ? '✓ Browser opened — log in, then test the connection below' : '⚠ Failed');
    if (res.ok) setStatus(s => s ? { ...s, has_claude: true } : s);
  };

  const handleTest = async () => {
    if (!provider) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await setupApi.testProvider(provider) as { ok: boolean; model?: string; latency_ms?: number; error?: string };
      if (res.ok) setTestResult({ ok: true, msg: `✓ Connected${res.model ? ` · ${res.model}` : ''}${res.latency_ms ? ` · ${res.latency_ms}ms` : ''}` });
      else setTestResult({ ok: false, msg: `✗ ${res.error || 'Connection failed'}` });
    } catch {
      setTestResult({ ok: false, msg: '✗ Request failed' });
    } finally {
      setTesting(false);
    }
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
            <div key={p} className={`provider-card${provider === p ? ' selected' : ''}`} onClick={() => {
              setProvider(p);
              setActionStatus('');
              setTestResult(null);
              setKeyVisible(false);
              if (p === 'groq') setKeyInput(status?.groq_key || '');
              else if (p === 'gemini') setKeyInput(status?.gemini_key || '');
              else setKeyInput('');
            }}>
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
          <div id="provider-action" style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>

            {/* Claude — login + optional install if CLI missing */}
            {provider === 'claude' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {status && !status.has_claude && (
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button className="btn btn-ghost btn-sm" onClick={handleInstallCli}>Install Claude CLI</button>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-faint)' }}>npm install -g @anthropic-ai/claude-code</span>
                  </div>
                )}
                <button className="btn btn-primary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={handleClaudeLogin}>
                  Open login in browser
                </button>
              </div>
            )}

            {/* Groq / Gemini — API key input */}
            {(provider === 'groq' || provider === 'gemini') && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input
                    type={keyVisible ? 'text' : 'password'}
                    placeholder={provider === 'groq' ? 'gsk_…' : 'AIza…'}
                    value={keyInput}
                    onChange={e => setKeyInput(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button className="btn btn-ghost btn-sm" type="button" title={keyVisible ? 'Hide key' : 'Show key'} style={{ padding: '5px 8px' }} onClick={() => setKeyVisible(v => !v)}>👁</button>
                  <button className="btn btn-primary btn-sm" onClick={handleSaveKey}>Save key</button>
                  {/* Gemini only: show install button if CLI is missing */}
                  {provider === 'gemini' && status && !status.has_gemini && (
                    <button className="btn btn-ghost btn-sm" onClick={handleInstallCli}>Install CLI</button>
                  )}
                </div>
                <div className="hint">Your key is saved locally in .env and never shared.</div>
              </div>
            )}

            {/* Test connection row — always shown once a provider is selected */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button className="btn btn-ghost btn-sm" onClick={handleTest} disabled={testing}>
                {testing ? 'Testing…' : 'Test connection'}
              </button>
              {testResult && (
                <span style={{ fontSize: 'var(--text-sm)', color: testResult.ok ? 'var(--green)' : 'var(--red)' }}>
                  {testResult.msg}
                </span>
              )}
            </div>

            {actionStatus && (
              <div className={`alert ${actionStatus.startsWith('✓') ? 'alert-ok' : actionStatus.includes('…') ? '' : 'alert-error'}`}>
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

function ExpBlock({ exp, idx, onChange, onRemove }: { exp: ExpEntry; idx: number; onChange: (e: ExpEntry) => void; onRemove: () => void }) {
  const set = (k: keyof ExpEntry, v: unknown) => onChange({ ...exp, [k]: v });
  return (
    <div className="exp-block">
      <div className="exp-block-header">
        <span>Role {idx + 1}</span>
        <button className="btn-icon" type="button" onClick={onRemove}>✕</button>
      </div>
      <div className="field-row cols-2">
        <div className="field"><label>Job Title</label><input placeholder="Product Owner" value={exp.title} onChange={e => set('title', e.target.value)} /></div>
        <div className="field"><label>Company</label><input placeholder="Acme Corp" value={exp.company} onChange={e => set('company', e.target.value)} /></div>
      </div>
      <div className="field-row cols-3">
        <div className="field"><label>Location</label><input placeholder="Berlin, Germany" value={exp.location} onChange={e => set('location', e.target.value)} /></div>
        <div className="field"><label>Start Date</label><input placeholder="Jan 2022" value={exp.start} onChange={e => set('start', e.target.value)} /></div>
        <div className="field"><label>End Date</label><input placeholder="Present" value={exp.end} onChange={e => set('end', e.target.value)} /></div>
      </div>
      <div className="sublabel">Key bullets</div>
      <DynamicList items={exp.bullets} onChange={v => set('bullets', v)} placeholder="Led delivery of X, resulting in Y" />
    </div>
  );
}

function EduBlock({ edu, idx, onChange, onRemove }: { edu: EduEntry; idx: number; onChange: (e: EduEntry) => void; onRemove: () => void }) {
  return (
    <div className="exp-block">
      <div className="exp-block-header">
        <span>Degree {idx + 1}</span>
        <button className="btn-icon" type="button" onClick={onRemove}>✕</button>
      </div>
      <div className="field-row cols-2">
        <div className="field"><label>Full Degree Name</label><input placeholder="Master of Science in Computer Science" value={edu.degree} onChange={e => onChange({ ...edu, degree: e.target.value })} /></div>
        <div className="field"><label>Institution</label><input placeholder="University Name" value={edu.school} onChange={e => onChange({ ...edu, school: e.target.value })} /></div>
      </div>
      <div className="field-row cols-2">
        <div className="field"><label>Year</label><input placeholder="2024" value={edu.year} onChange={e => onChange({ ...edu, year: e.target.value })} /></div>
        <div className="field"><label>Location</label><input placeholder="City, Country" value={edu.location} onChange={e => onChange({ ...edu, location: e.target.value })} /></div>
      </div>
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
    } catch (error) {
      setAutofillMsg(`⚠ ${error instanceof Error ? error.message : 'Upload failed'}`);
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
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
        <ExpBlock
          key={i} exp={exp} idx={i}
          onChange={v => { const n = [...form.experience]; n[i] = v; set('experience', n); }}
          onRemove={() => set('experience', form.experience.filter((_, j) => j !== i))}
        />
      ))}
      <button className="btn-add-row" type="button" onClick={() => set('experience', [...form.experience, EMPTY_EXP()])}>+ Add role</button>

      <div className="sublabel" style={{ marginTop: 12 }}>Education</div>
      {form.education.map((edu, i) => (
        <EduBlock
          key={i} edu={edu} idx={i}
          onChange={v => { const n = [...form.education]; n[i] = v; set('education', n); }}
          onRemove={() => set('education', form.education.filter((_, j) => j !== i))}
        />
      ))}
      <button className="btn-add-row" type="button" onClick={() => set('education', [...form.education, EMPTY_EDU()])}>+ Add degree</button>

      <div className="sublabel" style={{ marginTop: 12 }}>Certifications</div>
      <DynamicList items={form.certifications} onChange={v => set('certifications', v)} placeholder="e.g. PMP, AWS Solutions Architect (2024)" />

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
  const [suggesting, setSuggesting] = useState(true);
  const [suggestError, setSuggestError] = useState('');
  const [suggested, setSuggested] = useState<{ titles: string[]; location: string } | null>(null);

  useEffect(() => {
    setupApi.suggestConfig()
      .then((res: { ok: boolean; title_filter?: string[]; location?: string; error?: string }) => {
        if (res.ok) {
          setSuggested({ titles: res.title_filter ?? [], location: res.location ?? '' });
        } else {
          setSuggestError(res.error || 'Could not generate config');
        }
      })
      .catch(() => setSuggestError('Could not generate search config'))
      .finally(() => setSuggesting(false));
  }, []);

  const handleFetch = async () => {
    setFetching(true);
    setFetchMsg('Starting fetch…');
    try {
      await fetcherApi.trigger();
      setFetchMsg('Fetch started! Redirecting…');
      await refetch();
      setTimeout(() => navigate('/'), 1500);
    } catch {
      setFetchMsg('Failed to start fetch — go to dashboard and try manually.');
      setFetching(false);
    }
  };

  return (
    <div id="step-3" className="card" style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '3rem', marginBottom: 12 }}>🎉</div>
      <h2>You're all set!</h2>
      <p className="subtitle">Your profile is saved. Here's what we'll search for:</p>

      <div style={{ margin: '20px 0', textAlign: 'left', background: 'var(--bg-raised)', borderRadius: 'var(--radius)', padding: '14px 16px', border: '1px solid var(--border-faint)' }}>
        {suggesting && (
          <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>⏳ Generating search config from your profile…</p>
        )}
        {suggestError && (
          <p style={{ color: 'var(--red)', fontSize: 'var(--text-sm)' }}>⚠ {suggestError} — you can configure searches manually in Settings.</p>
        )}
        {suggested && (
          <>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-soft)', marginBottom: 6 }}>
              <strong style={{ color: 'var(--text)' }}>Titles:</strong> {suggested.titles.join(', ')}
            </p>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-soft)' }}>
              <strong style={{ color: 'var(--text)' }}>Location:</strong> {suggested.location}
            </p>
          </>
        )}
      </div>

      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 8 }}>
        <button className="btn btn-primary" onClick={handleFetch} disabled={fetching || suggesting}>
          {fetching ? 'Starting…' : '⚡ Fetch Jobs Now'}
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
