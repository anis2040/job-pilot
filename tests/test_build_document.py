"""Integration test: the resume branch of _build_document, end to end.

Stubs the LLM call to return JSON content, then verifies the pipeline renders
a .tex and (when pdflatex is available) compiles a PDF — proving the
JSON→render→compile path works without any model-authored LaTeX.
"""
import json
import shutil
import sqlite3

import pytest

import job.documents as documents
import job.db as db
import job.task_state as task_state


_CONTENT = {
    "company": "Target Company",
    "summary": "Senior Angular engineer with 100% focus on C# & C++ and $1M outcomes.",
    "core_competencies": ["Angular", "NgRx", "TypeScript", "Lit"],
    "experiences": [{
        "title": "Senior Engineer", "employer": "SAP LeanIX", "location": "Bonn, Germany",
        "dates": "Nov 2024 - Present",
        "bullets": ["Led NgRx refactor for 1M+ users.", "Built URL config engine."],
        "projects": [{"name": "Roadmap Report", "description": "Redesigned state mgmt with NgRx."}],
    }],
    "education": [{"degree": "MEng Software Engineering", "institution": "ESPRIT", "year": "2020"}],
    "certifications": [{"name": "Goethe B1", "issuer": "Goethe-Institut"}],
}

_PROFILE = """# Anis Helaoui — Full Profile

## Contact
- Location: Cologne, Germany
- Phone: +49 123
- Email: anis@icloud.com
- LinkedIn: https://linkedin.com/in/anis
"""


@pytest.fixture
def wired(tmp_path, monkeypatch):
    # Isolated DB
    db_file = tmp_path / "state.db"
    def _connect():
        con = sqlite3.connect(db_file); con.row_factory = sqlite3.Row; return con
    monkeypatch.setattr(db, "_connect", _connect)
    db.init_db()
    db.insert_job(job_id="li_1", url="http://x", title="Angular Engineer", company="Acme",
                  location="Berlin", remote="Remote", experience="", description="x" * 200,
                  posted_at=None, search_name="t")

    # Profile + output paths
    prof = tmp_path / "profile.md"; prof.write_text(_PROFILE)
    monkeypatch.setattr(documents, "get_profile_path", lambda: prof)
    monkeypatch.setattr(documents, "_validate_profile", lambda: None)
    monkeypatch.setattr(documents, "_candidate_name_slug", lambda: "Anis_Helaoui")
    resumes = tmp_path / "resumes"; resumes.mkdir()
    monkeypatch.setattr(documents, "_resumes_path", lambda: resumes)

    # Stub the LLM: return the JSON content the model would produce
    monkeypatch.setattr(documents, "_generate_content",
                        lambda *a, **k: json.dumps(_CONTENT))
    # Stub the summary-verification call so the build stays fully offline.
    monkeypatch.setattr(documents, "call_ai", lambda *a, **k: '{"ok": true}')
    monkeypatch.setattr(documents, "_verify_providers", lambda: [("gemini", "gemini-x")])

    task_state.clear_task_state()
    return resumes


def test_build_resume_renders_and_writes_tex(wired):
    resumes = wired
    documents._build_resume("li_1")

    status = task_state.get_task_status("li_1")
    tex = resumes / "Acme" / "resumes" / "Anis_Helaoui_Resume.tex"
    assert tex.exists(), f"tex not written; status={status}"
    assert not (resumes / "TargetCompany" / "resumes" / "Anis_Helaoui_Resume.tex").exists()
    text = tex.read_text()
    # Content present + specials escaped (the whole point of the refactor)
    assert "Anis Helaoui" in text
    assert r"Acme \& Co" in text or r"\&" in text
    assert r"100\%" in text and r"C\#" in text and r"\$1M" in text
    assert text.startswith(r"\documentclass") and r"\end{document}" in text


def test_build_resume_compiles_pdf_if_pdflatex(wired):
    if not shutil.which("pdflatex"):
        pytest.skip("pdflatex not installed")
    resumes = wired
    documents._build_resume("li_1")
    status = task_state.get_task_status("li_1")
    assert status.get("status") == "done", f"build failed: {status.get('error')}"
    assert status.get("pdf_path") and status["pdf_path"].endswith(".pdf")


# ── _verify_content (combined fabrication guard: summary+bullets+competencies) ─

import job.documents as _docs


@pytest.fixture(autouse=True)
def _stub_verify_provider(monkeypatch):
    # Pretend a strong verifier is available so _verify_content proceeds offline.
    monkeypatch.setattr(_docs, "_verify_providers", lambda: [("gemini", "gemini-x")])


