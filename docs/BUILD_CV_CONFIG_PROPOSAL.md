# Configurable Build CV — Architecture & Product Proposal

> Status: **proposal / not implemented**. Design only.
> Goal: let the user control *how far the system reaches* when positioning their real
> experience against a JD — while the prompt gets **leaner**, not heavier, and factual
> guards stay absolute.

---

## 0. The core problem (why this is a rewrite, not a feature bolt-on)

Today's `SKILL.md` handles the "how far to reach" question with a **fixed, cautious default the
user cannot move**. The relevant lines pull in two directions at once:

- `SKILL.md:41` — *"Adjacent experience exists → reframe truthfully from `profile.md`; never
  imply direct experience with an unused tool."* (invites reframing **and** warns against it)
- `SKILL.md:43` — the scope-precision rule (*"consuming an API ≠ building backend services …
  configuring a tool ≠ architecting the system. Reframe only as far as the evidence genuinely
  reaches."*)

The prose **isn't broken** — it explicitly permits truthful reframing and keyword-equivalence
(`SKILL.md:87`), so this is not a case of the prompt banning good matching. The problems are
narrower: **(a) it's ambiguous at the margin.** For a React/TypeScript candidate on a Next.js
role, "reframe truthfully" and "never imply direct experience with an unused tool" point opposite
ways; a literal LLM can land anywhere from a strong transferable framing to dropping Next.js — and
the user has no control over which. **(b) The reach is a fixed default, not a dial.** A user who
wants a more literal CV, or a bolder one, cannot ask for it.

The "how far to reach" concern also lives in **two** places that can drift: `SKILL.md` prose and
the `_verify_content` verifier (documents.py:347, a hardcoded system prompt). The deterministic
guards in `latex_render.py` are a *different* concern — they enforce vocabulary/pattern facts
(competency grounding, employer fabrication, specific scope/title/filler phrases), not the
semantic "is this a transferable framing or a direct claim" judgment, which no regex can make.
So the redundancy is prose↔verifier, not a three-way tangle — but it's still two owners for one
question, and piling a positioning *dial* on top without consolidating would add a third.

**The fix is subtractive first, then configurable:**
1. Collapse the "how truthful / how far to reach" concern to **one home** (a generated
   positioning stance), and **lean the redundant conservatism prose out of `SKILL.md`**.
2. Split the world cleanly into **immutable facts** (never a dial) and **positioning stance**
   (the *only* variable), so the two never argue.
3. Give the stance to the **user** via one dial, defaulting to a genuinely useful Balanced —
   replacing today's fixed, uncontrollable default.

The result is a *shorter* prompt with *fewer* rules, one of which the user controls.

---

## 1. Current Architecture

`Build CV` has **two independent consumers of the same skill prompt** (`resume-skill/SKILL.md`):

### A. Web JSON path (the product path) — `job/documents.py`
```
POST /api/resume/<job_id>                     web.py:733  → trigger_resume() → _build_resume()
  → _build_document(job_id, "resume")         documents.py:490
    → _build_resume_prompt()                  documents.py:176
        skill_text = SKILL.md
                   + profile.md (_append_profile)
                   + _JSON_OUTPUT_FORMAT       (code-defined contract, documents.py:25-66)
        user_prompt = company/title/location/url + raw JD text   (NO keyword vocab by design)
    → _generate_content(skill_text, user_prompt)   ai_providers.py  (provider-agnostic dispatch)
    → model returns JSON  → _parse_content_json()
    → DETERMINISTIC GUARDS (free, always run):
        ground_competencies()      drop competencies not in profile.json, backfill to 6
        clean_content()            strip filler/em-dash; scope-inflation guard (frontend-only);
                                   title-inflation downgrade (non-lead); metrics-first ordering
        validate_resume_content()  employer-fabrication check (+ optional jd_keywords coverage)
    → LLM FABRICATION GUARD:
        _verify_content()          strongest reachable model rewrites unsupported summary/bullets
    → render_resume_latex()  → _compile_latex()  → PDF
```

### B. CLI agentic path — `job/cli.py:326-359`
```
SKILL.md + references/latex_template.md + profile.md
  → `claude` CLI (--append-system-prompt) emits LaTeX DIRECTLY (Bash/Write tools)
  → NO JSON, NO deterministic guards, NO fabrication verifier
```

### Provider dispatch — `job/ai_providers.py`
`_generate_content(system, user)` is **fully provider-agnostic**: `PREFERRED_PROVIDER` picks
the lead provider (anthropic / gemini / groq / openrouter / claude-cli) with automatic
fallback; the *same* prompt string is handed to whichever `_build_with_*` runs. **A new
prompt layer therefore needs zero per-provider code.**

### Matching is already LLM-driven (do NOT wire the static vocab in)
`job/skills_vocab.py` is a hand-maintained ~100-skill list with a static alias map. It powers
**only** (1) dashboard job ranking (`compute_match` → matched/missing/score on the job list,
`web.py:360`) and (2) a *dormant* post-generation coverage warning (`validate_resume_content`
only when `jd_keywords` is passed — no caller passes it). **It is deliberately NOT part of
resume generation** (`documents.py:193-206`): the builder gets raw JD + `profile.md` and lets
the model judge requirements and transferable skills. A static graph can't know "React→Next.js
is transferable"; the LLM can. Build CV stays vocab-free and model-driven — this proposal never
changes that. (Dashboard-ranking-via-LLM is a separate future initiative, out of scope here.)

### Where settings live today
| Mechanism | Scope | Shape | Used for |
|---|---|---|---|
| `profiles/<user>/.env` (`job/user_env.py`) | per-user | flat `KEY=value`, allowlisted `AI_ENV_KEYS` | API keys, `PREFERRED_PROVIDER`, `*_MODEL`, `SEMANTIC_MATCH` |
| `meta.json` (`profiles.py:108`) | per-profile | JSON, `{label}` only | display label |
| `config.yaml` | per-profile | YAML | search/blacklist |
| `db_meta` KV (`db.py`) | per-profile | `key→value` (JSON strings) | migration flags, embedding cache |

AI Settings UI reads/writes via `aiSettings.get()/save()`; **`save()` already accepts arbitrary
keys**, and `/api/ai-settings` GET/POST is the canonical channel. `SEMANTIC_MATCH` is the exact
precedent for a non-secret behavior toggle surfaced there.

---

## 2. Current Limitations (what blocks good, user-controlled output)

1. **The reach is a fixed, uncontrollable default, ambiguous at the margin (§0).** `SKILL.md`
   permits transferable framing but also warns against implying unused-tool experience; a literal
   LLM can land anywhere between a strong framing and dropping the skill, and the user can't steer
   it. This is the primary problem — not that matching is banned, but that it's unsteerable.
2. **The "how far to reach" concern has two owners that can drift** (`SKILL.md` prose +
   `_verify_content`'s hardcoded prompt). The deterministic guards are a separate, factual concern.
   No single home for "reach."
3. **Positioning is not user-controllable.** There is no dial; the stance is hard-welded prose.
4. **The build call carries no options / there's no CV-config store.** `POST /api/resume/<id>`
   has no body; per-profile behavior settings live in `config.yaml` (search/blacklist) but nothing
   holds resume-positioning intent yet.
5. **Two prompt consumers can drift.** Any stance layer must reach both the web JSON path and the
   CLI path.

---

## 3. Recommended Product Model — one stance dial, leaner prompt, more user freedom

**One dial, three stops, plus optional free text.** The dial owns the *entire* positioning
stance — it doesn't sit on top of a fixed one, it **is** the variable layer. The base prompt
keeps only immutable facts + resume-quality craft; the redundant conservatism prose comes out.

**Internal enum vs. user-facing label.** The stored value stays `conservative | balanced |
aggressive` (stable code/config contract — see §4). The *label the user reads* is decoupled,
because "Aggressive" wrongly implies "fabricate more" when the implementation forbids exactly
that. User-facing labels:

| Internal enum | User-facing label | One-line meaning |
|---|---|---|
| `conservative` | **Conservative** | Only skills & terms your profile states directly. |
| `balanced` | **Balanced** *(recommended)* | Direct + equivalent terms + strong transferable skills, framed honestly. |
| `aggressive` | **Strong Match** | Maximizes honest relevance via transferable & adjacent skills and the employer's vocabulary. |

The stances themselves:

- **Conservative** — only skills/terminology explicitly in the profile. No transferable framing.
  (For users who want a literal, understated CV.)
- **Balanced (default, recommended)** — direct experience + equivalent terminology + **strong
  transferable skills surfaced and framed as transferable**. This is where "deep React →
  Next.js-ready" gets said out loud. A meaningfully more useful default than today's behavior.
- **Strong Match** (`aggressive`) — maximize apparent relevance: transferable + adjacent skills,
  related concepts, the employer's vocabulary, and the *underlying fundamentals* argument. Still
  cannot convert a transferable match into a direct factual claim; still never touches career facts.

The dial changes **how far the generator reaches and how boldly it frames**, nothing else.

**Design principle: fewer rules, one owner per concern.** We are not adding a rule matrix. We are
moving the *one* existing "how far to reach" concern out of its two homes (`SKILL.md` prose +
verifier prompt) into one user-controlled stance, and relocating the fixed-reach prose so the
default becomes a dial.

---

## 4. Configuration Model

```python
# structured intent — NOT prompt text
@dataclass
class BuildCvConfig:
    experience_positioning: Literal["conservative", "balanced", "aggressive"] = "balanced"
    additional_instructions: str = ""          # optional, additive, sanitized, ≤ ~500 chars

    @classmethod
    def load(cls, slug=None) -> "BuildCvConfig": ...      # from config.yaml build_cv:, defaults + forward-compat
    def to_stance_block(self) -> str: ...                 # pure fn → the ONE positioning block
```

- **V1 exposes exactly one enum + one optional text field.** No ATS dial, no Recruiter-Focus
  dial — those would re-introduce the conflicting-rules problem we're removing (see §10/§13).
- **Stored per-profile in `config.yaml`** under a `build_cv:` key, via the existing
  `/api/profiles/<slug>/config` GET/POST and `_read_config_yaml`/`_write_config_yaml`
  (`web.py:157-162`). Positioning is a **per-profile/persona trait** — a "backend engineer"
  profile and a "product manager" profile should be able to reach differently — and `config.yaml`
  is exactly the per-profile store the app already uses for search/blacklist settings. This is a
  cleaner fit than the per-user `.env` (which is for API keys and account-wide toggles like
  `SEMANTIC_MATCH`) and it comes with a fully-wired read/write/API/UI path already.
  ```yaml
  # profiles/<user>/<slug>/config.yaml
  build_cv:
    experience_positioning: balanced
    additional_instructions: ""
  ```
- **`BuildCvConfig` is the domain model; `config.yaml` is its backing store.** Don't scatter
  reads of the raw YAML dict — load through `BuildCvConfig.load(slug)` so validation/defaults live
  in one place. If this later goes multi-user/SaaS with a settings table, only `load()/save()`
  change.
- **Invalid/unknown values → `balanced`** at load; missing `build_cv:` key → all defaults;
  unknown keys ignored (forward-compat).

---

## 5. UX Proposal — a new tab in Profile Settings

**Placement: a new "Resume Positioning" section in Profile Settings**, not the AI Settings page.
Rationale: positioning is a **per-profile trait** (it lives with that persona's `profile.md` and
`config.yaml`), whereas AI Settings holds account-wide provider/key config. Profile Settings
already has the exact tab mechanism we need — a `sidenav` driven by `useState<Section>`
(`ProfileSettings/index.tsx:356`), today switching `profile` / `search` / `danger`.

**Wiring (small, follows existing patterns):**
- Extend the `Section` union: `'profile' | 'search' | 'positioning' | 'danger'`.
- Add one `sidenav-item` button in the Profile group: `🎯 Resume Positioning`.
- Render a new `<PositioningSection slug={slug} />` — a `settings-card` (same component the
  Search and Profile sections use), loading via `profilesApi.getConfig(slug)` and saving via
  `profilesApi.saveConfig(slug, {...})`. Success → existing `useToast('Saved')`.
- **⚠ Read-modify-write is mandatory, not optional.** Verified against the code: the backend POST
  handler does `_write_config_yaml(config_p, data)` (web.py:630) — a **full overwrite with no
  merge**. So `saveConfig` replaces the entire `config.yaml`. If `PositioningSection` naively saves
  `{build_cv: {...}}`, it will **destroy the profile's searches, blacklist, and title_filter.** The
  section must load the *full* current config first, merge `build_cv` into it, and save the whole
  object back: `const cfg = await getConfig(slug); await saveConfig(slug, {...cfg, build_cv})`.
  `SearchSection` gets away with a single-save because it owns the whole config; a second writer to
  the same file does not. Two safe implementations — pick one in §11:
  - **(a) Frontend RMW** (chosen): PositioningSection round-trips the full config, as above.
  - **(b) Dedicated endpoint**: add `/api/profiles/<slug>/positioning` that patches only the
    `build_cv:` subtree server-side. More robust against concurrent writers, slightly more code.

```
Profile Settings
┌─ sidenav ────────┐   ┌─ Resume Positioning ─────────────────────────────────┐
│ 👤 Profile        │   │ Choose how far your resume should reach when          │
│ 🔍 Search Settings│   │ positioning your experience against each job.         │
│ 🎯 Resume         │   │                                                       │
│    Positioning ◀  │   │  ( ) Conservative   Only skills & terms your profile  │
│ ──────────        │   │                     states directly.                 │
│ ⚠ Danger Zone     │   │  (•) Balanced       Recommended. Direct experience +  │
└──────────────────┘   │                     equivalent terms + strong          │
                        │                     transferable skills, surfaced      │
                        │                     honestly (deep React → ready for   │
                        │                     Next.js).                         │
                        │  ( ) Strong Match   Maximizes alignment via            │
                        │                     transferable & adjacent skills and │
                        │                     the employer's vocabulary.         │
                        │                                                       │
                        │  ℹ Never changed, on any setting: employers, job       │
                        │    titles, dates, years of experience, locations,      │
                        │    education, certifications, and metrics. These come  │
                        │    from your profile and are always preserved exactly. │
                        │                                                       │
                        │  Additional instructions (optional)                   │
                        │  ┌─────────────────────────────────────────────────┐ │
                        │  │ e.g. "For product roles, emphasize stakeholder   │ │
                        │  │ management and roadmap ownership."               │ │
                        │  └─────────────────────────────────────────────────┘ │
                        │                                    [ Save ]           │
                        └───────────────────────────────────────────────────────┘
```

- The non-negotiables note is **always visible** and names them explicitly (employers, titles,
  dates, **years of experience**, locations, education, certs, metrics) so the user sees exactly
  what the dial can never touch. *(Engineering note: this UI promise is scoped to "the dial doesn't
  change these" — which is true, the stance block never emits facts. It is **not** a claim that all
  of them are deterministically code-guarded; per §6, dates/locations/metrics are verifier-enforced,
  not regex-enforced. The copy is honest at the user's level; don't read it as a stronger guarantee
  than §6 states.)*
- Strong Match shows one extra reassurance line: *"Makes stronger use of transferable skills and
  equivalent terminology — it never adds experience you don't have, and never changes your
  career facts."*
- Save model: follows `SearchSection`'s explicit **Save** button (Profile Settings uses
  save-on-submit, not save-on-change) for consistency within the page.
- **Labels are display-only.** The radios render the user-facing labels from the §3 table
  (Conservative / Balanced / **Strong Match**); each maps to the stored enum
  (`conservative`/`balanced`/`aggressive`) in one place in the component, so renaming a label
  never touches the config contract or the backend.

> Alternative considered: a card on the AI Settings page (save-on-change, mirrors `SEMANTIC_MATCH`).
> Rejected because it would make positioning account-wide instead of per-profile, and split
> "everything about this persona's resume" across two pages. Keep it with the profile.

---

## 6. The one immutable boundary (no setting can cross it)

The dial can reach as far as it likes on *framing*; it can never cross into *fabricated fact*.
The single load-bearing invariant:

> **No unsupported *direct experience* may be claimed.** "Experience that maps to X" may be
> surfaced (and, on higher settings, emphasized); it may **never** silently become "experience
> *with* X."

This is **surface-dependent**, and both halves stay true regardless of mode:

- **Core Competencies list** stays hard-grounded. A bare `Next.js` chip *is* an implied direct
  claim, so `ground_competencies()` (`latex_render.py:570`) still drops any skill not in the
  profile. The list is for skills the candidate actually has.
- **Prose (summary/bullets)** is where transferable framing lives: *"React/TypeScript foundation
  directly applicable to Next.js development"* is allowed on Balanced+; *"4 years of Next.js"* is
  never allowed on any setting.

**What counts as a direct claim (the line the implementation must hold).** The boundary is not
"does the string contain the JD term" — transferable framing legitimately names the JD term. The
boundary is **whether the sentence asserts the candidate *did / used / built with* the tool**.
Concrete phrasings, for tests and for the verifier prompt (`JD: Next.js`, profile has React/TS,
no Next.js):

| Phrasing | Verdict | Why |
|---|---|---|
| "React/TypeScript experience directly applicable to Next.js development" | ✅ allowed | states the bridge, not usage |
| "Strong frontend engineering background applicable to Next.js environments" | ✅ allowed | capability framing, no usage claim |
| "Well-positioned to work in Next.js given deep React/TypeScript foundation" | ✅ allowed | readiness, not history |
| "Experienced in building Next.js applications using React and TypeScript" | ❌ forbidden | asserts having built with Next.js |
| "4 years of Next.js" / "Next.js" as a Core Competency chip | ❌ forbidden | asserts tenure / implied direct claim |

The tell is the verb and its object: *applicable to / positioned for / foundation for* X = framing;
*experienced in / built / used / worked with* X = a direct claim that requires profile evidence.

**Where this line is enforced — LLM verifier, not a regex.** No deterministic guard can make this
call: the distinction is semantic, and `latex_render.py`'s guards are all regex/set-membership
(they catch competency chips, employer fabrication, and a fixed list of scope/title phrases — none
of them "applicable to vs. experienced in"). So this boundary lives in `_verify_content`
(documents.py:347), the LLM fabrication pass, on the **web path only**. That has two consequences
the proposal must own: (1) the phrasing table is the **verifier's spec**, expressed as prompt
guidance and tested behaviorally against the verifier — not a code assertion that runs on every
build; (2) on the **CLI path there is no verifier at all**, so this boundary rests entirely on
`SKILL.md` prose there (see §10). §12's tests target the verifier's behavior, not a deterministic
gate that doesn't exist.

Also always protected, outside the dial — **the non-negotiables**. Be precise about *what the
code enforces today* versus what rests on the prompt, because they differ and the proposal must
not overclaim:

- **Code-enforced (deterministic, mode-invariant):** the contact header — name, location, phone,
  email, LinkedIn, work-auth — is extracted from `profile.md` by code, never taken from the model
  (`_parse_contact_from_profile`, `latex_render.py:65-90`). Employer names are fabrication-checked:
  every experience employer must appear in the profile or the build fails
  (`validate_resume_content`, `latex_render.py:620-623`). Competency chips are grounded
  (`ground_competencies`); specific scope/title inflations are downgraded by regex.
- **Prompt-enforced only (NOT code-checked today):** experience **dates, per-role locations, and
  metrics** are rendered straight from the model's JSON without a deterministic guard comparing
  them to `profile.md` (`latex_render.py:236-245`). `SKILL.md` forbids inventing them and the LLM
  verifier can catch some, but there is **no code gate** here the way there is for employers/contact.

The dial changes **none** of these — the stance block governs only how *real skills* are framed and
never emits career facts, so V1 holds "never change years/employer/where" by construction plus the
existing employer/contact guards. But making dates/locations/metrics as hard-guaranteed as employer
names is a **separate guard to add** (§11, flagged as a known gap), not something this feature can
assume already exists. No setting — not even Strong Match — may reach career facts.

Everything else is stance, and stance belongs to the user.

---

## 7. Experience Matching Model (kept model-driven, made explicit)

Matching stays the **LLM's job** (§1) — no static engine feeds it. What changes: the taxonomy
becomes an explicit, shared vocabulary in the stance block so the model reasons consistently, and
each level defines how far a relationship may be surfaced.

| Relationship | Meaning | Conservative | Balanced | Strong Match |
|---|---|---|---|---|
| **Direct** | profile states the exact skill | use as-is | use as-is | use as-is |
| **Equivalent terminology** | same thing, JD's words (`REST APIs`↔`RESTful API development`) | keep profile's words | adopt JD wording | adopt JD wording |
| **Strong transferable** | closely-related foundation (`React/TS` → `Next.js`) | omit | **frame as transferable / "ready for"** | emphasize the bridge + fundamentals |
| **Adjacent** | same domain, weaker link | omit | omit or one soft mention | surface as transferable framing |
| **Gap** | no profile evidence | omit | omit | omit (hard rule, all modes) |

Worked examples:
- `JD: Next.js`, profile `React + TypeScript` → **strong transferable**. Balanced wording:
  *"React/TypeScript foundation directly applicable to Next.js development"* — never "4 years of
  Next.js". (This is the exact case today's fixed default may drop, depending on how the LLM
  resolves line 41's ambiguity.)
- `JD: Backlog Management`, profile *"built and prioritized team backlogs"* → **equivalent** →
  adopt "backlog management" (Balanced+).
- `JD: Data Engineering`, no evidence → **Gap** → omit on every mode.

**Internal reasoning may be more permissive than the resume claim, by design** — the model may
recognize a transferable bridge it is not allowed to assert as direct experience. (The Requirement
Map in `SKILL.md:47` already asks for this internal analysis; we keep it internal in V1. Emitting
it as structured metadata is a deferred feature — see §10.)

---

## 8. Prompt Composition — lean the base, let the stance be the only variable

**Subtract, then compose.** First relocate the fixed "how far to reach" prose out of `SKILL.md`
(and out of the verifier's implicit stance) so each concern has one home; then insert **one**
generated stance block.

**Removed / relocated from `SKILL.md` (leaning pass):**
- Delete `SKILL.md:41` ("never imply direct experience with an unused tool") and fold the *only*
  surviving hard rule — the transferable≠direct line from §6 — into the immutable priorities.
- Move the "how far to reach" stance (currently the Gap-Analysis prose + scope-precision examples)
  **out** of the fixed skill and **into** `to_stance_block()`, where the user's level selects the
  wording. Conservative regenerates today's cautious stance; Balanced/Strong Match don't.
- Keep in `SKILL.md`: the immutable factual priorities, and the *craft* rules (summary formula,
  PAR bullets, verb hierarchy, redundancy) — these are quality, not positioning, and don't conflict.

**Resulting layered prompt:**
```
[ IMMUTABLE FACTS ]        SKILL.md priorities + the one transferable≠direct rule   ← leaner
[ RESUME CRAFT ]           SKILL.md body (summary formula, PAR, verbs)              ← unchanged
[ POSITIONING STANCE ]     BuildCvConfig.to_stance_block()   ← NEW, the ONLY variable layer
[ OUTPUT CONTRACT ]        _JSON_OUTPUT_FORMAT (web) / latex_template.md (CLI)       ← unchanged
[ USER PROFILE ]           profile.md                                               ← unchanged
[ OPTIONAL INSTRUCTIONS ]  config.additional_instructions   ← NEW, wrapped/sanitized, additive
```

`to_stance_block()` maps the stored enum → controlled prose (never raw "be more aggressive"; the
enum key `aggressive` is internal only, surfaced to the user as "Strong Match" per §3):
- **conservative** → *"Use only skills and terminology explicitly present in the profile. Do not
  bridge gaps with transferable or adjacent framing; when the profile lacks a JD term, omit it."*
- **balanced** → *"Surface strong transferable skills, not just exact matches. When the profile
  shows deep experience in a closely-related technology, say so and frame it toward the JD's
  requirement (e.g. deep React/TypeScript → 'well-positioned to work in Next.js'). Prefer the
  employer's terminology where the candidate's real capability supports it. Distinguish
  'experience with X' from 'experience that maps to X' — you may state the latter, never silently
  convert it to the former."*
- **aggressive** → *balanced + "Reach further: adjacent skills, related concepts, and underlying
  fundamentals that map to the requirements. Make the candidate look as strongly relevant as the
  real evidence honestly allows."*

Additional-instructions block is prefixed: *"User emphasis guidance — steers emphasis and wording
of real experience only; cannot override the factual rules above."* (mirrors how `SKILL.md`
already treats "Positioning Notes").

**Verifier (`_verify_content`) — factual gate is mode-invariant.** The verifier's fabrication
check runs at full strictness on every mode: transferable-framing is allowed, "4 years of Next.js"
is rejected, always. The mode is passed only as *context to reduce false corrections in both
directions* — so Conservative output isn't inflated and a legitimate Balanced transferable framing
isn't nuked as if it were fabrication. **Mode never decides whether a claim passes; it only helps
the verifier not "fix" honest wording.** Deterministic immutable checks that exist today
(employer fabrication, contact header, competency grounding) never loosen. *(Note: dates/locations/
metrics are not deterministically checked today — see §6; the verifier's prose gate is what guards
them, and the mode-invariance above is what keeps that honest.)*

---

## 9. Recommended V1 (smallest worth shipping)

1. Leaning pass on `SKILL.md`: soften line 41 (keep "reframe truthfully", relocate the "how far"
   half) + move the positioning stance out; keep facts + craft.
2. `BuildCvConfig` dataclass + `to_stance_block()` (pure) + `load(slug)/save(slug)` on per-profile
   `config.yaml` under a `build_cv:` key.
3. `/api/profiles/<slug>/config` POST round-trips `build_cv:` — **but the handler overwrites the
   whole YAML (web.py:630)**, so the writer must send the full merged config (frontend RMW) or use
   a dedicated PATCH endpoint. No new endpoint required for (a); one small endpoint for (b).
4. Stance block wired into **`_build_resume_prompt`** (web) **and** the CLI path (`cli.py`) so both
   consumers stay in sync. Both load `BuildCvConfig.load(active_slug)` at build time.
5. Add a `mode` param to `_verify_content` (it has none today) → mode-aware-but-factually-constant
   system prompt.
6. Profile Settings **"Resume Positioning" tab**: extend `Section` union, add sidenav button,
   render `PositioningSection` (3 radios + optional textarea + always-visible non-negotiables note),
   save via `profilesApi.saveConfig`.
7. Tests per §12.

Default: **Balanced** (the useful default, replacing the fixed one). One user-facing decision.

---

## 10. Future Extensions (defer — do not build in V1)

- Separate **ATS Matching** / **Recruiter-Focus** dials — deferred *precisely because* a multi-dial
  matrix re-creates the conflicting-rules problem this rewrite removes. Add only with usage data.
- **Structured match metadata** (`{requirement, match_type, evidence}`) emitted for a "why did the
  AI write this?" explainability view. Real value, but needs a second artifact/parser or extra call
  — its own iteration. **No numeric confidence scores** — LLM-generated confidences are
  uncalibrated; the categorical label is honest, a `0.91` is false precision.
- Cover-letter positioning parity (same stance block, `cover-letter-skill`).
- Dashboard-ranking-via-LLM (replace/augment `skills_vocab`) — separate initiative with its own
  cost/latency design (batching, caching, cheap embeddings).

### Architectural radar: the two Build CV paths have unequal safety pipelines

This proposal makes the **stance** consistent across the web and CLI paths (V1 wires the block
into both). It does **not** equalize everything else, and that gap is worth naming explicitly:

```
Web:  LLM → JSON → deterministic guards → fabrication verifier → PDF
CLI:  LLM → LaTeX ──────────────────────────────────────────────→ PDF   (no guards, no verifier)
```

So after V1, both paths *reach the same distance* (same stance), but only the web path has the
factual net beneath it — and the §6 framing-vs-usage boundary is verifier-enforced, so on the CLI
path it rests on `SKILL.md` prose alone. The reviewer's "same validation philosophy for both" is
the right *aspiration*, but it is **not a wrapper refactor** — and the proposal should not imply it
is. Verified against the code: every guard operates on the **JSON dict** the web path produces —
`ground_competencies` on `content['core_competencies']`, `_verify_content` on `content['summary']`
/ `content['experiences'][…]['bullets']`, `validate_resume_content` on `content['experiences']`.
The CLI path has **no such structure**: it hands `claude` a LaTeX template and the model writes the
`.tex` directly via Bash/Write. To run the same guards, the CLI would have to **stop emitting LaTeX
and emit JSON first** — i.e. drop `latex_template.md`, append `_JSON_OUTPUT_FORMAT`, parse the
response, run the guards, then render JSON→LaTeX. That is the web path's architecture; unifying
means the CLI **converges onto it**, not that we wrap a net around the existing LaTeX flow. Real
work, its own project — out of scope for V1, flagged as convergence (not a wrapper) so the cost
isn't underestimated.

---

## 11. Implementation Plan (ordered)

1. **Lean `SKILL.md`**: soften/relocate line 41 (it currently reads *"Adjacent experience exists →
   reframe truthfully…; never imply direct experience with an unused tool"* — keep the "reframe
   truthfully" half, move the "how far" half into the stance block); relocate the scope-precision
   stance (line 43); fold transferable≠direct into the immutable priorities. Keep the craft rules
   (summary formula 73-86, PAR 95-99, verbs 117-122).
2. **Backend config**: `job/build_cv_config.py` — `BuildCvConfig` dataclass, validation,
   `load(slug)/save(slug)` reading/writing the `build_cv:` key in that profile's `config.yaml`
   (reuse `profiles`' config path helpers), `to_stance_block()`.
3. **Prompt builder**: inject stance block in `documents.py::_build_resume_prompt` (naturally
   between the profile append and `_JSON_OUTPUT_FORMAT`, ~documents.py:184-185) and append the same
   block + guarded additional-instructions in `cli.py` (~343-359). **Code change to signature:**
   `_verify_content(content, profile_text)` (documents.py:347) takes **no mode today** — add a
   `mode`/stance parameter and thread the stance context into its hardcoded system prompt (373-409).
   Keep the factual gate constant across modes.
4. **Routes + safe write**: extend the existing `/api/profiles/<slug>/config` POST to round-trip
   `build_cv:` (validate the enum + clamp instructions length). **The POST handler overwrites the
   whole YAML (web.py:630, no merge)** — so either (a) require callers to send the full merged
   config (frontend RMW, §5a), or (b) add a dedicated `/api/profiles/<slug>/positioning` PATCH that
   merges only `build_cv:` server-side (§5b). Pick one; (a) is less code, (b) is safer under
   concurrent writers. No `/api/resume/<id>` change (config read server-side at build time).
5. **Frontend**: `SearchConfig` type gains an optional `build_cv` field; add the "Resume
   Positioning" `Section` + sidenav button + `PositioningSection` component. **It must
   read-modify-write** (`getConfig` → merge `build_cv` → `saveConfig`) so it doesn't clobber
   search/blacklist — or call the dedicated PATCH endpoint from step 4b.
6. **Validation**: mode-aware verifier prompt with constant factual gate; confirm deterministic
   guards untouched.
7. **Tests**: §12.
8. **Migration**: none — a `config.yaml` with no `build_cv:` key ⇒ Balanced defaults;
   forward-compatible load.

**Known gap, not blocking V1 (from §6):** experience **dates, per-role locations, and metrics** are
rendered from LLM JSON with **no deterministic guard** against `profile.md` today (only employer
names + contact header are code-checked). This feature does not make them worse — the stance block
never emits facts — but if we want them as hard-guaranteed as employers, add a `validate_dates_
locations_metrics(content, profile_text)` deterministic check alongside the employer check
(latex_render.py:620). Sequenced *after* V1 so the config feature isn't blocked on a pre-existing
guard gap; called out here so it's a tracked decision, not a silent hole.

---

## 12. Tests

**Reality check on the test harness (verified against the code).** The suite runs fully offline
(`tests/conftest.py`): `_generate_content` is stubbed as `lambda *a, **k: json.dumps(_CONTENT)`
(test_build_document.py:63) — it **ignores the prompt and returns fixed content**. Existing tests
assert the *rendering pipeline* and *verifier-correction logic*, not generation behavior. There is
no real-model call and no golden-output harness.

**Consequence — the reviewer's "behavioral output" test cannot be built as stated.** A test that
asserts "Conservative → no Next.js in output, Balanced → transferable framing in output" is
**impossible** against a stub whose output is independent of the mode: only the *prompt* changes,
not what the test sees come back. So we can't have it both ways — "test behavior, not prompt
wording" collides with an offline fixed-output stub. Three honest options:

| Option | What it tests | Cost |
|---|---|---|
| **A. Prompt-carries-stance** (chosen for V1) | mode → the assembled system prompt contains the right stance block; additional-instructions wrapped with the non-override guard; verifier system prompt is mode-aware | free, deterministic, offline |
| **B. Mode-keyed stub** | a stub that returns *different* canned JSON per detected mode, then assert the pipeline/guards handle each | cheap but tests the fixture, not the model — low value |
| **C. Golden / real-model eval** | actual mode-dependent generation quality | needs network or committed golden outputs; non-deterministic |

**V1 ships Option A and says so plainly:** unit tests assert the *prompt* is correctly composed
(this is legitimately what a unit test can verify offline), plus the deterministic guards and the
verifier-correction behavior, which *are* testable with fixed fixtures. We do **not** dress a
prompt-content assertion up as a behavioral one.

**A — prompt/stance composition (offline, deterministic):**
- `to_stance_block()` (pure): conservative vs balanced vs aggressive produce *distinguishable*
  blocks; additional-instructions wrapped with the non-override guard.
- `_build_resume_prompt` with each mode → assembled prompt contains that mode's stance block and,
  when set, the wrapped instructions. (Prompt assertion — honestly labeled as such.)
- `_verify_content` receives the mode and its system prompt reflects it (once threaded — see §11).

**Guard / verifier behavior (offline, uses fixed fixtures — genuinely behavioral):**
- **Verifier**: feed content containing a fabricated usage claim ("4 years of Next.js") → verifier
  rewrites/removes it; feed a legitimate transferable framing ("React foundation applicable to
  Next.js") → survives, not "corrected" away. Parametrize the mode passed as context; assert the
  factual gate does **not** loosen by mode. (Stub the verifier model with canned before/after pairs.)
- **Competency grounding**: `ground_competencies` still drops an ungrounded `Next.js` chip on every
  mode.
- **Employer/contact invariants**: employer fabrication still fails the build; contact header comes
  from `profile.md` — unaffected by mode.

**Config (offline):** defaults; each level round-trips save/load; invalid enum → balanced; unknown
keys ignored; missing `build_cv:` key → defaults; **saving `build_cv` preserves existing
search/blacklist keys** (regression test for the read-modify-write fix in §5/§11).

> **The distinction the §6 phrasing table draws (framing vs. usage claim) is a *verifier-behavior*
> contract, tested via Option A's verifier tests — not a deterministic code gate.** And the truly
> decisive validation is not a unit test at all: **does Balanced produce measurably better CVs than
> Conservative on real jobs without raising factual-error rate?** That's an offline eval / A-B on
> real JD+profile pairs (Option C), run once the feature exists. Flagged so it isn't mistaken for
> something the unit suite covers.

---

## 13. Product Decisions (answers)

1. **Four levels?** No — three (internal enum `conservative`/`balanced`/`aggressive`; shown as
   Conservative / Balanced / **Strong Match**).
2. **"Maximum Match" ≠ "Strong Match"?** Not meaningfully — with facts immutable, the only thing
   a "Maximum" tier could add over Strong Match is transferable→direct conversion, which we forbid.
   Drop it.
3. **ATS matching a separate setting?** No in V1 — a second dial re-introduces conflicting rules;
   the stance dial already governs terminology alignment.
4. **V1 settings?** Experience Positioning (enum) + optional Additional Instructions.
5. **Custom instructions?** Yes — additive, sanitized, wrapped with a non-override guard.
6. **Immutable?** The single boundary in §6: no unsupported *direct experience*. The dial touches
   none of the career facts (employers, titles, dates, years/tenure, locations, education, certs,
   metrics, contact, work-auth). But be precise (§6): only **contact header + employer names** are
   *deterministically* code-enforced today; **dates/locations/metrics are prompt+verifier-enforced**
   with no code gate yet (a tracked gap, §11), and the framing-vs-usage line is **verifier-enforced,
   not regex**. V1 keeps all of them off the dial; hardening the un-gated ones is sequenced after.
7. **Default?** Balanced — deliberately the *useful* default, replacing today's fixed reach.
8. **Explain trade-offs / where in the UI?** A **"Resume Positioning" tab in Profile Settings**
   (per-profile, beside Profile and Search) — not AI Settings. Labels are display-only (Conservative
   / Balanced / **Strong Match**) over the stable internal enum. Always-visible non-negotiables note
   naming years/employers/dates/locations; extra reassurance line on Strong Match.
9. **What I'd ship:** §9 — lean the prompt, one stance dial (Balanced default) + optional text,
   per-profile `config.yaml` storage, one stance block into both consumers, mode-aware/
   factually-constant verifier, immutable guards untouched, surfaced as a Profile Settings tab.

---

## 14. Engineering Constraints (honored)

- Raw system prompt never exposed — user sets structured intent; `SKILL.md` stays server-side.
- **Prompt gets leaner, not heavier** — one owner per concern; the ambiguous/duplicated "how far"
  guidance (prose ↔ verifier) is consolidated into the stance block.
- No per-provider duplication — the stance block rides the provider-agnostic `_generate_content`.
- Config cannot cross the factual boundary — the dial never emits facts, so §6 holds on every mode
  by construction; the verifier's factual gate stays mode-invariant. (Enforcement strength is honest
  about itself: code-enforced for employers/contact, verifier-enforced for framing and for
  dates/metrics — the un-gated ones flagged in §6/§11, not papered over.)
- Structured config over free-form prompt editing — one enum + one bounded, guarded text field.
- `BuildCvConfig` is the domain model; per-profile `config.yaml` (`build_cv:` key) is its backing
  store — load through `BuildCvConfig.load(slug)`, never scatter raw-YAML reads.
- Not over-engineered — one user decision; no conflicting rule matrix.
