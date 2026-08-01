# LaTeX Template — Resume

This is the base LaTeX template. Copy this shell and replace the body
content only — do not change the preamble, colors, or structural commands.

## Visual spec (from PDF)

- **Paper:** A4, 1 inch margins all sides
- **Name:** `\LARGE\textbf`, centered, top of page
- **Contact line:** 10pt, centered, em-dashes as separators, email and LinkedIn in blue hyperlinks
- **Section headings:** bold, `\large`, color `#4472C4` (headerblue), followed by full-width `\titlerule`
- **Section spacing:** ~10pt above heading, 4pt below rule before content
- **Job title line:** `\textbf{Title} -- \textit{Company} -- \textit{Location}` left-aligned, date `\hfill` right
- **Bullets:** `\begin{itemize}[leftmargin=*]`, no extra indent, bullet character `•`
- **Key Projects sub-label:** `\textbf{Key Projects:}` on its own line, then itemize
- **Education entries:** `\textbf{Degree}`, institution, em-dash, year — two lines, no bullets
- **Certifications:** `\textbf{Cert name}`, issuer — one line, no bullets
- **Page style:** `\pagestyle{empty}` (no page numbers)
- **Font:** default LaTeX (Computer Modern), 11pt base

---

## Full LaTeX Shell

```latex
\documentclass[11pt,a4paper]{article}

\usepackage[margin=1in]{geometry}
\usepackage{parskip}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{xcolor}
\usepackage[hidelinks]{hyperref}
\usepackage{microtype}

% Section heading color — matches PDF blue
\definecolor{headerblue}{HTML}{4472C4}

% Section heading style: bold, blue, full-width rule beneath
\titleformat{\section}
  {\bfseries\large\color{headerblue}}
  {}{0em}{}
  [\color{headerblue}\titlerule]
\titlespacing{\section}{0pt}{10pt}{4pt}

\pagestyle{empty}

\setlist[itemize]{leftmargin=*, itemsep=1pt, parsep=0pt, topsep=3pt}

\begin{document}

% ── HEADER ──────────────────────────────────────────────────
\begin{center}
  {\LARGE\textbf{CANDIDATE\_NAME}}\\[3pt]
  {\small
    CITY, STATE\ $\cdot$\ PHONE\ $\cdot$\
    \href{mailto:EMAIL}{\color{headerblue}EMAIL}\ $\cdot$\
    \href{LINKEDIN\_URL}{\color{headerblue}LinkedIn}
  }
\end{center}

% ── PROFESSIONAL SUMMARY ────────────────────────────────────
\section{Professional Summary}

% REPLACE: 3–5 sentence summary tailored to the JD

% ── CORE COMPETENCIES ───────────────────────────────────────
\section{Core Competencies}

\begin{itemize}
  \item % competency 1
  \item % competency 2
  % ... up to ~12 items
\end{itemize}

% ── PROFESSIONAL EXPERIENCE ─────────────────────────────────
\section{Professional Experience}

\noindent
\textbf{ROLE\_TITLE} -- \textit{EMPLOYER} -- \textit{LOCATION} \hfill \textit{START\_DATE -- END\_DATE}

\begin{itemize}
  \item % bullet 1
  \item % bullet 2
  % 6–8 bullets max
\end{itemize}

\medskip
\noindent\textbf{Key Projects:}

\begin{itemize}
  \item \textbf{PROJECT\_1:} % scope/objective + outcome
  \item \textbf{PROJECT\_2:} % scope/objective + outcome
\end{itemize}

% ── EDUCATION ───────────────────────────────────────────────
\section{Education}

\noindent
\textbf{DEGREE\_1}, INSTITUTION\_1 \hfill YEAR\_1\\
\textbf{DEGREE\_2}, INSTITUTION\_2 \hfill YEAR\_2

% ── CERTIFICATIONS ──────────────────────────────────────────
\section{Certifications}

\noindent
\textbf{CERTIFICATION\_NAME}, ISSUER

\end{document}
```

---

## Notes for the skill

- Replace all `CANDIDATE_NAME`, `ROLE_TITLE`, `EMPLOYER`, etc. placeholders with actual content from profile.md
- Escape special characters: `&` → `\&`, `%` → `\%`, `#` → `\#`, `_` → `\_`
- Do not add any packages beyond those listed above
- Compile with: `pdflatex -interaction=nonstopmode {{NAME_SLUG}}_Resume.tex`
