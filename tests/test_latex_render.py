"""Tests for the JSON-to-LaTeX resume renderer (job/latex_render.py)."""
import pytest

from job.latex_render import (
    _latex_escape,
    _latex_escape_url,
    _parse_contact_from_profile,
    _parse_content_json,
    list_resume_templates,
    render_resume_latex,
    ResumeParseError,
)


def _png_header(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
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


def test_resume_template_registry_exposes_us_and_eu():
    templates = {t.id: t for t in list_resume_templates()}
    assert set(templates) == {"us", "eu"}
    assert templates["us"].supports_profile_image is False
    assert templates["eu"].supports_profile_image is True


def test_us_template_does_not_render_profile_image(tmp_path):
    image = tmp_path / "profile-image.jpg"
    image.write_bytes(b"fake")

    latex = render_resume_latex(_VALID, _PROFILE, template_id="us", profile_image_path=str(image))

    assert "letterpaper" in latex.splitlines()[0]
    assert r"\includegraphics" not in latex


def test_eu_template_renders_profile_image(tmp_path):
    image = tmp_path / "profile-image.jpg"
    image.write_bytes(b"fake")

    latex = render_resume_latex(_VALID, _PROFILE, template_id="eu", profile_image_path=str(image))

    assert "a4paper" in latex.splitlines()[0]
    assert r"\includegraphics" in latex
    assert str(image) in latex


def test_eu_template_center_crops_profile_image_to_passport_frame(tmp_path):
    image = tmp_path / "profile-image.png"
    image.write_bytes(_png_header(1200, 800))

    latex = render_resume_latex(_VALID, _PROFILE, template_id="eu", profile_image_path=str(image))

    assert r"\usepackage{tikz}" in latex
    assert r"\begin{tikzpicture}" in latex
    assert "rectangle (2.55cm,3.25cm)" in latex
    assert "height=3.25cm" in latex
    assert "keepaspectratio" not in latex


def test_eu_template_scales_portrait_photo_by_width(tmp_path):
    image = tmp_path / "profile-image.png"
    image.write_bytes(_png_header(800, 1200))

    latex = render_resume_latex(_VALID, _PROFILE, template_id="eu", profile_image_path=str(image))

    assert r"\includegraphics[width=2.55cm]" in latex
    assert r"\includegraphics[height=3.25cm]" not in latex


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


def test_validate_coverage_is_alias_aware():
    # "owning backlogs" / "RESTful" must count toward the canonical JD keywords
    # "Backlog Management" / "REST" — a raw substring check would miss both.
    content = dict(_VALID, summary="Product Owner owning backlogs and RESTful integrations.",
                   core_competencies=[],
                   experiences=[{"title": "PO", "employer": "X", "location": "Y",
                                 "dates": "2020", "bullets": ["Ran PI planning"]}])
    warnings = validate_resume_content(
        content, "# Me\nWorked at X.",
        jd_keywords=["Backlog Management", "REST", "PI Planning", "Kubernetes"])
    ats = [w for w in warnings if w.startswith("ATS")]
    assert ats and "3/4" in ats[0]           # backlog, REST, PI planning covered
    assert "Kubernetes" in ats[0]            # the only genuine miss
    assert "Backlog Management" not in ats[0]


# ── ground_competencies (deterministic competency fabrication check) ──────────

from job.latex_render import ground_competencies


def test_ground_competencies_drops_unsupported():
    profile = {
        "competencies": ["Angular", "TypeScript", "NgRx"],
        "summary": "Frontend engineer.",
        "experience": [{"bullets": ["Built Angular apps with GraphQL"]}],
    }
    comps = ["Angular", "Apache Iceberg", "Java", "GraphQL"]
    kept, dropped = ground_competencies(comps, profile, backfill_to=0)
    assert "Angular" in kept and "GraphQL" in kept  # in comps list / in a bullet
    assert set(dropped) == {"Apache Iceberg", "Java"}  # nowhere in profile


def test_ground_competencies_backfills_when_short():
    # Model emitted mostly fabrications; after dropping them, top up from profile.
    profile = {"competencies": ["Angular", "TypeScript", "NgRx", "GraphQL", "Jest", "Cypress"],
               "summary": "", "experience": []}
    kept, dropped = ground_competencies(["Angular", "Apache Iceberg"], profile, backfill_to=6)
    assert "Apache Iceberg" in dropped
    assert kept[0] == "Angular"                 # grounded ones kept first
    assert len(kept) == 6                        # backfilled to 6 from profile
    assert "Apache Iceberg" not in kept          # fabrication never re-added


def test_ground_competencies_all_supported():
    profile = {"competencies": ["Python", "Django"], "summary": "", "experience": []}
    kept, dropped = ground_competencies(["Python", "Django"], profile, backfill_to=0)
    assert kept == ["Python", "Django"] and dropped == []


def test_ground_competencies_empty():
    assert ground_competencies([], {"competencies": []}) == ([], [])


# ── clean_content (deterministic post-generation cleanup) ─────────────────────

from job.latex_render import clean_content, _strip_ai_tells, _sort_bullets_metrics_first


@pytest.mark.parametrize("raw,expected", [
    ("Owned backlog — decomposed epics", "Owned backlog, decomposed epics"),
    ("delivered X -- reducing time", "delivered X, reducing time"),
    ("scope – the point", "scope, the point"),
    ("Plain sentence with no dash", "Plain sentence with no dash"),
    ("", ""),
])
def test_strip_ai_tells(raw, expected):
    assert _strip_ai_tells(raw) == expected


def test_strip_ai_tells_preserves_date_ranges():
    # A hyphenated range with no surrounding spaces must survive untouched.
    assert _strip_ai_tells("Oct 2020-Aug 2025 delivery") == "Oct 2020-Aug 2025 delivery"


def test_strip_ai_tells_collapses_double_comma():
    # Dash adjacent to an existing comma shouldn't produce ", ,".
    assert _strip_ai_tells("Built API, — scaling it") == "Built API, scaling it"


def test_sort_bullets_metrics_first():
    bullets = ["Led a team", "Increased velocity by 30%", "Owned backlog", "Reduced time 35%"]
    out = _sort_bullets_metrics_first(bullets)
    assert out == ["Increased velocity by 30%", "Reduced time 35%", "Led a team", "Owned backlog"]


def test_sort_bullets_stable_within_groups():
    # Relative order preserved inside the numbered and plain groups.
    bullets = ["A 1", "B", "C 2", "D"]
    assert _sort_bullets_metrics_first(bullets) == ["A 1", "C 2", "B", "D"]


def test_clean_content_full():
    content = {
        "company": "Acme",
        "summary": "Five years — shipping platforms.",
        "core_competencies": ["Backlog — prioritization", "Roadmaps"],
        "experiences": [{
            "title": "PO", "employer": "X", "location": "Y", "dates": "2020 - 2024",
            "bullets": ["Owned backlog", "Increased velocity by 30%"],
            "projects": [{"name": "P", "description": "Built it — fast."}],
        }],
        "education": [{"degree": "BSc", "institution": "U", "year": "2020"}],
    }
    clean_content(content)
    assert "—" not in content["summary"]
    assert content["core_competencies"][0] == "Backlog, prioritization"
    # metrics-first: the numbered bullet leads
    assert content["experiences"][0]["bullets"][0] == "Increased velocity by 30%"
    assert "—" not in content["experiences"][0]["projects"][0]["description"]
