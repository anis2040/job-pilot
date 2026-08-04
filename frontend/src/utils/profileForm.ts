// Data shapes for the structured profile form
export interface ExpEntry {
  title: string;
  company: string;
  location: string;
  start: string;
  end: string;
  bullets: string[];
  projects: { name: string; desc: string }[];
}

export interface EduEntry {
  degree: string;
  school: string;
  year: string;
  location: string;
}

export interface ProfileFormData {
  name: string;
  location: string;
  phone: string;
  email: string;
  linkedin: string;
  auth: string;
  summary: string;
  competencies: string[];
  experience: ExpEntry[];
  education: EduEntry[];
  certifications: string[];
}

export const EMPTY_EXP = (): ExpEntry => ({ title: '', company: '', location: '', start: '', end: '', bullets: [''], projects: [] });
export const EMPTY_EDU = (): EduEntry => ({ degree: '', school: '', year: '', location: '' });
export const DEFAULT_FORM = (): ProfileFormData => ({
  name: '', location: '', phone: '', email: '', linkedin: '', auth: '', summary: '',
  competencies: ['', '', ''],
  experience: [EMPTY_EXP()],
  education: [EMPTY_EDU()],
  certifications: [],
});

export function buildProfileMd(d: ProfileFormData): string {
  const lines: string[] = [];
  lines.push(`# ${d.name || 'Your Name'} — Full Profile`, '');
  lines.push('## Contact');
  if (d.location) lines.push(`- Location: ${d.location}`);
  if (d.phone)    lines.push(`- Phone: ${d.phone}`);
  if (d.email)    lines.push(`- Email: ${d.email}`);
  if (d.linkedin) lines.push(`- LinkedIn: ${d.linkedin}`);
  if (d.auth)     lines.push(`- Work authorization: ${d.auth}`);
  lines.push('', '---', '');

  if (d.summary) lines.push('## Professional Summary', '', d.summary, '', '---', '');

  const comps = d.competencies.filter(Boolean);
  if (comps.length) {
    lines.push('## Core Competencies', '');
    comps.forEach(c => lines.push(`- ${c}`));
    lines.push('', '---', '');
  }

  const exps = d.experience.filter(e => e.title || e.company);
  if (exps.length) {
    lines.push('## Professional Experience', '');
    exps.forEach(e => {
      lines.push(`### ${e.title} — ${e.company}`);
      if (e.location) lines.push(`**Location:** ${e.location}`);
      if (e.start)    lines.push(`**Dates:** ${e.start} – ${e.end || 'Present'}`);
      lines.push('');
      const bullets = e.bullets.filter(Boolean);
      if (bullets.length) { lines.push('**Bullets:**'); bullets.forEach(b => lines.push(`- ${b}`)); lines.push(''); }
      const projects = e.projects.filter(p => p.name || p.desc);
      if (projects.length) {
        lines.push('**Key Projects:**');
        projects.forEach(p => lines.push(`- **${p.name || 'Project'}:** ${p.desc}`));
        lines.push('');
      }
    });
    lines.push('---', '');
  }

  const edus = d.education.filter(e => e.degree);
  if (edus.length) {
    lines.push('## Education', '');
    edus.forEach(e => {
      lines.push(`### ${e.degree}`);
      if (e.school)   lines.push(`- **Institution:** ${e.school}`);
      if (e.location) lines.push(`- **Location:** ${e.location}`);
      if (e.year)     lines.push(`- **Year conferred:** ${e.year}`);
      lines.push('');
    });
    lines.push('---', '');
  }

  const certs = d.certifications.filter(Boolean);
  if (certs.length) {
    lines.push('## Certifications', '');
    certs.forEach(c => lines.push(`- ${c}`));
  }

  return lines.join('\n');
}

