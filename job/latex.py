from __future__ import annotations
import sys
import re
import subprocess
import json as _json
from pathlib import Path

from .ai_providers import strip_llm_fences
from .concurrency import pdflatex_slot


def _compile_latex(tex_path: Path) -> Path:
    """Run pdflatex on a .tex file. Returns path to the generated PDF."""
    tex_dir = tex_path.parent
    tex_name = tex_path.name

    # Find pdflatex
    import shutil
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        # Try common macOS BasicTeX path
        common = Path("/usr/local/texlive/2026basic/bin/universal-darwin/pdflatex")
        if common.exists():
            pdflatex = str(common)
    if not pdflatex:
        raise RuntimeError(
            "pdflatex not found. Install BasicTeX (macOS: brew install --cask basictex) "
            "or MiKTeX (Windows: miktex.org/download) or texlive-latex-extra (Linux)."
        )

    env = None
    if sys.platform == "darwin":
        import os
        env = os.environ.copy()
        env["PATH"] = "/usr/local/texlive/2026basic/bin/universal-darwin:" + env.get("PATH", "")

    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = subprocess.CREATE_NO_WINDOW

    cmd = [pdflatex, "-interaction=nonstopmode", tex_name]
    if sys.platform == "win32":
        cmd.insert(1, "--enable-installer")  # MiKTeX: auto-install missing packages silently

    with pdflatex_slot():
        result = subprocess.run(
            cmd,
            cwd=str(tex_dir),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            **extra,
        )

    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"pdflatex failed.{_latex_error_detail(tex_path, result)}")

    # Clean up build artifacts
    for pattern in ["*.aux", "*.log", "*.out", "*.toc", "*.fls", "*.fdb_latexmk", "*.synctex.gz"]:
        for f in tex_dir.glob(pattern):
            try:
                f.unlink()
            except Exception:
                pass

    return pdf_path


def _latex_error_detail(tex_path: Path, result) -> str:
    """Build an actionable error message from the pdflatex .log file.

    pdflatex writes the real diagnostic (`! LaTeX Error: ...` / `! Undefined
    control sequence` etc.) into the .log, then keeps going in nonstopmode — so
    the tail of stdout is usually just the closing prompt, not the cause. Pull
    the actual error lines (plus a few following lines, which show the offending
    source) instead.
    """
    log_path = tex_path.with_suffix(".log")
    try:
        log = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        tail = (result.stdout or result.stderr or "")[-800:]
        return f" Log tail:\n{tail}" if tail else " No log available."

    lines = log.splitlines()
    blocks: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("!"):
            blocks.append("\n".join(lines[i:i + 4]).rstrip())
    if blocks:
        return f" Errors:\n" + "\n\n".join(blocks[:5])
    return f" Log tail:\n{log[-800:]}"


def _sanitize_latex(text: str) -> str:
    """Strip invisible Unicode and repair the one unescapable-character mistake
    weak models make, without altering correct LaTeX from strong models."""
    # Zero-width and other invisible characters that sneak in from scraped content
    _STRIP = (
        "​",  # zero-width space
        "‌",  # zero-width non-joiner
        "‍",  # zero-width joiner
        "‎",  # left-to-right mark
        "‏",  # right-to-left mark
        "﻿",  # BOM / zero-width no-break space
        "­",  # soft hyphen
    )
    for ch in _STRIP:
        text = text.replace(ch, "")

    # Escape stray ampersands. The resume template forbids tables/columns and
    # uses \hfill for alignment, so a bare `&` is never valid syntax here — it's
    # a literal ampersand a weak model failed to escape (e.g. "Backend & Cloud"),
    # which aborts pdflatex with "Misplaced alignment tab character &". Only
    # touch `&` that isn't already escaped, so correct `\&` from a strong model
    # is left untouched. `%`, `#`, `_` are deliberately NOT escaped: they have
    # legitimate uses (comments, macro params, URLs) that fixing would corrupt.
    text = re.sub(r"(?<!\\)&", r"\\&", text)
    return text


def _parse_latex_response(response_text: str) -> tuple[str, dict]:
    """Extract LaTeX content and metadata JSON from model response."""
    # Find the JSON block after \end{document}
    meta = {}
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            meta = _json.loads(json_match.group(1))
        except Exception:
            pass
        response_text = response_text[:json_match.start()]

    # Extract LaTeX — everything from \documentclass to \end{document}
    latex_match = re.search(r'(\\documentclass.*?\\end\{document\})', response_text, re.DOTALL)
    if latex_match:
        return _sanitize_latex(latex_match.group(1)), meta

    # Fallback: strip markdown code fences
    return _sanitize_latex(strip_llm_fences(response_text.strip())), meta
