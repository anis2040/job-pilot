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

def _extract_json_object(text: str) -> dict:
    """Tolerantly extract the first JSON object from a model response.

    Handles ```json fences, leading prose, and trailing text by scanning for the
    first balanced {...}. Raises ResumeParseError on anything unusable. Shared by
    the resume and cover-letter parsers.
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
        return _json.loads(candidate)
    except _json.JSONDecodeError as e:
        raise ResumeParseError(f"Invalid JSON: {e}") from e


def _parse_content_json(text: str) -> dict:
    """Extract and validate the resume content JSON from a model response."""
    data = _extract_json_object(text)
    _validate_resume_content(data)
    return data


def _validate_resume_content(data: dict) -> None:
    if not isinstance(data, dict):
        raise ResumeParseError("Top-level JSON must be an object")
    for field in ("company", "summary", "core_competencies", "experiences", "education"):
        if field not in data or not data[field]:
            raise ResumeParseError(f"Missing or empty required field: {field}")
    if not isinstance(data["core_competencies"], (list, dict)):
        raise ResumeParseError("core_competencies must be a list or category object")
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
\usepackage{{multicol}}

% Slightly open line height for readability (1.0 reads cramped at 11pt).
\linespread{{1.12}}

\definecolor{{headerblue}}{{HTML}}{{4472C4}}

\titleformat{{\section}}
  {{\bfseries\large\color{{headerblue}}}}
  {{}}{{0em}}{{}}
  [\color{{headerblue}}\titlerule]
\titlespacing{{\section}}{{0pt}}{{14pt}}{{6pt}}

\pagestyle{{empty}}

% Roomier list spacing: gap between bullets (itemsep), space above the list
% (topsep), and space between wrapped lines within one bullet (parsep).
\setlist[itemize]{{leftmargin=*, itemsep={itemsep}, parsep=2pt, topsep=5pt}}

\begin{{document}}
"""

_ALLOWED_MARGINS = {"1in", "0.75in", "0.5in"}
_ALLOWED_ITEMSEP = {"6pt", "5pt", "4pt", "3pt", "2pt"}


