import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { profiles as profilesApi, setup, constants } from '../../api/client';
import { useProfile } from '../../hooks/useProfile';
import { useToast } from '../../components/ui/Toast';
import { Topbar } from '../../components/layout/Topbar';
import { TagInput } from '../../components/ui/TagInput';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { SearchRow, groupSearchEntries, expandSearchRows } from '../../components/ui/SearchRow';
import type { SearchConfig } from '../../api/types';
import { buildProfileMd, parseProfileMd, DEFAULT_FORM, EMPTY_EXP, EMPTY_EDU } from '../../utils/profileForm';
import type { ProfileFormData, ExpEntry, EduEntry } from '../../utils/profileForm';

type Section = 'profile' | 'search' | 'danger';

function DynamicList({ items, onChange, placeholder }: {
  items: string[]; onChange: (items: string[]) => void; placeholder: string;
}) {
  const set = (i: number, val: string) => { const next = [...items]; next[i] = val; onChange(next); };
  const remove = (i: number) => onChange(items.filter((_, idx) => idx !== i));
  const add = () => onChange([...items, '']);
  return (
    <div>
      <div className="dynamic-list">
        {items.map((v, i) => (
          <div key={i} className="dynamic-row">
            <input type="text" placeholder={placeholder} value={v} onChange={e => set(i, e.target.value)} />
            <button className="btn-icon" type="button" onClick={() => remove(i)} title="Remove">✕</button>
          </div>
        ))}
      </div>
      <button className="btn-add-row" type="button" onClick={add}>+ Add</button>
    </div>
  );
}

