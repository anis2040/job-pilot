"""Process-wide limits for CPU/RAM-heavy work on a single VM."""
from __future__ import annotations

import os
import threading

PDFLATEX_LIMIT = max(1, int(os.environ.get("PDFLATEX_LIMIT", "2")))

_pdflatex_slots = threading.Semaphore(PDFLATEX_LIMIT)


def reset_for_tests() -> None:
    """Restore semaphores between tests (test suite only)."""
    global _pdflatex_slots
    _pdflatex_slots = threading.Semaphore(PDFLATEX_LIMIT)


class pdflatex_slot:
    """Context manager — at most PDFLATEX_LIMIT concurrent pdflatex runs.

    Uses blocking acquire: builds wait in queue rather than failing.
    """

    def __enter__(self):
        _pdflatex_slots.acquire()
        return self

    def __exit__(self, *exc):
        _pdflatex_slots.release()
        return False
