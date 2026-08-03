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
    "company": "Acme & Co",
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

    task_state.clear_task_state()
    return resumes


def test_build_resume_renders_and_writes_tex(wired):
    resumes = wired
    documents._build_resume("li_1")

    status = task_state._task_status.get("li_1", {})
    tex = resumes / "AcmeCo" / "resumes" / "Anis_Helaoui_Resume.tex"
    assert tex.exists(), f"tex not written; status={status}"
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
    status = task_state._task_status.get("li_1", {})
    assert status.get("status") == "done", f"build failed: {status.get('error')}"
    assert status.get("pdf_path") and status["pdf_path"].endswith(".pdf")