def _content(**over):
    c = {
        "summary": "Data engineer with Spark.",
        "core_competencies": ["Angular", "Apache Iceberg", "Java"],
        "experiences": [
            {"bullets": ["Built Angular apps", "Architected Kafka pipelines"]},
            {"bullets": ["Wrote tests in Jest"]},
        ],
    }
    c.update(over)
    return c


def test_verify_content_prose_fields_corrected(monkeypatch):
    # _verify_content now covers only summary + bullets (competencies are
    # grounded deterministically elsewhere).
    monkeypatch.setattr(_docs, "call_ai", lambda p, system="": (
        '{"summary": "Frontend engineer with Angular.", '
        '"bullets": ["Built Angular apps", "Led NgRx refactor", "Wrote tests in Jest"]}'
    ))
    c = _content()
    changed = _docs._verify_content(c, "# Me\nAngular NgRx Jest dev.")
    assert set(changed) == {"summary", "bullets"}
    assert c["summary"] == "Frontend engineer with Angular."
    # bullet remap by position, only the fabricated one changed
    assert c["experiences"][0]["bullets"] == ["Built Angular apps", "Led NgRx refactor"]
    assert c["experiences"][1]["bullets"] == ["Wrote tests in Jest"]


def test_verify_content_noop_when_grounded(monkeypatch):
    # Verifier echoes everything unchanged -> no field reported changed.
    def echo(p, system=""):
        return ('{"summary": "Data engineer with Spark.", '
                '"bullets": ["Built Angular apps", "Architected Kafka pipelines", "Wrote tests in Jest"]}')
    monkeypatch.setattr(_docs, "call_ai", echo)
    c = _content()
    assert _docs._verify_content(c, "prof") == []


def test_verify_content_ignores_bullet_length_mismatch(monkeypatch):
    # Wrong bullet count must NOT scramble the mapping; other fields still apply.
    monkeypatch.setattr(_docs, "call_ai", lambda p, system="": (
        '{"summary": "Fixed.", "bullets": ["only one"], "competencies": ["Angular"]}'
    ))
    c = _content()
    changed = _docs._verify_content(c, "prof")
    assert "bullets" not in changed
    assert c["experiences"][0]["bullets"] == ["Built Angular apps", "Architected Kafka pipelines"]
    assert "summary" in changed and c["summary"] == "Fixed."


def test_verify_content_tolerates_fences(monkeypatch):
    monkeypatch.setattr(_docs, "call_ai", lambda p, system="":
        'Here:\n```json\n{"summary": "Fixed.", "bullets": [], "competencies": []}\n```')
    c = _content(experiences=[], core_competencies=[])
    assert _docs._verify_content(c, "prof") == ["summary"]


def test_verify_content_empty_is_noop(monkeypatch):
    called = []
    monkeypatch.setattr(_docs, "call_ai", lambda *a, **k: called.append(1) or "{}")
    c = {"summary": "", "core_competencies": [], "experiences": [{"bullets": []}]}
    assert _docs._verify_content(c, "prof") == []
    assert not called  # nothing to check -> no call


def test_verify_content_survives_dead_verifier(monkeypatch):
    def boom(p, system=""): raise RuntimeError("no credits")
    monkeypatch.setattr(_docs, "call_ai", boom)
    c = _content()
    assert _docs._verify_content(c, "prof") == []  # never blocks
    assert c["summary"] == "Data engineer with Spark."  # untouched


def test_verify_content_none_when_no_verifier(monkeypatch):
    monkeypatch.setattr(_docs, "_verify_providers", lambda: [])
    called = []
    monkeypatch.setattr(_docs, "call_ai", lambda *a, **k: called.append(1) or "{}")
    assert _docs._verify_content(_content(), "prof") == []
    assert not called


def test_verify_content_falls_through_on_failure(monkeypatch):
    monkeypatch.setattr(_docs, "_verify_providers",
                        lambda: [("anthropic", "claude"), ("groq", "openai/gpt-oss-120b")])
    calls = []
    def flaky(p, system=""):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("no credits")
        return '{"summary": "Grounded.", "bullets": [], "competencies": []}'
    monkeypatch.setattr(_docs, "call_ai", flaky)
    c = _content(experiences=[], core_competencies=[])
    assert _docs._verify_content(c, "prof") == ["summary"]
    assert len(calls) == 2


def test_verify_content_restores_env(monkeypatch):
    import os
    monkeypatch.setattr(_docs, "call_ai", lambda p, system="":
        '{"summary": "s", "bullets": [], "competencies": []}')
    monkeypatch.setattr(_docs, "_verify_providers", lambda: [("groq", "openai/gpt-oss-120b")])
    monkeypatch.setenv("PREFERRED_PROVIDER", "gemini")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    _docs._verify_content(_content(experiences=[], core_competencies=[]), "prof")
    assert os.environ.get("PREFERRED_PROVIDER") == "gemini"
    assert os.environ.get("GROQ_MODEL") is None


