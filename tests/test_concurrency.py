"""Tests for process-wide concurrency limits."""
import threading
import time

from job.concurrency import PDFLATEX_LIMIT, pdflatex_slot, reset_for_tests


def setup_function():
    reset_for_tests()


def teardown_function():
    reset_for_tests()


def test_pdflatex_slot_allows_up_to_limit():
    acquired = []
    gate = threading.Event()

    def hold_slot():
        with pdflatex_slot():
            acquired.append(1)
            gate.wait(timeout=2)

    threads = [threading.Thread(target=hold_slot) for _ in range(PDFLATEX_LIMIT)]
    for t in threads:
        t.start()

    deadline = time.monotonic() + 1.0
    while len(acquired) < PDFLATEX_LIMIT and time.monotonic() < deadline:
        time.sleep(0.01)

    assert len(acquired) == PDFLATEX_LIMIT

    gate.set()
    for t in threads:
        t.join(timeout=2)


def test_pdflatex_slot_queues_beyond_limit():
    """Third acquire blocks until a slot is released — no rejection."""
    gate = threading.Event()
    held = []

    def hold_one():
        with pdflatex_slot():
            held.append(1)
            gate.wait(timeout=2)

    t1 = threading.Thread(target=hold_one)
    t2 = threading.Thread(target=hold_one)
    t1.start()
    t2.start()

    deadline = time.monotonic() + 1.0
    while len(held) < PDFLATEX_LIMIT and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(held) == PDFLATEX_LIMIT

    queued = threading.Event()

    def wait_for_third():
        with pdflatex_slot():
            queued.set()

    t3 = threading.Thread(target=wait_for_third)
    t3.start()
    assert not queued.wait(timeout=0.05)

    gate.set()
    t1.join(timeout=2)
    t2.join(timeout=2)
    t3.join(timeout=2)
    assert queued.is_set()
