from __future__ import annotations
import sys
import re
import subprocess
import json as _json
from pathlib import Path


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

    result = subprocess.run(
        [pdflatex, "-interaction=nonstopmode", tex_name],
        cwd=str(tex_dir),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        **extra,
    )

    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        err_snippet = result.stdout[-1000:] if result.stdout else result.stderr[-500:]
        raise RuntimeError(f"pdflatex failed. Log tail:\n{err_snippet}")

    # Clean up build artifacts
    for pattern in ["*.aux", "*.log", "*.out", "*.toc", "*.fls", "*.fdb_latexmk", "*.synctex.gz"]:
        for f in tex_dir.glob(pattern):
            try:
                f.unlink()
            except Exception:
                pass

    return pdf_path


def _sanitize_latex(text: str) -> str:
    """Strip invisible/problematic Unicode that pdflatex can't handle."""
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
    text = response_text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        text = text.rsplit("```", 1)[0].strip()
    return _sanitize_latex(text), meta
