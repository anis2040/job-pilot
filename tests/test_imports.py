"""Smoke test: every module imports without error.

This is the single most valuable test in the suite — a missing module-level
import (like the `os` bug that broke Build CV) surfaces here instantly, with
zero setup and no keys required.
"""
import importlib
import pytest

MODULES = [
    "job.web_api",
    "job.db",
    "job.config",
    "job.utils",
    "job.models",
    "job.profiles",
    "job.fetcher",
    "job.greenhouse_fetcher",
    "job.himalayas_fetcher",
    "job.jobicy_fetcher",
    "job.linkedin_fetcher",
    "job.cli",
    "web",
]


@pytest.mark.parametrize("modname", MODULES)
def test_module_imports(modname):
    """Importing the module must not raise (catches missing imports, syntax errors)."""
    importlib.import_module(modname)


def test_web_api_uses_os_at_module_level():
    """Regression: web_api references os.environ in _generate_content / _get_model.
    `os` must be importable from the module namespace, not only inside functions."""
    import job.web_api as w
    assert hasattr(w, "os"), "job.web_api must import os at module level"
