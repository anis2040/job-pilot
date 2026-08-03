"""Tests for the JSON-to-LaTeX resume renderer (job/latex_render.py)."""
import pytest

from job.latex_render import (
    _latex_escape,
    _latex_escape_url,
    _parse_contact_from_profile,
    _parse_content_json,
    render_resume_latex,
    ResumeParseError,
)


# ── _latex_escape ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("R&D", r"R\&D"),
    ("100% done", r"100\% done"),
    ("C#", r"C\#"),
    ("var_name", r"var\_name"),
    ("$1M", r"\$1M"),
    ("{x}", r"\{x\}"),
    ("~home", r"\textasciitilde{}home"),
    ("x^2", r"x\textasciicircum{}2"),
    ("Plain text", "Plain text"),
    ("", ""),
])
def test_latex_escape(raw, expected):
    assert _latex_escape(raw) == expected


def test_latex_escape_backslash_first():
    # Backslash escaped first, then the inserted braces aren't re-escaped.
    assert _latex_escape(r"a\b") == r"a\textbackslash{}b"


def test_latex_escape_combined():
    assert _latex_escape("R&D: 100% of $5M for C#") == r"R\&D: 100\% of \$5M for C\#"


def test_latex_escape_url_keeps_url_chars():
    # URL chars like / ? = _ & stay; only % # \ are neutralized.
    assert _latex_escape_url("https://x.com/in/a_b?ref=1") == "https://x.com/in/a_b?ref=1"
    assert _latex_escape_url("https://x.com/a%20b") == r"https://x.com/a\%20b"


# ── _parse_contact_from_profile ───────────────────────────────────────────────

def test_parse_contact_all_fields():
    profile = """# Anis Helaoui — Full Profile

## Contact
- Location: Cologne, Germany
- Phone: +49 1573 6128121
- Email: anis@icloud.com
- LinkedIn: https://linkedin.com/in/anis
- Work authorization: Green Card holder
"""
    c = _parse_contact_from_profile(profile)
    assert c["name"] == "Anis Helaoui"
    assert c["location"] == "Cologne, Germany"
    assert c["phone"] == "+49 1573 6128121"
    assert c["email"] == "anis@icloud.com"
    assert c["linkedin_url"] == "https://linkedin.com/in/anis"
    assert c["work_auth"] == "Green Card holder"


def test_parse_contact_missing_fields_empty():
    profile = "# Jane Smith — Full Profile\n\n## Contact\n- Email: jane@test.com\n"
    c = _parse_contact_from_profile(profile)
    assert c["name"] == "Jane Smith"
    assert c["email"] == "jane@test.com"
    assert c["phone"] == ""
    assert c["linkedin_url"] == ""
    assert c["work_auth"] == ""


# ── _parse_content_json ───────────────────────────────────────────────────────

_VALID = {
    "company": "Acme",
    "summary": "Senior engineer.",
    "core_competencies": ["Angular", "TypeScript"],
    "experiences": [{"title": "Dev", "employer": "X", "location": "Berlin",
                     "dates": "2020 -- 2024", "bullets": ["Built things"]}],
    "education": [{"degree": "BSc", "institution": "U", "year": "2020"}],
}


def _json_str(d):
    import json
    return json.dumps(d)


def test_parse_json_clean():
    assert _parse_content_json(_json_str(_VALID))["company"] == "Acme"


def test_parse_json_strips_fences():
    text = "```json\n" + _json_str(_VALID) + "\n```"
    assert _parse_content_json(text)["company"] == "Acme"


def test_parse_json_leading_prose():
    text = "Here is your resume content:\n\n" + _json_str(_VALID)
    assert _parse_content_json(text)["summary"] == "Senior engineer."


def test_parse_json_no_object_raises():
    with pytest.raises(ResumeParseError, match="No JSON object"):
        _parse_content_json("just prose, no json here")


def test_parse_json_missing_required_raises():
    bad = {k: v for k, v in _VALID.items() if k != "company"}
    with pytest.raises(ResumeParseError, match="company"):
        _parse_content_json(_json_str(bad))