# ── cover-letter JSON build + guard ───────────────────────────────────────────

_CL_CONTENT = {
    "company": "Target Company",
    "paragraphs": [
        "I'm applying for the Staff Engineer role. My NgRx work at SAP LeanIX for 1M+ users fits.",
        "At DocCheck I cut CI/CD time by 50% and built shared component libraries.",
        "I'd love to contribute to your platform and would welcome a conversation.",
    ],
}


def test_cover_letter_prompt_prioritizes_recruiter_call(tmp_path, monkeypatch):
    prof = tmp_path / "profile.md"
    prof.write_text(_PROFILE)
    monkeypatch.setattr(documents, "get_profile_path", lambda: prof)

    skill_text, _ = documents._build_cover_letter_prompt(
        {"description": "Build a practical product with Angular and strong collaboration.", "location": "Berlin"},
        "Acme",
        "Staff Engineer",
        "Anis_Helaoui",
        documents._cl_skill_path(),
    )

    assert "designed to get a recruiter to pick up the phone" in skill_text
    assert "Make the candidate look like a clear, high-fit choice" in skill_text
    assert "Use 2-4 short paragraphs" in skill_text
    assert "do not force the same structure every time" in skill_text
    assert "Do not use em dashes or en dashes" in skill_text
    assert "Source-backed claims" in skill_text
    assert "the 3 body paragraphs" not in skill_text


@pytest.fixture
def cl_wired(tmp_path, monkeypatch):
    db_file = tmp_path / "state.db"
    def _connect():
        con = sqlite3.connect(db_file); con.row_factory = sqlite3.Row; return con
    monkeypatch.setattr(db, "_connect", _connect)
    db.init_db()
    db.insert_job(job_id="li_2", url="http://x", title="Staff Engineer", company="Acme",
                  location="Berlin", remote="Remote", experience="", description="x" * 200,
                  posted_at=None, search_name="t")
    prof = tmp_path / "profile.md"; prof.write_text(_PROFILE)
    monkeypatch.setattr(documents, "get_profile_path", lambda: prof)
    monkeypatch.setattr(documents, "_validate_profile", lambda: None)
    monkeypatch.setattr(documents, "_candidate_name_slug", lambda: "Anis_Helaoui")
    resumes = tmp_path / "resumes"; resumes.mkdir()
    monkeypatch.setattr(documents, "_resumes_path", lambda: resumes)
    monkeypatch.setattr(documents, "_generate_content", lambda *a, **k: json.dumps(_CL_CONTENT))
    monkeypatch.setattr(documents, "call_ai", lambda *a, **k: '{"ok": true}')
    monkeypatch.setattr(documents, "_verify_providers", lambda: [("gemini", "gemini-x")])
    task_state.clear_task_state()
    return resumes


def test_build_cover_letter_renders_json_to_tex(cl_wired):
    resumes = cl_wired
    documents._build_cover_letter("li_2")
    st = task_state.get_cl_task_status("li_2")
    tex = resumes / "Acme" / "cover-letters" / "Anis_Helaoui_Cover_Letter.tex"
    assert tex.exists(), f"CL tex not written; status={st}"
    assert not (resumes / "TargetCompany" / "cover-letters" / "Anis_Helaoui_Cover_Letter.tex").exists()
    text = tex.read_text()
    assert text.startswith(r"\documentclass") and r"\end{document}" in text
    assert r"Hiring Manager\\Acme" in text  # company from the job, not model placeholder
    assert "Anis Helaoui" in text  # name from profile
    assert "NgRx work at SAP LeanIX" in text  # paragraph rendered


def test_verify_cover_letter_rewrites_fabricated(monkeypatch):
    monkeypatch.setattr(_docs, "_verify_providers", lambda: [("gemini", "gemini-x")])
    monkeypatch.setattr(_docs, "call_ai", lambda p, system="":
        '{"ok": false, "paragraphs": ["Grounded p1", "Grounded p2"]}')
    content = {"paragraphs": ["Invented Kafka pipelines", "Real Angular work"]}
    assert _docs._verify_cover_letter(content, "# Me\nAngular dev") is True
    assert content["paragraphs"] == ["Grounded p1", "Grounded p2"]


def test_verify_cover_letter_length_mismatch_ignored(monkeypatch):
    monkeypatch.setattr(_docs, "_verify_providers", lambda: [("gemini", "gemini-x")])
    monkeypatch.setattr(_docs, "call_ai", lambda p, system="": '{"ok": false, "paragraphs": ["only one"]}')
    content = {"paragraphs": ["a", "b"]}
    assert _docs._verify_cover_letter(content, "prof") is False
    assert content["paragraphs"] == ["a", "b"]
