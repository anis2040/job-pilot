"""Tests for _parse_latex_response — extracts LaTeX + metadata from model output."""
from job.web_api import _parse_latex_response


def test_extracts_latex_and_json_meta():
    response = r"""Here is your resume:
\documentclass{article}
\begin{document}
Hello World
\end{document}

```json
{"company": "Acme Corp", "role": "Engineer"}
```
"""
    latex, meta = _parse_latex_response(response)
    assert latex.startswith(r"\documentclass")
    assert latex.rstrip().endswith(r"\end{document}")
    assert meta == {"company": "Acme Corp", "role": "Engineer"}


def test_latex_without_meta():
    response = r"\documentclass{article}\begin{document}Hi\end{document}"
    latex, meta = _parse_latex_response(response)
    assert r"\documentclass" in latex
    assert meta == {}


def test_malformed_json_meta_ignored():
    response = r"""\documentclass{article}\begin{document}X\end{document}
```json
{not valid json}
```
"""
    latex, meta = _parse_latex_response(response)
    assert r"\documentclass" in latex
    assert meta == {}


def test_fallback_strips_code_fences():
    response = "```latex\nsome content here\n```"
    latex, meta = _parse_latex_response(response)
    assert "some content here" in latex
    assert "```" not in latex
    assert meta == {}


def test_latex_extracted_before_json_block():
    """The JSON block must be stripped before LaTeX extraction so it isn't
    swept into the returned LaTeX body."""
    response = r"""\documentclass{article}
\begin{document}
Body
\end{document}
```json
{"company": "X"}
```"""
    latex, meta = _parse_latex_response(response)
    assert "json" not in latex.lower()
    assert meta["company"] == "X"


# ── _latex_to_prose (live cover-letter streaming preview) ───────────────────────
from job.documents import _latex_to_prose


def test_prose_strips_preamble_and_commands():
    tex = (r"\documentclass{article}" "\n"
           r"\usepackage{geometry}" "\n"
           r"\begin{document}" "\n"
           r"Dear Hiring Manager,\\" "\n"
           r"I bring \textbf{5 years} of experience." "\n"
           r"% hidden comment" "\n"
           r"\end{document}")
    out = _latex_to_prose(tex)
    assert "documentclass" not in out
    assert "usepackage" not in out
    assert "hidden comment" not in out
    assert "\\textbf" not in out
    assert "5 years" in out                 # bold content preserved
    assert "Dear Hiring Manager" in out


def test_prose_handles_partial_stream():
    # Mid-stream fragment (no \end{document} yet) must not blow up
    partial = r"\begin{document}" "\n" r"Dear Team, I am writing to"
    out = _latex_to_prose(partial)
    assert "Dear Team, I am writing to" in out


def test_prose_empty_safe():
    assert _latex_to_prose("") == ""
