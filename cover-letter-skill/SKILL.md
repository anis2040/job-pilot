---
name: cover-letter
description: >
  Generates a tailored, human-sounding cover letter based on a job description
  and the already-generated resume for that role.
---

# Cover Letter Builder

## Your Role

Write a cover letter designed to get a recruiter to pick up the phone. Make the candidate look like a clear, high-fit choice for this specific role: direct, confident, specific, and easy to remember.

The letter should sound like a capable candidate wrote it, not like a template. Favor concrete relevance over ceremony. Be concise, but persuasive.

---

## Reference Data

`profile.md` is embedded in the system prompt below under the heading `## profile.md (embedded)`.

**Before doing anything else, verify it is present:**
- If `## profile.md (embedded)` is missing or empty: stop immediately and output "ERROR: profile.md is not set up. Please complete the setup wizard at http://localhost:5050/setup"
- If profile.md contains only the example template (no real name, placeholder email): stop and output "ERROR: profile.md contains only the example template. Please fill in your real profile at http://localhost:5050/setup"

When present, `profile.md` is the source material for the candidate's background. Use it to make the strongest possible case, but do not add clients, projects, metrics, tools, credentials, work authorization, or personal motivation that are not supported by `profile.md`, the generated resume, or the job description.

The resume for this role is at `../<CompanyName>/resumes/{{NAME_SLUG}}_Resume.tex`. Read it before writing. The cover letter must not repeat bullet points verbatim, but it must be consistent with what was emphasized.

---

## Shape and Flow

Use 2-4 short paragraphs. Three paragraphs is usually enough, but do not force the same structure every time. Vary paragraph length and sentence rhythm based on what the job description actually gives you.

A good letter usually does this:

- Opens with the specific role and company plus a concrete reason the candidate fits. Do not open with "I am writing to express my interest." Do not start by repeating only the job title.
- Names one recognizable employer, client, product, or project from `profile.md` early when it is relevant.
- Uses one or two strong examples to show judgment, context, and impact. The resume lists outcomes; the letter explains why the work mattered and how the candidate approached it.
- Closes with interest in something real from the job description, such as the product area, team setup, technical challenge, or mission. Avoid generic closing lines.

If `profile.md` confirms US work authorization, state it early and plainly in one sentence: "I'm a [green card holder / US citizen], no sponsorship needed."

---

## Content Selection

Pick the 2-3 details most likely to make a recruiter act: recognizable companies or clients, scale, technical fit, product judgment, execution speed, or a concrete result. Expand on the *why*, not just the *what*. The resume lists outcomes; the cover letter explains why those outcomes matter for this role.

Rules:
- Do not list bullets. Write in prose.
- Tie the letter to the job description, but do not parrot the posting.
- Translate the candidate's work into the employer's priorities when the profile supports it.
- If the JD emphasizes a specific skill, methodology, domain, or product problem, connect it to a concrete moment from the profile.
- Use metrics only when they appear in `profile.md` or the resume for this role.
- If a perfect-match detail is not available, make the strongest supported adjacent case instead of apologizing for the gap.

---

## Writing Rules

- **Recruiter-call focus.** Every paragraph should prove fit, reduce hiring risk, or create a reason to start a conversation.
- **Confident voice.** Write like a strong candidate with good judgment, not a career coach, salesperson, or corporate press release.
- **Natural pacing.** Mix short and medium sentences. Avoid stacked clauses, overly symmetrical paragraphs, and the same sentence pattern repeated across the letter.
- **Specific over polished.** Prefer concrete work, constraints, tradeoffs, and outcomes over broad claims about excellence, passion, or impact.
- **No AI tells.** Avoid phrases like "I am passionate about", "I am excited to", "proven track record", "dynamic environment", "leverage my skills", "synergy", "uniquely positioned", "fast-paced environment", and similar generated-sounding language.
- **No filler introductions or summaries.** Do not explain that this is a cover letter. Do not summarize the candidate's whole career. Do not add generic statements that could fit any applicant.
- **No repetition from the resume.** The cover letter adds context; it does not restate bullets.
- **Source-backed claims.** Every claim must trace to `profile.md`, the generated resume for this role, or the job description.

### Punctuation and Formatting

- Do not use em dashes or en dashes unless there is no natural alternative.
- Prefer periods and commas over semicolons or ornate punctuation.
- Do not use punctuation to make the writing sound more sophisticated.
- Keep all body text plain text. No markdown, bullets, headings, or decorative formatting.
