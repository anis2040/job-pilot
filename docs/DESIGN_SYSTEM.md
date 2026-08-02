# Design System

All visual styling flows from CSS custom properties (design tokens) defined in
one place: the `:root` block at the top of [`static/base.css`](../static/base.css).

**Rule of thumb:** never hardcode a colour, size, radius, duration, or easing in
a template or component. Reference a token. If no token fits, add one to `:root`
first, then use it. This is what keeps every screen feeling like one product
instead of a pile of independently-built pages.

---

## Color

| Token | Use |
|-------|-----|
| `--bg-page` | App background (deepest layer) |
| `--bg-surface` | Cards, panels, header |
| `--bg-sunken` | Inset areas (inputs, code blocks) |
| `--bg-raised` | Ghost buttons, chips, raised controls |
| `--bg-hover` | Hover state for rows/cards |
| `--bg-active` | Selected/active row background |
| `--border` | Default 1px borders |
| `--border-faint` | Subtle dividers |
| `--border-focus` | Focus outline colour |
| `--text` | Primary body text |
| `--text-soft` | Secondary text |
| `--text-muted` | Tertiary / metadata (WCAG AA ≥4.5:1) |
| `--text-faint` | Lowest-emphasis text (WCAG AA ≥4.5:1) |
| `--text-white` | Headings / max contrast |
| `--blue`, `--blue-light`, `--blue-dim` | Brand / interactive / info badges |
| `--green` / `--green-bg` / `--green-border` | Success, "applied", positive |
| `--red` / `--red-bg` / `--red-border` | Danger, "skipped", destructive |
| `--orange`, `--yellow` | Warnings, "hybrid" |

Semantic aliases in JS come from `/api/constants` (`remote_css`, `job_statuses`).

## Typography

Scale (base = 14px, 1.25 ratio). Use `var(--text-*)`, never raw rem.

`--text-xs` 12 · `--text-sm` 13 · `--text-base` 14 · `--text-md` 15 ·
`--text-lg` 16 · `--text-xl` 18 · `--text-2xl` 22 · `--text-3xl` 28

Line heights: `--leading-tight` 1.3 (headings) · `--leading-normal` 1.5 (body) ·
`--leading-relaxed` 1.7 (long-form descriptions).

## Spacing (4px grid)

`--space-1` 4 · `-2` 8 · `-3` 12 · `-4` 16 · `-5` 20 · `-6` 24 · `-7` 28 ·
`-8` 32 · `-10` 40 · `-12` 48. Use for padding, margin, and gap.

## Radius

`--radius-sm` 4 (inputs, small controls) · `--radius` 8 (buttons) ·
`--radius-md` 10 · `--radius-lg` 12 (cards, modals) · `--radius-xl` 16 ·
`--radius-full` 99px (pills, avatars).

## Elevation / shadow

`--shadow-sm` (subtle lift) · `--shadow` (cards on hover) ·
`--shadow-lg` (modals, dropdowns, toasts).

## Motion

Durations and easing are tokenized so animations feel consistent app-wide.

| Token | Value | Use |
|-------|-------|-----|
| `--dur-fast` | 120ms | Hover/press micro-feedback: color, background, opacity, border |
| `--dur-base` | 200ms | Standard state changes; small layout moves (input width, etc.) |
| `--dur-slow` | 320ms | Larger moves: panels, modals, layout shifts |
| `--dur-spin` | 650ms | Spinner rotation period |
| `--dur-shimmer` | 1400ms | Skeleton shimmer loop period |
| `--ease-out` | `cubic-bezier(0.16,1,0.3,1)` | Enter / reveal (decelerate) — panels, modals appearing |
| `--ease-in-out` | `cubic-bezier(0.65,0,0.35,1)` | Moving between two states |
| `--ease-standard` | `ease` | Neutral default for micro-feedback |

**Pattern:** `transition: <prop> var(--dur-fast) var(--ease-standard);` for
hover feedback; `var(--dur-base) var(--ease-out)` for things that appear.

All motion is disabled automatically under `@media (prefers-reduced-motion:
reduce)` — you don't need to handle that per-component.

## Adding a new feature

1. Compose from existing tokens — check this doc first.
2. Reuse shared components before writing new CSS: `.btn`/`.btn-sm`/`.btn-lg`,
   `.card`, `.badge-*`, `.avatar*`, `.empty-state`, `.skeleton`, `.tag-*`,
   `.filter-chip`, plus JS helpers in [`static/ui.js`](../static/ui.js)
   (`showToast`, `confirmDialog`, `promptDialog`, `trapFocus`, `icon()`).
3. Only if nothing fits: add a token to `:root`, document it here, then use it.