def _render_header(contact: dict, headline: str = "") -> str:
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
    # Optional headline (professional title) directly under the name — a strong
    # ATS title-match signal and standard resume practice. Rendered only if set.
    headline_line = ""
    if headline and headline.strip():
        headline_line = (
            f"\\\\[3pt]\n  {{\\normalsize\\color{{headerblue}}\\textbf{{{_latex_escape(headline.strip())}}}}}"
        )
    header = (
        "% ── HEADER ──\n"
        "\\begin{center}\n"
        f"  {{\\LARGE\\textbf{{{name}}}}}{headline_line}\\\\[3pt]\n"
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


# ── Deterministic content cleanup ─────────────────────────────────────────────
#
# SKILL.md states two rules the model is asked to self-apply: ban em-dashes (an
# AI tell) and order bullets metrics-first. Strong models comply; weak ones don't.
# Enforcing both in code guarantees the behavior regardless of model — the exact
# kind of deterministic work that shouldn't depend on model intelligence.

# Em-dash (always) and en-dash / '--' runs only when space-surrounded, so date
# ranges like "2020-2024" or "2020–2024" inside prose are left untouched.
_DASH_RE = re.compile(r"\s*—\s*|\s+–\s+|\s+--+\s+")
_NUM_RE = re.compile(r"\d")

# Banned adjectives/phrases that weak models inject despite the SKILL.md rule.
# Each tuple is (compiled pattern, replacement). Patterns match whole words only
# (non-alnum boundary) and are case-insensitive. Replacements are the minimal
# grammatically-correct fix — usually just deletion of the adjective.
_FILLER_SUBS: list[tuple[re.Pattern, str]] = [
    # Standalone adjectives that can be dropped without changing meaning
    (re.compile(r"\benterprise\b[\s-]", re.IGNORECASE), ""),
    (re.compile(r"\brobust\b[\s-]", re.IGNORECASE), ""),
    (re.compile(r"\bseamless(?:ly)?\b[\s-]?", re.IGNORECASE), ""),
    (re.compile(r"\bscalable\b[\s-]", re.IGNORECASE), ""),
    (re.compile(r"\bdynamic\b[\s-]", re.IGNORECASE), ""),
    (re.compile(r"\bhigh[- ]performance\b[\s-]?", re.IGNORECASE), ""),
    (re.compile(r"\bpassionate(?:ly)?\b[\s,]?", re.IGNORECASE), ""),
    (re.compile(r"\bresults?[- ]driven\b[\s,]?", re.IGNORECASE), ""),
    # Multi-word filler phrases — replace with nothing, trim surrounding space
    (re.compile(r"\bproven track record\b[,\s]*(?:of\s+)?", re.IGNORECASE), ""),
    (re.compile(r"\bproven ability\b[,\s]*(?:to\s+)?", re.IGNORECASE), ""),
    (re.compile(r"\bexpert(?:ise)? in\b\s*", re.IGNORECASE), ""),
    (re.compile(r"\bproficient in\b\s*", re.IGNORECASE), ""),
    (re.compile(r"\bleveraging\b\s*", re.IGNORECASE), "using "),
    (re.compile(r"\bend[- ]to[- ]end\b\s*", re.IGNORECASE), ""),
    (re.compile(r"\bhigh[- ]availability\b[\s-]?", re.IGNORECASE), ""),
    # Empty intensifiers/superlatives that add no information (adverbs + adjectives)
    (re.compile(r"\bsignificantly\b\s*", re.IGNORECASE), ""),
    (re.compile(r"\bdrastically\b\s*", re.IGNORECASE), ""),
    (re.compile(r"\bcomprehensive\b\s*", re.IGNORECASE), ""),
    (re.compile(r"\bcomplete\b\s+(?=visual|domain|architecture|documentation)", re.IGNORECASE), ""),
    # "key architectural recommendations" → "architectural recommendations"
    (re.compile(r"\bkey\b\s+(?=architectural|technical|strategic)", re.IGNORECASE), ""),
]


def _strip_ai_tells(text: str) -> str:
    """Strip AI-tell patterns from prose: em/en-dashes and banned filler words/phrases.

    Dashes → comma (weak models emit them despite the rule).
    Filler adjectives (enterprise, robust, seamless, etc.) → deleted.
    Runs deterministically on every prose field so the LLM verifier doesn't need
    to handle these mechanical cases. Collapses any whitespace artifacts left behind.
    """
    if not text:
        return text
    out = _DASH_RE.sub(", ", text)
    for pat, repl in _FILLER_SUBS:
        out = pat.sub(repl, out)
    out = re.sub(r",\s*,", ", ", out)    # ", ," → ", "
    out = re.sub(r"\s{2,}", " ", out)    # collapse runs of spaces
    out = re.sub(r"\s+([,.])", r"\1", out)  # "word ," → "word,"
    return out.strip()


def _sort_bullets_metrics_first(bullets: list) -> list:
    """Stable-partition bullets so those containing a number lead.

    The prompt asks for metrics-first ordering; weak models often ignore it. A
    stable partition enforces it while preserving the model's relative order within
    each group, so it's minimally disruptive.
    """
    numbered = [b for b in bullets if _NUM_RE.search(b or "")]
    plain = [b for b in bullets if not _NUM_RE.search(b or "")]
    return numbered + plain


# Skills whose absence in the profile should prevent "backend"/"full-stack"
# scope-inflation. These are server-side language tokens; if none appear in the
# profile's competencies the candidate is frontend-only and the model must not
# imply backend ownership in prose.
_BACKEND_LANGUAGES = {
    "java", "spring", "spring boot", "kotlin", "go", "golang", "rust",
    "python", "django", "fastapi", "flask", "ruby", "rails", "php",
    "laravel", "c#", ".net", "asp.net", "scala", "elixir", "node.js",
    "nodejs", "express", "nestjs", "backend", "server-side",
}

# Patterns that imply backend *development* (not frontend consumption of an API).
# If any pattern matches a prose field AND the profile has no backend language,
# replace with a precision-reduced alternative.
_SCOPE_INFLATION_REPLACEMENTS = [
    # "backend service integrations" → "API integrations"
    (re.compile(r"\bbackend service integrations?\b", re.IGNORECASE), "API integrations"),
    # "AWS Serverless backend services" → "AWS Serverless services"
    (re.compile(r"\bAWS Serverless backend services?\b", re.IGNORECASE), "AWS Serverless services"),
    # "full-stack features" → "features" (the adjective is the overstatement)
    (re.compile(r"\bfull[- ]stack features?\b", re.IGNORECASE), "features"),
    # "full-stack development" / "full-stack engineer" → soften if no backend lang
    (re.compile(r"\bfull[- ]stack (development|engineer|developer|work|experience)\b", re.IGNORECASE),
     lambda m: m.group(1)),  # keep just the noun ("development", "engineer", etc.)
    # "ship maintainable full-stack X" → "ship maintainable X"
    (re.compile(r"\bmaintainable full[- ]stack\b", re.IGNORECASE), "maintainable"),
    # Frontend consumption of a serverless/GraphQL endpoint doesn't establish
    # ownership of "system scalability" (a backend/infra outcome). Drop that claim
    # tail while keeping the real, frontend-scoped part of the sentence.
    (re.compile(r"\s+and system scalability\b", re.IGNORECASE), ""),
]


def _guard_scope_inflation(text: str, profile_has_backend: bool) -> str:
    """Strip scope-inflation phrases from prose when the profile lacks a backend language.

    Only fires when the profile has no server-side language in its competencies —
    i.e. the candidate is frontend-only. Leaves text unchanged for genuine full-stack
    profiles. This catches what the LLM verifier misses: "API consumption from a
    frontend" being silently reframed as "backend service integrations".
    """
    if not text or profile_has_backend:
        return text
    for pat, replacement in _SCOPE_INFLATION_REPLACEMENTS:
        if callable(replacement):
            text = pat.sub(replacement, text)
        else:
            text = pat.sub(replacement, text)
    # Collapse any whitespace artifacts from multi-word removals.
    text = re.sub(r"  +", " ", text).strip()
    return text


def _profile_has_backend(profile: dict | None) -> bool:
    """Return True if the profile's competencies contain at least one backend language."""
    if not profile:
        return False
    comps = " ".join(profile.get("competencies", []) or []).lower()
    return any(lang in comps for lang in _BACKEND_LANGUAGES)


# Verb forms that assert formal architect/lead authority. If the profile has no
# architect/lead/principal/staff/head/manager title, these overstate an IC role
# and a background check exposes the gap. Downgrade to build/deliver verbs.
# Verb forms only — the noun "architecture" / competency "Frontend Architecture"
# is untouched (it's a domain, not a claimed title).
# Verb forms that assert formal architect/lead authority. If the profile has no
# architect/lead/principal/staff/head/manager title, these overstate an IC role
# and a background check exposes the gap. Downgrade to build/deliver verbs.
# Verb forms only — the noun "architecture" / competency "Frontend Architecture"
# is untouched (it's a domain, not a claimed title). Replacements are callables
# so the original capitalization is preserved (these verbs often open a bullet).
def _match_case(repl: str):
    def _sub(m: re.Match) -> str:
        word = m.group(0)
        if word[:1].isupper():
            return repl[:1].upper() + repl[1:]
        return repl
    return _sub


_TITLE_INFLATION_REPLACEMENTS = [
    (re.compile(r"\barchitecting\b", re.IGNORECASE), _match_case("building")),
    (re.compile(r"\barchitected\b", re.IGNORECASE), _match_case("built")),
    (re.compile(r"\bspearheaded\b", re.IGNORECASE), _match_case("drove")),
    # "Led development of X" / "Led end-to-end development of X" → "Developed X"
    (re.compile(r"\bled (?:end[- ]to[- ]end )?development of\b", re.IGNORECASE),
     _match_case("developed")),
]

# Title tokens that license architect/lead-level ownership verbs.
_LEAD_TITLE_TOKENS = (
    "architect", "lead", "principal", "staff", "head of", "manager",
    "director", "vp", "chief",
)


_HR_SUFFIX_RE = re.compile(
    r"\s*[-–—(]\s*(?:"
    r"all\s+genders?|"
    r"[mwfdx/]{1,5}\s*[/|]\s*[mwfdx/]{1,5}(?:\s*[/|]\s*[mwfdx/]{1,5})*|"  # w/m/d, m/f/d, f/m/x
    r"[mwf]\s*/\s*[mwf](?:\s*/\s*[mwf])?|"                                   # m/f, m/w
    r"diverse\b|divers\b|any\s+gender"
    r")\s*[)–—]?\s*$",
    re.IGNORECASE,
)


def _strip_hr_suffixes(title: str) -> str:
    """Remove gender/diversity suffixes job postings append to role titles.
    '(w/m/d)', '- All Genders', '– m/f/d', etc. are HR artefacts, not the title."""
    if not title:
        return title
    return _HR_SUFFIX_RE.sub("", title).strip(" -–—")


def _profile_has_lead_title(profile: dict | None) -> bool:
    """True if any experience title in the profile carries architect/lead-level authority."""
    if not profile:
        return False
    titles = " ".join(
        (e.get("title") or "") for e in (profile.get("experience") or [])
    ).lower()
    return any(tok in titles for tok in _LEAD_TITLE_TOKENS)


def _guard_title_inflation(text: str, profile_has_lead_title: bool) -> str:
    """Downgrade architect/lead-authority verbs to build/deliver verbs when the
    profile has no architect/lead title. Frontend-only ICs get "architecting" →
    "building", "spearheaded" → "drove", etc. Leaves genuine leads untouched.
    Catches what the LLM verifier misses: verb-level seniority inflation that
    reads impressive but contradicts the HR-of-record title."""
    if not text or profile_has_lead_title:
        return text
    for pat, replacement in _TITLE_INFLATION_REPLACEMENTS:
        text = pat.sub(replacement, text)
    return re.sub(r"  +", " ", text).strip()



def clean_content(content: dict, profile: dict | None = None) -> dict:
    """Apply deterministic post-generation cleanup to resume content, in place.

    Enforces SKILL.md rules weak models violate: strip em-dashes from prose,
    order each role's bullets metrics-first, and remove scope-inflation phrases
    (e.g. "full-stack features", "backend service integrations") when the profile
    has no backend language. Returns the same dict. Runs after the fabrication
    guard so it also catches anything the verifier introduced.
    """
    has_backend = _profile_has_backend(profile)
    has_lead_title = _profile_has_lead_title(profile)

    def _guard(text: str) -> str:
        return _guard_title_inflation(
            _guard_scope_inflation(_strip_ai_tells(text), has_backend),
            has_lead_title,
        )

    if content.get("summary"):
        content["summary"] = _guard(content["summary"])
    if content.get("headline"):
        content["headline"] = _strip_hr_suffixes(content["headline"])
    if content.get("core_competencies"):
        cc = content["core_competencies"]
        if isinstance(cc, dict):
            content["core_competencies"] = {
                cat: [_strip_ai_tells(c) for c in items if c and c.strip()]
                for cat, items in cc.items()
                if items
            }
        else:
            content["core_competencies"] = [
                _strip_ai_tells(c) for c in cc if c and c.strip()
            ]
    for exp in content.get("experiences", []):
        bullets = [
            _guard(b)
            for b in exp.get("bullets", []) if b and b.strip()
        ]
        exp["bullets"] = _sort_bullets_metrics_first(bullets)
        for p in exp.get("projects", []) or []:
            if p.get("description"):
                p["description"] = _guard(p["description"])
    return content


def _competencies_flat(cc) -> list[str]:
    """Normalize either a flat list or a category-dict to a flat list of strings."""
    if isinstance(cc, dict):
        return [item for items in cc.values() for item in items if item and item.strip()]
    return [c for c in (cc or []) if c and c.strip()]


def _render_competencies(cc) -> str:
    """Render core_competencies as categorized rows (dict) or a 2-column list (flat list)."""
    if isinstance(cc, dict):
        # Category label: Skill1 · Skill2 · Skill3
        lines = ["\\section{Core Competencies}", "\\begin{description}[leftmargin=0pt, labelindent=0pt, itemsep=3pt, topsep=2pt]"]
        for cat, items in cc.items():
            if not items:
                continue
            skills = " $\\cdot$ ".join(_latex_escape(s) for s in items)
            lines.append(f"  \\item[\\textbf{{{_latex_escape(cat)}:}}] {skills}")
        lines.append("\\end{description}")
        return "\n".join(lines)
    # Flat list fallback: 2-column grid
    comps = [c for c in (cc or []) if c and c.strip()]
    if not comps:
        return ""
    if len(comps) >= 5:
        block = [
            "\\section{Core Competencies}",
            "\\begin{multicols}{2}",
            "\\begin{itemize}[itemsep=2pt, topsep=2pt, parsep=0pt]",
        ]
        block.extend(f"  \\item {_latex_escape(c)}" for c in comps)
        block.append("\\end{itemize}")
        block.append("\\end{multicols}")
    else:
        block = ["\\section{Core Competencies}", "\\begin{itemize}"]
        block.extend(f"  \\item {_latex_escape(c)}" for c in comps)
        block.append("\\end{itemize}")
    return "\n".join(block)


def ground_competencies(competencies: list, profile: dict, backfill_to: int = 6) -> tuple[list, list]:
    """Deterministically drop competencies not supported by the structured
    profile, then backfill from the profile's real competency list so the
    section stays strong. A competency is grounded if it appears in the
    profile's competencies, its experience bullets, or its summary
    (case/space-insensitive substring). Returns (kept, dropped).

    Backfill matters because a weak model may emit mostly-fabricated JD
    keywords; after dropping them we top up (preserving order, no dupes) from
    the profile's own competencies up to `backfill_to`, so grounding never
    leaves a near-empty section. Free — profile.json is ground truth.
    """
    if not competencies and not profile.get("competencies"):
        return [], []
    haystack = _norm(" ".join([
        " ".join(profile.get("competencies", []) or []),
        profile.get("summary", "") or "",
        " ".join(b for e in profile.get("experience", []) or [] for b in (e.get("bullets") or [])),
    ]))
    kept, dropped = [], []
    for c in competencies:
        if c and c.strip() and _norm(c) and _norm(c) in haystack:
            kept.append(c)
        elif c and c.strip():
            dropped.append(c)
    # Backfill from the profile's real competencies if we're short.
    if len(kept) < backfill_to:
        seen = {_norm(c) for c in kept}
        for c in profile.get("competencies", []) or []:
            if len(kept) >= backfill_to:
                break
            if c and _norm(c) not in seen:
                kept.append(c)
                seen.add(_norm(c))
    return kept, dropped


def validate_resume_content(content: dict, profile_text: str, jd_keywords: list[str] | None = None) -> list[str]:
    """Deterministic post-generation check. Returns human-readable warnings
    (empty = clean). Non-fatal: the resume is already rendered — this surfaces
    likely fabrication for logging/UI.

    High-signal, vocabulary-free check (chosen to avoid false positives):
    every experience employer must appear in profile.md (catches invented jobs).
    When callers pass JD keywords, coverage is checked through the shared skill
    vocabulary so aliases count the same way they do in job matching.
    """
    warnings: list[str] = []
    prof = _norm(profile_text)

    for exp in content.get("experiences", []):
        employer = (exp.get("employer") or "").strip()
        if employer and _norm(employer) not in prof:
            warnings.append(f"Employer not found in profile (possible fabrication): {employer!r}")

    if jd_keywords:
        from .skills_vocab import detect_keywords

        pieces = [content.get("summary") or "", " ".join(_competencies_flat(content.get("core_competencies")))]
        for exp in content.get("experiences", []) or []:
            pieces.extend(exp.get("bullets") or [])
            for project in exp.get("projects", []) or []:
                pieces.append(project.get("description") or "")
        covered = {keyword.lower() for keyword in detect_keywords("\n".join(pieces))}

        missing: list[str] = []
        for keyword in jd_keywords:
            canonical = detect_keywords(keyword) or [keyword]
            if not any(item.lower() in covered for item in canonical):
                missing.append(keyword)
        if missing:
            matched_count = len(jd_keywords) - len(missing)
            warnings.append(
                f"ATS keyword coverage: {matched_count}/{len(jd_keywords)} covered; missing: {', '.join(missing)}"
            )

    return warnings


def render_resume_latex(content: dict, profile_text: str) -> str:
    """Assemble a complete, compilable .tex document from validated content."""
    contact = _parse_contact_from_profile(profile_text)

    margin = content.get("margin") if content.get("margin") in _ALLOWED_MARGINS else "0.75in"
    itemsep = content.get("itemsep") if content.get("itemsep") in _ALLOWED_ITEMSEP else "4pt"

    parts = [_PREAMBLE.format(margin=margin, itemsep=itemsep)]
    parts.append(_render_header(contact, headline=content.get("headline", "")))

    parts.append("\\section{Professional Summary}\n\n" + _latex_escape(content["summary"]))

    cc = content.get("core_competencies")
    if cc:
        rendered_cc = _render_competencies(cc)
        if rendered_cc:
            parts.append(rendered_cc)

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


# ── Cover letter ──────────────────────────────────────────────────────────────

def _parse_cover_letter_json(text: str) -> dict:
    """Parse + validate cover-letter content JSON (paragraphs + company).

    Reuses the tolerant _extract_json_object, then validates the cover-letter
    shape. Raises ResumeParseError on anything unusable.
    """
    data = _extract_json_object(text)
    if not isinstance(data, dict):
        raise ResumeParseError("Top-level JSON must be an object")
    paras = data.get("paragraphs")
    if not isinstance(paras, list) or not [p for p in paras if isinstance(p, str) and p.strip()]:
        raise ResumeParseError("Missing or empty 'paragraphs'")
    return data


_CL_PREAMBLE = r"""\documentclass[11pt,a4paper]{letter}
\usepackage[margin=1in]{geometry}
\usepackage[hidelinks]{hyperref}
\usepackage{microtype}
\pagestyle{empty}

\begin{document}
"""


def render_cover_letter_latex(content: dict, profile_text: str) -> str:
    """Render a complete cover-letter .tex from structured content.

    Contact/name come from profile.md (never the model). Body paragraphs are
    escaped. The fixed `letter` shell lives here, not in the model output —
    eliminating cover-letter compile failures.
    """
    contact = _parse_contact_from_profile(profile_text)
    name = _latex_escape(contact.get("name") or "Candidate")
    company = _latex_escape(content.get("company") or "the company")
    greeting = _latex_escape(content.get("greeting") or "Dear Hiring Manager,")
    closing = _latex_escape(content.get("closing") or "Best regards,")
    paras = [p.strip() for p in content.get("paragraphs", []) if isinstance(p, str) and p.strip()]

    parts = [_CL_PREAMBLE]
    parts.append(f"\\begin{{letter}}{{Hiring Manager\\\\{company}}}")
    parts.append(f"\\opening{{{greeting}}}")
    parts.append("\n\n".join(_latex_escape(p) for p in paras))
    parts.append(f"\\closing{{{closing}}}")
    # Signature block: name + contact from profile
    contact_bits = []
    if contact.get("email"):
        contact_bits.append(_latex_escape(contact["email"]))
    if contact.get("phone"):
        contact_bits.append(_latex_escape(contact["phone"]))
    sig = f"\\vspace{{1em}}\n\\noindent {name}"
    if contact_bits:
        sig += "\\\\\n" + " $\\cdot$ ".join(contact_bits)
    parts.append(sig)
    parts.append("\\end{letter}")
    parts.append("\\end{document}")
    return "\n\n".join(parts) + "\n"