def test_parse_json_empty_experiences_raises():
    bad = dict(_VALID, experiences=[])
    with pytest.raises(ResumeParseError, match="experiences"):
        _parse_content_json(_json_str(bad))


def test_parse_json_experience_missing_key_raises():
    bad = dict(_VALID, experiences=[{"title": "Dev", "employer": "X", "dates": "2020"}])  # no bullets
    with pytest.raises(ResumeParseError, match="bullets"):
        _parse_content_json(_json_str(bad))


def test_parse_json_tolerates_extra_fields():
    ok = dict(_VALID, gaps=["x"], emphasis="y", unknown=123)
    assert _parse_content_json(_json_str(ok))["company"] == "Acme"


# ── render_resume_latex ───────────────────────────────────────────────────────

_PROFILE = """# Anis Helaoui — Full Profile

## Contact
- Location: Cologne, Germany
- Phone: +49 123
- Email: anis@icloud.com
- LinkedIn: https://linkedin.com/in/anis
"""


def test_render_produces_document():
    latex = render_resume_latex(_VALID, _PROFILE)
    assert latex.startswith(r"\documentclass")
    assert latex.rstrip().endswith(r"\end{document}")
    assert "Anis Helaoui" in latex
    assert "Senior engineer." in latex
    assert "Angular" in latex
    assert "Built things" in latex


def test_render_escapes_content_specials():
    content = dict(
        _VALID,
        summary="100% focused on C# & R&D, saving $1M.",
        core_competencies=["R&D", "C++"],
    )
    latex = render_resume_latex(content, _PROFILE)
    assert r"100\%" in latex
    assert r"C\#" in latex
    assert r"R\&D" in latex
    assert r"\$1M" in latex


def test_render_omits_empty_certifications():
    latex = render_resume_latex(_VALID, _PROFILE)  # no certs key
    assert "\\section{Certifications}" not in latex


def test_render_includes_projects_when_present():
    content = dict(_VALID, experiences=[dict(
        _VALID["experiences"][0],
        projects=[{"name": "Migration", "description": "Nx monorepo."}],
    )])
    latex = render_resume_latex(content, _PROFILE)
    assert "Key Projects" in latex
    assert "Migration" in latex


def test_render_work_auth_line():
    prof = _PROFILE + "- Work authorization: US citizen\n"
    latex = render_resume_latex(_VALID, prof)
    assert "US citizen" in latex


# ── validate_resume_content ───────────────────────────────────────────────────

from job.latex_render import validate_resume_content


def test_validate_flags_fabricated_employer():
    content = dict(_VALID, experiences=[{
        "title": "Dev", "employer": "Totally Made Up Inc", "location": "X",
        "dates": "2020", "bullets": ["did things"],
    }])
    warnings = validate_resume_content(content, "# Me\nWorked at Acme and Globex.")
    assert any("fabrication" in w.lower() for w in warnings)


def test_validate_passes_real_employer():
    content = dict(_VALID, experiences=[{
        "title": "Dev", "employer": "SAP LeanIX", "location": "Bonn",
        "dates": "2020", "bullets": ["did things"],
    }])
    profile = "# Me\n\nSoftware Engineer at SAP LeanIX in Bonn."
    warnings = validate_resume_content(content, profile)
    assert not any("fabrication" in w.lower() for w in warnings)


def test_validate_reports_keyword_coverage():
    content = dict(_VALID, summary="I use Angular daily.",
                   core_competencies=["Angular"],
                   experiences=[{"title": "Dev", "employer": "X", "location": "Y",
                                 "dates": "2020", "bullets": ["Built Angular apps"]}])
    profile = "# Me\nWorked at X."
    warnings = validate_resume_content(content, profile, jd_keywords=["Angular", "Kubernetes", "Go"])
    ats = [w for w in warnings if w.startswith("ATS")]
    assert ats and "1/3" in ats[0]
    assert "Kubernetes" in ats[0] and "Go" in ats[0]
