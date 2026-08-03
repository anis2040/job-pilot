"""Tests for _parse_latex_response — extracts LaTeX + metadata from model output."""
from job.web_api import _parse_latex_response
from job.latex import _sanitize_latex


def test_sanitize_escapes_stray_ampersand():
    # Weak models sometimes emit a literal `&` (e.g. "Backend & Cloud"), which
    # aborts pdflatex. The template has no tables, so a bare `&` is always wrong.
    assert _sanitize_latex("Backend & Cloud Services") == r"Backend \& Cloud Services"


def test_sanitize_leaves_escaped_ampersand_untouched():
    # Correct `\&` from a strong model must not be double-escaped.
    assert _sanitize_latex(r"R\&D and Q\&A") == r"R\&D and Q\&A"
    assert _sanitize_latex(r"A & B \& C") == r"A \& B \& C"


def test_sanitize_does_not_touch_percent_or_underscore():
    # `%` (comments) and `_` (URLs/macros) have legitimate uses — leave them.
    src = r"% REPLACE header" + "\n" + r"\href{https://x.com/a_b}{link}"
    assert _sanitize_latex(src) == src


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


# (Cover-letter live-streaming preview and _latex_to_prose were removed when
# cover letters moved to JSON-content + code rendering; tests dropped with them.)

