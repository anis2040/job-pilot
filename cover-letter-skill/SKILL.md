---
name: yassine-cover-letter
description: >
  Generates a tailored, human-sounding cover letter for Yassine Helaoui based on a job description
  and the already-generated resume for that role.
---

# Cover Letter Builder — Yassine Helaoui

## Your Role

Write a cover letter that sounds like a real person wrote it, not a template. Three tight paragraphs. No filler. The goal is to get a US recruiter to pick up the phone for someone whose entire work history is in Tunisia.

---

## Reference Data

`profile.md` is embedded in the system prompt. Use it directly — do not read it from disk.

The resume for this role is at `../resumes/<CompanyName>/Yassine_Helaoui_Resume.tex`. Read it before writing — the cover letter must not repeat bullet points verbatim, but must be consistent with what was emphasized.

---

## Three-Paragraph Structure (strict)

### Paragraph 1 — The hook (3–4 sentences)

Open with the specific role and company, then immediately name the most recognizable client work. Do not open with "I am writing to express my interest." Do not open with your job title.

The Tunisia background needs to be reframed here, not hidden:
- Name AIG France and MAIF Vie as the anchor — AIG is US-headquartered and immediately recognizable. Lead with it.
- Frame the work as delivering for global enterprise clients, not as working for a Tunisian firm.
- State work authorization in this paragraph: "I'm a green card holder — no sponsorship needed." One sentence, matter-of-fact.

### Paragraph 2 — The evidence (4–5 sentences)

Pick the 2–3 strongest, most relevant things from the resume and expand on the *why*, not just the *what*. The resume lists outcomes; the cover letter explains the context that made them hard to achieve and the judgment calls that got there.

Rules:
- Do not list bullets. Write in prose.
- At least one sentence must reference a named client (AIG France or MAIF Vie) with a specific outcome from the profile.
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
- **Single employer framing:** Yassine has one employer (Vermeg) over nearly 5 years. Address this proactively — frame as platform depth and client diversity, not stagnation.
- **English-language delivery:** If any work was delivered in English (documentation, stakeholder communication), surface it naturally — it closes the language assumption without stating it directly.

---

## Output Format — LaTeX Letter

Use a clean LaTeX letter class. No colors, no rules, no header bar — this is a letter, not a branded document.

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
\noindent Yassine Helaoui\\
Chicago, IL $\cdot$ +1 312-351-4880 $\cdot$
\href{mailto:yassinehelaoui4@gmail.com}{yassinehelaoui4@gmail.com} $\cdot$
\href{https://www.linkedin.com/in/yassinehelaoui}{LinkedIn}

\end{letter}
\end{document}
```

**Output directory:** same folder as the resume. Save as:
- `../resumes/<CompanyName>/Yassine_Helaoui_Cover_Letter.tex`

---

## Compile to PDF

```bash
export PATH="/usr/local/texlive/2026basic/bin/universal-darwin:$PATH" && \
cd ../resumes/<CompanyName> && \
pdflatex -interaction=nonstopmode Yassine_Helaoui_Cover_Letter.tex && \
find . -maxdepth 1 -name "Yassine_Helaoui_Cover_Letter.*" ! -name "*.pdf" ! -name "*.tex" -delete && \
ls Yassine_Helaoui_Cover_Letter.pdf
```

If pdflatex is not found, it is already installed from the resume build — re-export the PATH and retry.

If compilation fails, fix LaTeX errors (unescaped `&`, `%`, `_`, `#`; unclosed environments) and retry.

---

## Deliver

1. Confirm the PDF exists at `../resumes/<CompanyName>/Yassine_Helaoui_Cover_Letter.pdf`
2. Report the output paths:
   - `../resumes/<CompanyName>/Yassine_Helaoui_Cover_Letter.pdf`
   - `../resumes/<CompanyName>/Yassine_Helaoui_Cover_Letter.tex`
3. Print the plain-text body of the letter (the three paragraphs only, no LaTeX) so it can be pasted into an online application form.
