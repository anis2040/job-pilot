# Design System

All visual styling flows from CSS custom properties (design tokens) defined in
one place: the `:root` block at the top of
[`frontend/src/styles/base.css`](../frontend/src/styles/base.css).

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

## Opacity

`--opacity-disabled` 0.4 · `--opacity-muted` 0.6 · `--opacity-hover` 0.88 ·
`--opacity-hidden` 0 (pre-transition transparent state).

## Z-index

One ladder for the whole app — never invent a raw z-index.

| Token | Value | Layer |
|-------|-------|-------|
| `--z-base` | 0 | Normal flow |
| `--z-sticky` | 50 | Sticky headers / toolbars |
| `--z-backdrop` | 100 | Modal / overlay backdrops |
| `--z-dropdown` | 200 | Menus, popovers, select panels |
| `--z-toast` | 1000 | Transient notifications |
| `--z-dialog` | 1100 | Confirm / prompt dialogs (above toasts) |
| `--z-skiplink` | 9999 | Skip-to-content (top when focused) |

## Breakpoints

`@media` can't read custom properties, so these live in `:root` as the
documented source of truth — match them exactly when writing queries.

`--bp-sm` 480 · `--bp-md` 768 (collapse split/two-column layouts) ·
`--bp-lg` 1024 · `--bp-xl` 1200 (master-detail split view enables).

---

## Components

Compose these; don't restyle per-screen. Shared primitives are defined in
`frontend/src/styles/base.css`, with React helpers in `frontend/src/components`.

**Buttons** — `.btn` + one variant (`.btn-primary`, `.btn-success`,
`.btn-danger`, `.btn-ghost`, `.btn-danger-outline`) + optional size
(`.btn-sm` 34px, default 36px, `.btn-lg` 42px, `.btn-xl` 48px). `.btn-icon`
for 32px icon-only (44px on mobile). Hover dims to `--opacity-hover`, press
nudges 1px down, focus shows the global ring. Loading = swap label for
`<span class="spinner">` + disable.

**Cards** — `.card` (surface + border + `--radius-lg`), `.card-header`
(title + optional subtitle), `.card-body` (`--space-5` padding). Hover
elevation via `--shadow` where interactive.

**Badges / chips** — `.badge-*` (status: pending/applied/skipped, free/paid,
active/none). `.filter-chip` for toggleable filters (`aria-pressed`), `.tag`
for removable tokens, `.skill-tag` for read-only labels.

**Forms** — `.field` (label + input), `.field-row.cols-2/3` for grids,
`.tag-input-wrap`/`.tag` for multi-value, `.dynamic-row` for repeatable rows.
Focus = blue border. Inputs are 9px 12px padding, `--radius`. Validation errors
use `.alert-error`; success uses `.save-notice` or a toast.

**Feedback** — `.empty-state` (icon + title + desc + CTA), `.skeleton`
(shimmer placeholder), `.alert`/`.alert-error`/`.alert-ok`, and the JS
`showToast()` for transient status. Dialogs: `confirmDialog()` / `promptDialog()`
(never native `confirm`/`prompt`/`alert`).

**Lists & tables** — job rows use a two-column grid (identity left, meta +
actions right) with `--bg-hover` on hover and a `--blue` inset bar when selected.
Reuse this row rhythm for any future list (application history, analytics rows).

## AI experience patterns

Every AI Skill inherits these — adding a skill should need **no new CSS**:

| Class | Use |
|-------|-----|
| `.skill-page` / `.skill-header` / `.skill-body` | Page shell for any AI feature (icon + title + subtitle, consistent column width & rhythm) |
| `.ai-card` + `.ai-badge` | A titled AI result block that visibly marks AI-generated content |
| `.ai-stream.streaming` | Token-by-token streaming text with a blinking caret |
| `.ai-task` + `.ai-progress` | Long-running task with a stage label and determinate/indeterminate bar |
| `.report-section` | Sectioned structured output (ATS report, company insights) |
| `.score-meter` (`.good`/`.mid`/`.low`) | At-a-glance metric (match %, readiness) |
| `.rec-list` / `.rec-item` (`.high`/`.med`/`.low`) | Prioritized actionable recommendations |
| `.roadmap` / `.roadmap-step` | Stepped guidance / learning path |
| `.ai-skeleton` | Loading placeholder while an analysis is pending |

**Streaming rule:** show `.ai-skeleton` before the first token, switch to
`.ai-stream.streaming` while tokens arrive, drop the `streaming` class when done.
**Always mark AI content** with `.ai-badge` so users can distinguish it from
their own data.

## Adding a new feature

1. Compose from existing tokens — check this doc first.
2. Reuse shared components before writing new CSS: `.btn`/`.btn-sm`/`.btn-lg`,
   `.card`, `.badge-*`, `.avatar*`, `.empty-state`, `.skeleton`, `.tag-*`,
   `.filter-chip`, plus React helpers such as
   [`Toast`](../frontend/src/components/ui/Toast.tsx),
   [`ConfirmDialog`](../frontend/src/components/ui/ConfirmDialog.tsx),
   [`PromptDialog`](../frontend/src/components/ui/PromptDialog.tsx), and
   [`Icon`](../frontend/src/components/ui/Icon.tsx).
3. Only if nothing fits: add a token to `:root`, document it here, then use it.