export function parseProfileMd(md: string): ProfileFormData {
  if (!md) return DEFAULT_FORM();
  const d = DEFAULT_FORM();
  d.competencies = [];
  d.experience = [];
  d.education = [];

  const lines = md.split('\n');
  let section = '';
  let currentExp: ExpEntry | null = null;
  let currentEdu: EduEntry | null = null;
  let inBullets = false, inProjects = false;

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.startsWith('## Contact'))                { section = 'contact'; continue; }
    if (line.startsWith('## Professional Summary'))   { section = 'summary'; continue; }
    if (line.startsWith('## Core Competencies'))      { section = 'competencies'; continue; }
    if (line.startsWith('## Professional Experience')){ section = 'experience'; continue; }
    if (line.startsWith('## Education'))              { section = 'education'; continue; }
    if (line.startsWith('## Certifications'))         { section = 'certifications'; continue; }
    if (line.startsWith('---')) continue;

    if (section === 'contact' && line.startsWith('- ')) {
      const m = line.slice(2).match(/^([\w ]+):\s*(.+)/);
      if (m) {
        const key = m[1].toLowerCase().trim(), val = m[2].trim();
        if (key === 'location') d.location = val;
        else if (key === 'phone') d.phone = val;
        else if (key === 'email') d.email = val;
        else if (key === 'linkedin') d.linkedin = val;
        else if (key === 'work authorization') d.auth = val;
        else if (key === 'name' || key === 'full name') d.name = val;
      }
    }
    if (section === 'summary' && line.trim()) d.summary = (d.summary ? d.summary + ' ' : '') + line.trim();
    if (section === 'competencies' && line.startsWith('- ')) d.competencies.push(line.slice(2).trim());
    if (section === 'experience') {
      if (line.startsWith('### ')) {
        const parts = line.slice(4).split(' — ');
        currentExp = { title: parts[0]?.trim() || '', company: parts.slice(1).join(' — ').trim() || '', location: '', start: '', end: '', bullets: [], projects: [] };
        d.experience.push(currentExp);
        inBullets = false; inProjects = false;
      } else if (currentExp) {
        const locM = line.match(/^\*\*Location:\*\*\s*(.+)/);
        const dateM = line.match(/^\*\*Dates:\*\*\s*(.+)/);
        if (locM) currentExp.location = locM[1].trim();
        else if (dateM) { const dp = dateM[1].split(' – '); currentExp.start = dp[0]?.trim() || ''; currentExp.end = dp[1]?.trim() || ''; }
        else if (line.trim() === '**Bullets:**') { inBullets = true; inProjects = false; }
        else if (line.trim() === '**Key Projects:**') { inProjects = true; inBullets = false; }
        else if (inBullets && line.startsWith('- ')) currentExp.bullets.push(line.slice(2).trim());
        else if (inProjects && line.startsWith('- ')) {
          const pm = line.slice(2).match(/^\*\*(.+?):\*\*\s*(.*)/);
          if (pm) currentExp.projects.push({ name: pm[1].trim(), desc: pm[2].trim() });
        }
      }
    }
    if (section === 'education') {
      if (line.startsWith('### ')) { currentEdu = { degree: line.slice(4).trim(), school: '', year: '', location: '' }; d.education.push(currentEdu); }
      else if (currentEdu && line.startsWith('- ')) {
        const m = line.slice(2).match(/^\*\*(.+?):\*\*\s*(.*)/);
        if (m) {
          const key = m[1].toLowerCase();
          if (key.includes('institution')) currentEdu.school = m[2].trim();
          else if (key.includes('location')) currentEdu.location = m[2].trim();
          else if (key.includes('year')) currentEdu.year = m[2].trim();
        }
      }
    }
    if (section === 'certifications' && line.startsWith('- ')) d.certifications.push(line.slice(2).trim());
  }

  if (!d.competencies.length) d.competencies = ['', '', ''];
  if (!d.experience.length) d.experience = [EMPTY_EXP()];
  if (!d.education.length) d.education = [EMPTY_EDU()];

  return d;
}
