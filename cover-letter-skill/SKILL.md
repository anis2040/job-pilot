---
name: cover-letter
description: >
  Generates a tailored, human-sounding cover letter based on a job description
  and the already-generated resume for that role.
---

# Cover Letter Builder

## Your Role

Write a cover letter that sounds like a real person wrote it, not a template. Three tight paragraphs. No filler. The goal is to get a recruiter to pick up the phone.

---

## Reference Data

`profile.md` is embedded in the system prompt below under the heading `## profile.md (embedded)`.

**Before doing anything else, verify it is present:**
- If `## profile.md (embedded)` is missing or empty: stop immediately and output "ERROR: profile.md is not set up. Please complete the setup wizard at http://localhost:5050/setup"
- If profile.md contains only the example template (no real name, placeholder email): stop and output "ERROR: profile.md contains only the example template. Please fill in your real profile at http://localhost:5050/setup"

When present, `profile.md` is the single source of truth. Never fabricate clients, projects, metrics, or tools not listed there.

The resume for this role is at `../resumes/<CompanyName>/{{NAME_SLUG}}_Resume.tex`. Read it before writing — the cover letter must not repeat bullet points verbatim, but must be consistent with what was emphasized.

---

## Three-Paragraph Structure (strict)

### Paragraph 1 — The hook (3–4 sentences)

Open with the specific role and company, then immediately name the most recognizable client or project work from `profile.md`. Do not open with "I am writing to express my interest." Do not open with the job title.

If `profile.md` confirms US work authorization, state it here matter-of-factly in one sentence: "I'm a [green card holder / US citizen] — no sponsorship needed."

### Paragraph 2 — The evidence (4–5 sentences)

Pick the 2–3 strongest, most relevant things from the resume and expand on the *why*, not just the *what*. The resume lists outcomes; the cover letter explains the context that made them hard to achieve and the judgment calls that got there.

Rules:
- Do not list bullets. Write in prose.
- At least one sentence must reference a specific named client or project from `profile.md` with a concrete outcome.
- If the JD emphasizes a specific skill or methodology, connect it to a concrete moment from the profile.
- No metrics that are not in `profile.md`.

### Paragraph 3 — The close (2–3 sentences)

Express genuine interest in this specific company/role — reference something real from the JD (a product area, a stated challenge, a team structure). Do not use "I look forward to hearing from you." Close with a direct, confident sentence about next steps.

---

## Writing Rules

- **Plain voice.** Write like a person, not a career coach. Short sentences. No em-dashes.
- **No AI tells:** no "I am passionate about", "I am excited to", "proven track record", "dynamic environment", "leverage my skills", "synergy", or any phrase that sounds generated.
- **No repetition from the resume.** The cover letter adds context; it does not restate bullets.
- **Never fabricate.** Every claim must trace to `profile.md`. No clients, projects, metrics, or tools not listed there.

---

## Output Format — LaTeX Letter

```latex
\documentclass[11pt,a4paper]{letter}
\usepackage[margin=1in]{geometry}
\usepackage[hidelinks]{hyperref}
\usepackage{microtype}
\pagestyle{empty}

\begin{document}

\begin{letter}{Hiring Manager\\<CompanyName>}

\opening{Dear Hiring Manager,}

% Paragraph 1

% Paragraph 2

% Paragraph 3

\closing{Best regards,}

\vspace{1em}
\noindent {{CANDIDATE_NAME}}\\
% Contact details from profile.md

\end{letter}
\end{document}
```

**Output directory:** same folder as the resume. Save as:
- `../resumes/<CompanyName>/{{NAME_SLUG}}_Cover_Letter.tex`

---

## Compile to PDF

```bash
export PATH="/usr/local/texlive/2026basic/bin/universal-darwin:$PATH" && \
cd ../resumes/<CompanyName> && \
pdflatex -interaction=nonstopmode {{NAME_SLUG}}_Cover_Letter.tex && \
find . -maxdepth 1 -name "{{NAME_SLUG}}_Cover_Letter.*" ! -name "*.pdf" ! -name "*.tex" -delete && \
ls {{NAME_SLUG}}_Cover_Letter.pdf
```

If pdflatex is not found, it is already installed from the resume build — re-export the PATH and retry.

If compilation fails, fix LaTeX errors (unescaped `&`, `%`, `_`, `#`; unclosed environments) and retry.

---

## Deliver

1. Confirm the PDF exists at `../resumes/<CompanyName>/{{NAME_SLUG}}_Cover_Letter.pdf`
2. Report the output paths:
   - `../resumes/<CompanyName>/{{NAME_SLUG}}_Cover_Letter.pdf`
   - `../resumes/<CompanyName>/{{NAME_SLUG}}_Cover_Letter.tex`
3. Print the plain-text body of the letter (the three paragraphs only, no LaTeX) so it can be pasted into an online application form.
