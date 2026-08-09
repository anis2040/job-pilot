"""Tests for process-wide concurrency limits."""
from job.concurrency import (
    FETCH_LIMIT,
    DOC_BUILD_LIMIT,
    try_acquire_fetch,
    release_fetch,
    try_acquire_doc_build,
    release_doc_build,
    pdflatex_slot,
    reset_for_tests,
)


def setup_function():
    reset_for_tests()


def teardown_function():
    reset_for_tests()


def test_fetch_slots_respect_limit():
    acquired = 0
    for _ in range(FETCH_LIMIT):
        assert try_acquire_fetch() is True
        acquired += 1
    assert try_acquire_fetch() is False
    for _ in range(acquired):
        release_fetch()
    assert try_acquire_fetch() is True
    release_fetch()


def test_doc_build_slots_respect_limit():
    acquired = 0
    for _ in range(DOC_BUILD_LIMIT):
        assert try_acquire_doc_build() is True
        acquired += 1
    assert try_acquire_doc_build() is False
    for _ in range(acquired):
        release_doc_build()
    assert try_acquire_doc_build() is True
    release_doc_build()


def test_pdflatex_slot_serializes():
    with pdflatex_slot():
        pass
