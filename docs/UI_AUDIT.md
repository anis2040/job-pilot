# UI Audit & Roadmap — JobPilot AI

Status snapshot after the design-system consolidation. Many items from the
original pre-launch audit were already fixed in prior work (duplicate-CSS
removal, WCAG contrast, touch targets, focus rings, keyboard nav, modal focus
trap, custom dialogs, SVG icon migration, split view, motion tokens). This
document records what's **done**, what **remains**, and the priority order.

See [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) for the token/component reference.

---

## Scores (current)

| Dimension | Was | Now | Notes |
|-----------|:---:|:---:|-------|
| Overall UI | 6 | 8 | Card list, split view, consistent chrome |
| UX | 6 | 8 | Keyboard nav, filters, posted-date sort, labels |
| Visual design | 6 | 8 | Deeper palette, real elevation, type scale |
| Consistency | 5 | 8 | Full token layer; near-zero raw values |
| Accessibility | 5 | 8 | Contrast AA, focus rings, traps, ARIA, reduced-motion |
| Modern feel | 6 | 8 | SVG icons, skeletons, micro-interactions |
| Premium feel | 5 | 7 | Strong foundation; AI-content polish is the next lever |

---

## Consistency audit — resolved

- **Design tokens** cover color, text, spacing (4px grid), radius, shadow,
  type scale, line-height, motion (duration + easing), opacity, z-index,
  breakpoints. One `:root` in `base.css`.
- **Buttons** — single `.btn` system with size variants; no inline
  `min-height` overrides; identical hover/press/focus everywhere.
- **Cards** — one `.card` definition; per-screen bespoke card CSS removed.
- **Badges/chips** — unified sizing/padding; `.badge-active` bordered like peers.
- **Radius / shadow / motion** — no raw values in components (verified: 0 raw
  z-index, 0 raw transition durations).
- **Icons** — chrome migrated to inline Lucide-style SVGs via `icon()`.

## Consistency audit — remaining (low)

- A few status **hex literals** persist for semantic accents not yet
  tokenized (`#16a34a` success-solid, `#0d2e1a`/`#1a4d2e` remote-remote pill,
  `#a78bfa` code purple, doc-action button colors). Low risk — they're
  single-purpose — but could become `--success-solid`, `--accent-purple`, etc.
- Meta emoji (🌐📍🏢) in job rows are intentional accents, not migrated to SVG.

---

## Accessibility audit

**Done:** AA contrast on all text tokens; `:focus-visible` ring globally;
modal + dialog focus traps with Escape + focus restore; keyboard-navigable job
rows (Enter/Space/j/k) and profile menu (arrows/Escape); `aria-pressed` on
filter chips; `aria-label`s on icon buttons and selects; skip-to-content →
`<main>`; `role="status" aria-live="polite"` toast; `prefers-reduced-motion`
honored; touch targets ≥44px on mobile.

**Remaining:** run one screen-reader pass on the split-view (announce panel
open); verify colour is never the *only* status signal (remote pills pair
colour with a text label already — good; confirm score meters do too when built).

---

## Premium polish — where we still trail Linear/Stripe/Vercel

1. **AI content presentation** — the biggest gap. The AI-Skill layer now
   exists in CSS but isn't wired to a real streaming surface yet. Resume/cover-
   letter generation shows a spinner + stage text, not streamed output.
   *Highest-impact lever for perceived quality.*
2. **Page transitions** — navigations are hard cuts. A subtle fade/slide on
   route change (or view-transition API) would add continuity.
3. **Dashboard** — there's no overview/home; the app opens straight into the
   job list. A light stats/next-actions dashboard would frame the product.
4. **Search** — functional but plain; no keyboard-first command palette (⌘K).
5. **Empty/loading** — skeletons and empty states are solid; AI-pending states
   should use the new `.ai-skeleton` for parity.

---

## Prioritized roadmap

### Quick wins (<30 min each)
- Tokenize the remaining semantic hexes (`--success-solid`, `--accent-purple`,
  remote-pill bg/border) and swap in components.
- Add `.score-meter` colour+label pairing helper so it never relies on colour alone.
- Pair each meta-emoji with an `aria-hidden` wrapper (icons are decorative).

### High-impact
- **Wire a real AI streaming surface** using `.ai-stream` + `.ai-skeleton`
  (start with the cover-letter build, since it already polls). Biggest premium
  jump for the least new design.
- **Dashboard/home** with `.ai-card` stat tiles + next-actions.
- **⌘K command palette** (fuzzy search jobs + jump to skills).
- **Page transitions** via the View Transitions API (progressive enhancement).

### Components to refactor first
1. Job row → extract a documented `.list-row` primitive so application-history
   and analytics rows reuse it verbatim.
2. The three doc-action buttons (inline-styled CV/Letter colors) → `.btn-cv` /
   `.btn-letter` token classes.
3. Consolidate the sidebar-card in `job_detail` with the generic `.ai-card`
   (same structure, different content) to shrink the surface area.

---

## Feature-first: adding an AI Skill

A new skill (e.g. "Interview Prep") should be: a route → a `.skill-page`
shell → `.ai-card`/`.report-section`/`.rec-list`/`.score-meter` blocks →
`.ai-skeleton` then `.ai-stream` for generated content. **No new CSS.** If a
skill needs a visual the system lacks, add the primitive to `base.css` and
document it — don't style inline.
