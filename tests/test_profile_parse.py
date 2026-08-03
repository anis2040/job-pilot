"""Tests for deterministic profile.md -> structured JSON parsing (Feature D)."""
from job.profiles import parse_profile_md

_PROFILE = """# Jane Doe — Full Profile

## Contact
- Location: Chicago, IL
- Phone: +1 555-1234
- Email: jane@example.com
- LinkedIn: https://linkedin.com/in/jane
- Work authorization: US citizen

---

## Professional Summary

Senior engineer with 8 years building web apps.

---

## Core Competencies

- Python
- Django
- PostgreSQL

---

## Professional Experience

### Senior Engineer — Acme Corp
**Location:** Chicago, IL
**Dates:** Jan 2020 – Present

**Bullets:**
- Led the billing rewrite.
- Cut latency by 40%.

### Developer — Globex
**Location:** Remote
**Dates:** 2018 – 2020

**Bullets:**
- Built the reporting module.

---

## Education

### Bachelor of Science in Computer Science
- **Institution:** MIT
- **Location:** Cambridge, MA
- **Year conferred:** 2018

---

## Certifications

- AWS Solutions Architect, Amazon (2022)
"""


def test_parse_name_and_contact():
    d = parse_profile_md(_PROFILE)
    assert d["name"] == "Jane Doe"
    assert d["contact"]["location"] == "Chicago, IL"
    assert d["contact"]["email"] == "jane@example.com"
    assert d["contact"]["auth"] == "US citizen"


def test_parse_summary_and_competencies():
    d = parse_profile_md(_PROFILE)
    assert "Senior engineer" in d["summary"]
    assert d["competencies"] == ["Python", "Django", "PostgreSQL"]


def test_parse_experience_blocks():
    d = parse_profile_md(_PROFILE)
    assert len(d["experience"]) == 2
    e0 = d["experience"][0]
    assert e0["title"] == "Senior Engineer"
    assert e0["employer"] == "Acme Corp"
    assert e0["location"] == "Chicago, IL"
    assert e0["dates"] == "Jan 2020 – Present"
    # Bold **Location:**/**Dates:**/**Bullets:** lines must NOT be counted as bullets
    assert e0["bullets"] == ["Led the billing rewrite.", "Cut latency by 40%."]
    assert d["experience"][1]["bullets"] == ["Built the reporting module."]


def test_parse_education_and_certs():
    d = parse_profile_md(_PROFILE)
    assert d["education"][0]["degree"].startswith("Bachelor of Science")
    assert d["education"][0]["institution"] == "MIT"
    assert d["education"][0]["year"] == "2018"
    assert d["certifications"] == ["AWS Solutions Architect, Amazon (2022)"]


def test_parse_empty_profile_safe():
    d = parse_profile_md("# Nobody\n")
    assert d["name"] == "Nobody"
    assert d["competencies"] == [] and d["experience"] == [] and d["education"] == []
