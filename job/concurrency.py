"""Process-wide limits for CPU/RAM-heavy work on a single VM."""
from __future__ import annotations

import threading

FETCH_LIMIT = 2
DOC_BUILD_LIMIT = 2
PDFLATEX_LIMIT = 1

_fetch_slots = threading.Semaphore(FETCH_LIMIT)
_doc_build_slots = threading.Semaphore(DOC_BUILD_LIMIT)
_pdflatex_slots = threading.Semaphore(PDFLATEX_LIMIT)

_fetch_active = 0
_doc_build_active = 0
_counters_lock = threading.Lock()


def try_acquire_fetch() -> bool:
    global _fetch_active
    acquired = _fetch_slots.acquire(blocking=False)
    if acquired:
        with _counters_lock:
            _fetch_active += 1
    return acquired


def release_fetch() -> None:
    global _fetch_active
    with _counters_lock:
        _fetch_active = max(0, _fetch_active - 1)
    _fetch_slots.release()


def fetch_active_count() -> int:
    with _counters_lock:
        return _fetch_active


def reset_for_tests() -> None:
    """Restore semaphores/counters between tests (test suite only)."""
    global _fetch_slots, _doc_build_slots, _pdflatex_slots
    global _fetch_active, _doc_build_active
    _fetch_slots = threading.Semaphore(FETCH_LIMIT)
    _doc_build_slots = threading.Semaphore(DOC_BUILD_LIMIT)
    _pdflatex_slots = threading.Semaphore(PDFLATEX_LIMIT)
    with _counters_lock:
        _fetch_active = 0
        _doc_build_active = 0


def try_acquire_doc_build() -> bool:
    global _doc_build_active
    acquired = _doc_build_slots.acquire(blocking=False)
    if acquired:
        with _counters_lock:
            _doc_build_active += 1
    return acquired


def release_doc_build() -> None:
    global _doc_build_active
    with _counters_lock:
        _doc_build_active = max(0, _doc_build_active - 1)
    _doc_build_slots.release()


def doc_build_active_count() -> int:
    with _counters_lock:
        return _doc_build_active


class pdflatex_slot:
    """Context manager — at most PDFLATEX_LIMIT concurrent pdflatex runs."""

    def __enter__(self):
        _pdflatex_slots.acquire()
        return self

    def __exit__(self, *exc):
        _pdflatex_slots.release()
        return False
