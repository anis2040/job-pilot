import { escapeHtml } from './format';

function decodeEntities(text: string): string {
  const ta = document.createElement('textarea');
  ta.innerHTML = String(text || '');
  return ta.value;
}

function looksLikeHeading(line: string): boolean {
  const t = line.trim();
  if (t.length === 0 || t.length > 60) return false;
  if (t.endsWith(':')) return true;
  if (/[.!?,]$/.test(t)) return false;
  const words = t.split(/\s+/);
  return words.length <= 6 && /^[A-Z0-9]/.test(t);
}

export function formatDescription(text: string): string {
  const cleaned = decodeEntities(text)
    .split('\n')
    .map(l => l.replace(/\s+$/, ''))
    .filter(ln => !/^\s*(show more|show less)\s*$/i.test(ln));

  const parts: string[] = [];
  let para: string[] = [];
  let bullets: string[] = [];

  const flushPara = () => {
    if (para.length) { parts.push(`<p>${para.map(escapeHtml).join('<br>')}</p>`); para = []; }
  };
  const flushBullets = () => {
    if (bullets.length) { parts.push(`<ul>${bullets.map(b => `<li>${escapeHtml(b)}</li>`).join('')}</ul>`); bullets = []; }
  };

  for (const raw of cleaned) {
    const line = raw.trim();
    if (!line) { flushPara(); flushBullets(); continue; }
    const bulletMatch = line.match(/^([•\-*–])\s+(.*)$/);
    if (bulletMatch) { flushPara(); bullets.push(bulletMatch[2]); }
    else if (looksLikeHeading(line)) { flushPara(); flushBullets(); parts.push(`<h4 class="desc-heading">${escapeHtml(line.replace(/:$/, ''))}</h4>`); }
    else { flushBullets(); para.push(line); }
  }
  flushPara();
  flushBullets();
  return parts.join('');
}

export function isLongDescription(text: string): boolean {
  return decodeEntities(text).length > 400;
}