function ExperienceBlock({ exp, idx, onChange, onRemove }: {
  exp: ExpEntry; idx: number; onChange: (e: ExpEntry) => void; onRemove: () => void;
}) {
  const set = (k: keyof ExpEntry, v: unknown) => onChange({ ...exp, [k]: v });
  return (
    <div className="exp-block">
      <div className="exp-block-header">
        <span>Role {idx + 1}</span>
        <button className="btn-icon" type="button" onClick={onRemove}>✕</button>
      </div>
      <div className="field-row cols-2">
        <div className="field"><label>Job Title *</label><input className="exp-title" placeholder="Product Owner" value={exp.title} onChange={e => set('title', e.target.value)} /></div>
        <div className="field"><label>Company *</label><input className="exp-company" placeholder="Acme Corp" value={exp.company} onChange={e => set('company', e.target.value)} /></div>
      </div>
      <div className="field-row cols-3">
        <div className="field"><label>Location</label><input placeholder="Tunis, Tunisia" value={exp.location} onChange={e => set('location', e.target.value)} /></div>
        <div className="field"><label>Start Date</label><input placeholder="Oct 2020" value={exp.start} onChange={e => set('start', e.target.value)} /></div>
        <div className="field"><label>End Date</label><input placeholder="Present" value={exp.end} onChange={e => set('end', e.target.value)} /></div>
      </div>
      <div className="sublabel">Key bullets</div>
      <DynamicList items={exp.bullets} onChange={v => set('bullets', v)} placeholder="Led delivery of X, resulting in Y" />
      <div className="sublabel" style={{ marginTop: 8 }}>Key Projects (optional)</div>
      <div className="dynamic-list">
        {exp.projects.map((p, i) => (
          <div key={i} className="dynamic-row">
            <div style={{ flex: 1, display: 'flex', gap: 6 }}>
              <input style={{ width: 140, flexShrink: 0 }} type="text" placeholder="Project Name" value={p.name} onChange={e => { const next = [...exp.projects]; next[i] = { ...p, name: e.target.value }; set('projects', next); }} />
              <input type="text" placeholder="What it was, your role, and outcome" value={p.desc} onChange={e => { const next = [...exp.projects]; next[i] = { ...p, desc: e.target.value }; set('projects', next); }} />
            </div>
            <button className="btn-icon" type="button" onClick={() => set('projects', exp.projects.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
      </div>
      <button className="btn-add-row" type="button" onClick={() => set('projects', [...exp.projects, { name: '', desc: '' }])}>+ Add project</button>
    </div>
  );
}

function EduBlock({ edu, idx, onChange, onRemove }: {
  edu: EduEntry; idx: number; onChange: (e: EduEntry) => void; onRemove: () => void;
}) {
  return (
    <div className="exp-block">
      <div className="exp-block-header">
        <span>Degree {idx + 1}</span>
        <button className="btn-icon" type="button" onClick={onRemove}>✕</button>
      </div>
      <div className="field-row cols-2">
        <div className="field"><label>Full Degree Name</label><input className="edu-degree" placeholder="Master of Science in Information Systems" value={edu.degree} onChange={e => onChange({ ...edu, degree: e.target.value })} /></div>
        <div className="field"><label>Institution</label><input placeholder="University Name" value={edu.school} onChange={e => onChange({ ...edu, school: e.target.value })} /></div>
      </div>
      <div className="field-row cols-2">
        <div className="field"><label>Year</label><input placeholder="2024" value={edu.year} onChange={e => onChange({ ...edu, year: e.target.value })} /></div>
        <div className="field"><label>Location</label><input placeholder="City, Country" value={edu.location} onChange={e => onChange({ ...edu, location: e.target.value })} /></div>
      </div>
    </div>
  );
}

function AutoConfigCard({ slug }: { slug: string }) {
  const { showToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [result, setResult] = useState('');

  const handleAutoConfig = async () => {
    setLoading(true);
    setResult('');
    try {
      const res = await setup.suggestConfig() as { ok: boolean; searches: unknown[]; title_filter: string[]; location: string; error?: string };
      if (!res.ok) { setResult(`⚠ ${res.error || 'Failed'}`); return; }
      // Save the suggested config to this profile
      await profilesApi.saveConfig(slug, {
        searches: res.searches as never,
        title_filter: res.title_filter,
        blacklist: [],
        company_blacklist: [],
      });
      setResult(`✓ Configured ${res.searches.length} searches for ${res.location || 'your location'}`);
      showToast('Search config updated from profile');
    } catch { setResult('⚠ Failed to configure'); }
    finally { setLoading(false); }
  };

  return (
    <div className="settings-card" style={{ marginTop: 'var(--space-6)' }}>
      <div className="settings-card-header" role="button" tabIndex={0}
        onClick={() => setExpanded(e => !e)}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setExpanded(x => !x); }}>
        <div>
          <h3>Auto-configure searches</h3>
          <p>Let the AI read your profile and set up search queries automatically</p>
        </div>
        <span className="toggle-icon">{expanded ? '▲' : '▼'}</span>
      </div>
      <div className={`settings-card-body${expanded ? ' is-expanded' : ''}`}>
        <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)', marginBottom: 12 }}>
          Analyzes your profile to extract job titles, location, and remote preference, then rewrites your search config.
        </p>
        <button className="btn btn-primary btn-sm" onClick={handleAutoConfig} disabled={loading}>
          {loading ? '⚡ Configuring…' : '⚡ Configure from profile'}
        </button>
        {result && <div style={{ marginTop: 10, fontSize: 'var(--text-sm)' }}>{result}</div>}
      </div>
    </div>
  );
}

function ProfileFormSection({ slug }: { slug: string }) {
  const { showToast } = useToast();
  const [form, setForm] = useState<ProfileFormData>(DEFAULT_FORM());
  const [autofillStatus, setAutofillStatus] = useState('');
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    profilesApi.getMarkdown(slug).then(({ content }) => {
      if (content) setForm(parseProfileMd(content));
    });
  }, [slug]);

  const set = <K extends keyof ProfileFormData>(k: K, v: ProfileFormData[K]) => setForm(f => ({ ...f, [k]: v }));

  const handleAutofill = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setAutofillStatus('Extracting…');
    try {
      const res = await setup.parseResume(file) as { ok: boolean; data: Partial<ProfileFormData>; error?: string };
      if (!res.ok) { setAutofillStatus(`⚠ ${res.error}`); return; }
      setForm(f => ({ ...f, ...res.data }));
      setAutofillStatus(`✓ Form filled from ${file.name}`);
    } catch { setAutofillStatus('⚠ Upload failed.'); }
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleSave = async () => {
    if (!form.name) { showToast('Please enter your full name', 'err'); return; }
    if (!form.email) { showToast('Please enter your email', 'err'); return; }
    setSaving(true);
    const res = await profilesApi.saveMarkdown(slug, buildProfileMd(form));
    setSaving(false);
    if (res.ok) showToast('Profile saved');
    else showToast('Failed to save', 'err');
  };

  const AUTH_OPTIONS = [
    '', 'US Citizen — no sponsorship required', 'Green Card holder — legally authorized to work in the U.S.',
    'Authorized to work in the US · No sponsorship required', 'Requires H-1B sponsorship',
  ];

  return (
    <div className="section active" id="section-profile">
      <div className="section-title page-title">Profile</div>
      <div className="section-desc page-desc">Your contact info, experience, and skills. The AI uses this exclusively to build resumes and cover letters.</div>

      <div className="autofill-bar">
        <label className="btn btn-ghost btn-sm" style={{ cursor: 'pointer' }}>
          📎 Autofill from resume
          <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" style={{ display: 'none' }} onChange={handleAutofill} />
        </label>
        {autofillStatus && <span style={{ fontSize: 'var(--text-sm)', marginLeft: 8 }}>{autofillStatus}</span>}
      </div>

      <div className="settings-card">
        <div className="settings-card-body is-expanded">
          <div className="field-row cols-2">
            <div className="field"><label>Full Name *</label><input id="p-name" placeholder="Jane Smith" value={form.name} onChange={e => set('name', e.target.value)} /></div>
            <div className="field"><label>Location</label><input placeholder="City, Country" value={form.location} onChange={e => set('location', e.target.value)} /></div>
          </div>
          <div className="field-row cols-2">
            <div className="field"><label>Email *</label><input id="p-email" type="email" placeholder="jane@example.com" value={form.email} onChange={e => set('email', e.target.value)} /></div>
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
            <textarea rows={4} placeholder="2–3 sentence professional summary" value={form.summary} onChange={e => set('summary', e.target.value)} />
          </div>

          <div className="sublabel" style={{ marginTop: 16 }}>Core Competencies</div>
          <DynamicList items={form.competencies} onChange={v => set('competencies', v)} placeholder="e.g. Agile / SAFe Methodologies" />

          <div className="sublabel" style={{ marginTop: 16 }}>Professional Experience</div>
          {form.experience.map((exp, i) => (
            <ExperienceBlock key={i} exp={exp} idx={i}
              onChange={v => { const next = [...form.experience]; next[i] = v; set('experience', next); }}
              onRemove={() => set('experience', form.experience.filter((_, j) => j !== i))}
            />
          ))}
          <button className="btn-add-row" type="button" onClick={() => set('experience', [...form.experience, EMPTY_EXP()])}>+ Add role</button>

          <div className="sublabel" style={{ marginTop: 16 }}>Education</div>
          {form.education.map((edu, i) => (
            <EduBlock key={i} edu={edu} idx={i}
              onChange={v => { const next = [...form.education]; next[i] = v; set('education', next); }}
              onRemove={() => set('education', form.education.filter((_, j) => j !== i))}
            />
          ))}
          <button className="btn-add-row" type="button" onClick={() => set('education', [...form.education, EMPTY_EDU()])}>+ Add degree</button>

          <div className="sublabel" style={{ marginTop: 16 }}>Certifications</div>
          <DynamicList items={form.certifications} onChange={v => set('certifications', v)} placeholder="e.g. PSPO I, Scrum.org" />

          <div className="save-row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save profile'}
            </button>
          </div>
        </div>
      </div>

      <AutoConfigCard slug={slug} />
    </div>
  );
}

function SearchSection({ slug }: { slug: string }) {
  const { showToast } = useToast();
  const [allSources, setAllSources] = useState<string[]>([]);
  const [rows, setRows] = useState<{ query: string; location: string; remote: boolean; sources: string[] }[]>([]);
  const [titleFilter, setTitleFilter] = useState<string[]>([]);
  const [blacklist, setBlacklist] = useState<string[]>([]);
  const [companyBlacklist, setCompanyBlacklist] = useState<string[]>([]);

  useEffect(() => {
    constants.sources().then(setAllSources);
    profilesApi.getConfig(slug).then((cfg: SearchConfig) => {
      setRows(groupSearchEntries(cfg.searches || []));
      setTitleFilter(cfg.title_filter || []);
      setBlacklist(cfg.blacklist || []);
      setCompanyBlacklist(cfg.company_blacklist || []);
    });
  }, [slug]);

  const handleSave = async () => {
    const cfg: SearchConfig = {
      searches: expandSearchRows(rows),
      title_filter: titleFilter,
      blacklist,
      company_blacklist: companyBlacklist,
    };
    const res = await profilesApi.saveConfig(slug, cfg);
    if (res.ok) showToast('Search settings saved');
    else showToast('Failed to save', 'err');
  };

  return (
    <div className="section active" id="section-search">
      <div className="section-title page-title">Search Settings</div>
      <div className="section-desc page-desc">Configure which job sources, queries, and locations to search.</div>

      <div className="settings-card">
        <div className="settings-card-header"><div><h3>Search Sources</h3><p>One entry per query + source combination</p></div></div>
        <div className="settings-card-body is-expanded">
          <div id="search-rows">
            {rows.map((row, i) => (
              <SearchRow
                key={i} entry={row} sources={allSources}
                onChange={v => { const next = [...rows]; next[i] = v; setRows(next); }}
                onRemove={() => setRows(rows.filter((_, j) => j !== i))}
              />
            ))}
          </div>
          <button className="btn-add-row" onClick={() => setRows([...rows, { query: '', location: 'United States', remote: true, sources: allSources }])}>+ Add search</button>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-card-header"><div><h3>Filters</h3><p>Title filter, blacklist, company blacklist</p></div></div>
        <div className="settings-card-body is-expanded">
          <div className="field">
            <label>Title Filter <span className="label-hint">(keep jobs matching at least one)</span></label>
            <TagInput value={titleFilter} onChange={setTitleFilter} placeholder="add keyword, Enter" />
          </div>
          <div className="field">
            <label>Blacklist <span className="label-hint">(drop jobs containing these words)</span></label>
            <TagInput value={blacklist} onChange={setBlacklist} placeholder="add keyword, Enter" />
          </div>
          <div className="field">
            <label>Company Blacklist</label>
            <TagInput value={companyBlacklist} onChange={setCompanyBlacklist} placeholder="add company, Enter" />
          </div>
        </div>
      </div>

      <div className="save-row">
        <button className="btn btn-primary" onClick={handleSave}>Save search settings</button>
      </div>
    </div>
  );
}

export default function ProfileSettingsPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { active, profiles, refetch } = useProfile();
  const { showToast } = useToast();
  const [section, setSection] = useState<Section>('profile');
  const [confirmClear, setConfirmClear] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const profile = profiles.find(p => p.slug === slug);
  const isActive = active?.slug === slug;

  if (!slug) return null;

  const handleClearJobs = async () => {
    const res = await profilesApi.clearJobs(slug);
    setConfirmClear(false);
    if (res.ok) showToast('Jobs cleared');
    else showToast('Failed to clear', 'err');
  };

  const handleDeleteProfile = async () => {
    const res = await profilesApi.delete(slug);
    setConfirmDelete(false);
    if (res.ok) { await refetch(); navigate('/manage-profiles'); showToast('Profile deleted'); }
    else showToast('Failed to delete', 'err');
  };

  return (
    <>
      <Topbar
        backTo="/manage-profiles"
        backLabel="Profiles"
        title={profile?.label || profile?.name || slug}
        avatarColor={profile?.color}
        avatarInitials={profile?.initials}
      />
      <div className="layout page-enter">
        <nav className="sidenav">
          <div className="sidenav-section">Profile</div>
          {(['profile', 'search'] as Section[]).map(s => (
            <button key={s} className={`sidenav-item${section === s ? ' active' : ''}`} onClick={() => setSection(s)}>
              {s === 'profile' ? '👤 Profile' : '🔍 Search Settings'}
            </button>
          ))}
          <div className="sidenav-divider" />
          <button className={`sidenav-item${section === 'danger' ? ' active' : ''}`} style={{ color: '#f87171' }} onClick={() => setSection('danger')}>
            ⚠ Danger Zone
          </button>
        </nav>

        <div className="main">
          {section === 'profile' && <ProfileFormSection slug={slug} />}
          {section === 'search'  && <SearchSection slug={slug} />}
          {section === 'danger'  && (
            <div className="section active" id="section-danger">
              <div className="section-title page-title">Danger Zone</div>
              <div className="section-desc page-desc">Irreversible actions for this profile.</div>

              <div className={`danger-card${isActive ? '' : ''}`} style={{ marginBottom: 'var(--space-3)', ...(isActive ? { borderColor: 'var(--border)' } : {}) }}>
                <div className="info">
                  <h4>Delete this profile</h4>
                  <p>{isActive ? 'Switch to another profile first before deleting this one.' : 'Permanently deletes all jobs, resumes, and settings for this profile.'}</p>
                </div>
                <button className="btn btn-danger-outline" disabled={isActive} onClick={() => setConfirmDelete(true)}>Delete profile</button>
              </div>

              <div className="danger-card">
                <div className="info">
                  <h4>Clear all jobs</h4>
                  <p>Wipe this profile's job database. Resumes on disk are kept.</p>
                </div>
                <button className="btn btn-danger-outline" onClick={() => setConfirmClear(true)}>Clear jobs</button>
              </div>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmClear}
        title="Clear all jobs?"
        message="This will wipe the job database for this profile. Resumes on disk are kept."
        confirmLabel="Clear jobs"
        danger
        onConfirm={handleClearJobs}
        onCancel={() => setConfirmClear(false)}
      />
      <ConfirmDialog
        open={confirmDelete}
        title="Delete this profile?"
        message="Permanently deletes all jobs, resumes, and settings for this profile. This cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={handleDeleteProfile}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  );
}
