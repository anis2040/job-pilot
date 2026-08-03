"""Deterministic LaTeX rendering for resumes.

The resume LLM call returns structured JSON *content* (summary, competencies,
experiences, …); this module renders the final .tex from a fixed template.
Escaping, preamble, layout and structure are all owned here — the model never
emits LaTeX, which eliminates the whole class of compile errors weak models
produce (unescaped specials, broken preambles, unbalanced braces).

Contact details and the candidate name are extracted from profile.md by code,
never taken from the model, so they can't be fabricated.
"""
from __future__ import annotations
import json as _json
import re

from .profiles import name_from_markdown


class ResumeParseError(ValueError):
    """Raised when the model's JSON content is missing, malformed, or invalid."""


# ── Escaping ────────────────────────────────────────────────────────────────

_LATEX_SPECIAL = {
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "$": r"\$",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _latex_escape(text: str) -> str:
    """Escape LaTeX special characters in a plain-text content string.

    Backslash is handled via a sentinel so the braces in its replacement
    (\\textbackslash{}) aren't themselves re-escaped by the { } rules.
    Applied to every content field, so "C++", "R&D", "100%", "$1M" render.
    """
    if not text:
        return ""
    _SENTINEL = "\x00BS\x00"
    text = text.replace("\\", _SENTINEL)
    for ch, rep in _LATEX_SPECIAL.items():
        text = text.replace(ch, rep)
    return text.replace(_SENTINEL, r"\textbackslash{}")


def _latex_escape_url(url: str) -> str:
    """Escape a URL for use inside \\href{...}. Only % # and backslash are
    problematic in the argument; other URL chars (/, ?, =, _, &) are fine there
    and must NOT be text-escaped or the link breaks."""
    if not url:
        return ""
    return url.replace("\\", "").replace("%", r"\%").replace("#", r"\#")


# ── Contact extraction from profile.md ────────────────────────────────────────

def _parse_contact_from_profile(profile_text: str) -> dict:
    """Pull contact fields from profile.md's `## Contact` section.

    Name reuses profiles.name_from_markdown (single source of truth); the rest
    are simple `- Field: value` lines. Missing fields come back as "".
    """
    result = {
        "name": name_from_markdown(profile_text) or "",
        "location": "",
        "phone": "",
        "email": "",
        "linkedin_url": "",
        "work_auth": "",
    }
    patterns = {
        "location":     r"^-\s*Location:\s*(.+)$",
        "phone":        r"^-\s*Phone:\s*(.+)$",
        "email":        r"^-\s*Email:\s*(.+)$",
        "linkedin_url": r"^-\s*LinkedIn:\s*(\S+)",
        "work_auth":    r"^-\s*Work authorization:\s*(.+)$",
    }
    for key, pat in patterns.items():
        m = re.search(pat, profile_text, re.IGNORECASE | re.MULTILINE)
        if m:
            result[key] = m.group(1).strip()
    return result


# ── JSON parsing + validation ─────────────────────────────────────────────────

def _parse_content_json(text: str) -> dict:
    """Extract and validate the resume content JSON from a model response.

    Tolerant of ```json fences, leading prose, and trailing text — scans for the
    first balanced {...} object. Raises ResumeParseError on anything unusable.
    """
    if not text:
        raise ResumeParseError("Empty response")

    # Prefer a fenced ```json block if present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None

    if candidate is None:
        # Scan for the first balanced top-level object.
        start = text.find("{")
        if start == -1:
            raise ResumeParseError("No JSON object found in response")
        depth = 0
        end = -1
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == -1:
            raise ResumeParseError("Unclosed JSON object in response")
        candidate = text[start:end]

    try:
        data = _json.loads(candidate)
    except _json.JSONDecodeError as e:
        raise ResumeParseError(f"Invalid JSON: {e}") from e

    _validate_resume_content(data)
    return data


def _validate_resume_content(data: dict) -> None:
    if not isinstance(data, dict):
        raise ResumeParseError("Top-level JSON must be an object")
    for field in ("company", "summary", "core_competencies", "experiences", "education"):
        if field not in data or not data[field]:
            raise ResumeParseError(f"Missing or empty required field: {field}")
    if not isinstance(data["core_competencies"], list):
        raise ResumeParseError("core_competencies must be a list")
    if not isinstance(data["experiences"], list) or not data["experiences"]:
        raise ResumeParseError("experiences must be a non-empty list")
    for i, exp in enumerate(data["experiences"]):
        if not isinstance(exp, dict):
            raise ResumeParseError(f"experiences[{i}] must be an object")
        for key in ("title", "employer", "dates", "bullets"):
            if key not in exp or not exp[key]:
                raise ResumeParseError(f"experiences[{i}] missing '{key}'")
        if not isinstance(exp["bullets"], list):
            raise ResumeParseError(f"experiences[{i}].bullets must be a list")


# ── Rendering ─────────────────────────────────────────────────────────────────

_PREAMBLE = r"""\documentclass[11pt,a4paper]{{article}}

\usepackage[margin={margin}]{{geometry}}
\usepackage{{parskip}}
\usepackage{{enumitem}}
\usepackage{{titlesec}}
\usepackage{{xcolor}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{microtype}}

\definecolor{{headerblue}}{{HTML}}{{4472C4}}

\titleformat{{\section}}
  {{\bfseries\large\color{{headerblue}}}}
  {{}}{{0em}}{{}}
  [\color{{headerblue}}\titlerule]
\titlespacing{{\section}}{{0pt}}{{10pt}}{{4pt}}

\pagestyle{{empty}}

\setlist[itemize]{{leftmargin=*, itemsep={itemsep}, parsep=0pt, topsep=3pt}}

\begin{{document}}
"""

_ALLOWED_MARGINS = {"1in", "0.75in", "0.5in"}
_ALLOWED_ITEMSEP = {"3pt", "2pt", "1pt", "0pt"}


def _render_header(contact: dict) -> str:
    name = _latex_escape(contact.get("name") or "Candidate")
    bits = []
    if contact.get("location"):
        bits.append(_latex_escape(contact["location"]))
    if contact.get("phone"):
        bits.append(_latex_escape(contact["phone"]))
    if contact.get("email"):
        email = _latex_escape(contact["email"])
        bits.append(rf"\href{{mailto:{_latex_escape_url(contact['email'])}}}{{\color{{headerblue}}{email}}}")
    if contact.get("linkedin_url"):
        bits.append(rf"\href{{{_latex_escape_url(contact['linkedin_url'])}}}{{\color{{headerblue}}LinkedIn}}")
    sep = r"\ $\cdot$\ "
    contact_line = sep.join(bits)
    header = (
        "% ── HEADER ──\n"
        "\\begin{center}\n"
        f"  {{\\LARGE\\textbf{{{name}}}}}\\\\[3pt]\n"
        f"  {{\\small\n    {contact_line}\n  }}\n"
        "\\end{center}"
    )
    if contact.get("work_auth"):
        header += (
            "\n\\begin{center}\n"
            f"  {{\\small {_latex_escape(contact['work_auth'])}}}\n"
            "\\end{center}"
        )
    return header


def _render_experience(exp: dict) -> str:
    title = _latex_escape(exp.get("title", ""))
    employer = _latex_escape(exp.get("employer", ""))
    location = _latex_escape(exp.get("location", ""))
    dates = _latex_escape(exp.get("dates", ""))
    head = "\\noindent\n"
    if location:
        head += rf"\textbf{{{title}}} -- \textit{{{employer}}} -- \textit{{{location}}} \hfill \textit{{{dates}}}"
    else:
        head += rf"\textbf{{{title}}} -- \textit{{{employer}}} \hfill \textit{{{dates}}}"
    parts = [head]

    bullets = [b for b in exp.get("bullets", []) if b and b.strip()]
    if bullets:
        parts.append("\\begin{itemize}")
        parts.extend(f"  \\item {_latex_escape(b)}" for b in bullets)
        parts.append("\\end{itemize}")

    projects = [p for p in (exp.get("projects") or []) if p and p.get("name")]
    if projects:
        parts.append("\\medskip\n\\noindent\\textbf{Key Projects:}")
        parts.append("\\begin{itemize}")
        for p in projects:
            name = _latex_escape(p.get("name", ""))
            desc = _latex_escape(p.get("description", ""))
            parts.append(rf"  \item \textbf{{{name}:}} {desc}")
        parts.append("\\end{itemize}")
    return "\n".join(parts)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def validate_resume_content(content: dict, profile_text: str, jd_keywords: list | None = None) -> list[str]:
    """Deterministic post-generation checks. Returns a list of human-readable
    warnings (empty = clean). Non-fatal: the resume is already rendered — these
    surface likely fabrication and thin ATS coverage for logging/UI.

    Two high-signal checks (chosen to avoid false positives):
    - Every experience employer must appear in profile.md (catches invented jobs).
    - Report which detected JD keywords the resume did NOT cover.
    """
    warnings: list[str] = []
    prof = _norm(profile_text)

    for exp in content.get("experiences", []):
        employer = (exp.get("employer") or "").strip()
        if employer and _norm(employer) not in prof:
            warnings.append(f"Employer not found in profile (possible fabrication): {employer!r}")

    if jd_keywords:
        blob = _norm(" ".join([
            content.get("summary", ""),
            " ".join(content.get("core_competencies", [])),
            " ".join(b for e in content.get("experiences", []) for b in e.get("bullets", [])),
        ]))
        missed = [k for k in jd_keywords if _norm(k) not in blob]
        if missed:
            covered = len(jd_keywords) - len(missed)
            warnings.append(
                f"ATS: covered {covered}/{len(jd_keywords)} detected JD keywords; "
                f"missing: {', '.join(missed)}"
            )
    return warnings


def render_resume_latex(content: dict, profile_text: str) -> str:
    """Assemble a complete, compilable .tex document from validated content."""
    contact = _parse_contact_from_profile(profile_text)

    margin = content.get("margin") if content.get("margin") in _ALLOWED_MARGINS else "0.75in"
    itemsep = content.get("itemsep") if content.get("itemsep") in _ALLOWED_ITEMSEP else "1pt"

    parts = [_PREAMBLE.format(margin=margin, itemsep=itemsep)]
    parts.append(_render_header(contact))

    parts.append("\\section{Professional Summary}\n\n" + _latex_escape(content["summary"]))

    comps = [c for c in content["core_competencies"] if c and c.strip()]
    if comps:
        block = ["\\section{Core Competencies}", "\\begin{itemize}"]
        block.extend(f"  \\item {_latex_escape(c)}" for c in comps)
        block.append("\\end{itemize}")
        parts.append("\n".join(block))

    exp_block = ["\\section{Professional Experience}"]
    exp_block.extend(_render_experience(e) for e in content["experiences"])
    parts.append("\n\n".join(exp_block))

    edu = [e for e in content["education"] if e and e.get("degree")]
    if edu:
        lines = ["\\section{Education}", "\\noindent"]
        rendered = []
        for e in edu:
            degree = _latex_escape(e.get("degree", ""))
            inst = _latex_escape(e.get("institution", ""))
            year = _latex_escape(e.get("year", ""))
            rendered.append(rf"\textbf{{{degree}}}, {inst} \hfill {year}")
        lines.append(" \\\\\n".join(rendered))
        parts.append("\n".join(lines))

    certs = [c for c in (content.get("certifications") or []) if c and c.get("name")]
    if certs:
        lines = ["\\section{Certifications}", "\\noindent"]
        rendered = []
        for c in certs:
            name = _latex_escape(c.get("name", ""))
            issuer = _latex_escape(c.get("issuer", ""))
            rendered.append(rf"\textbf{{{name}}}, {issuer}" if issuer else rf"\textbf{{{name}}}")
        lines.append(" \\\\\n".join(rendered))
        parts.append("\n".join(lines))

    parts.append("\\end{document}")
    return "\n\n".join(parts) + "\n"
