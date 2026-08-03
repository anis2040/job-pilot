"""Tests for the Phase-1 provider layer: JobProvider interface, FunctionProvider
adapter, and ProviderRegistry. Fully offline."""
import pytest

from job.config import SearchConfig
from job.models import RawJob
from job.providers import (
    JobProvider, FunctionProvider, ProviderMeta, Capability, ProviderRegistry,
)
from job.providers import registry as app_registry


def _job(jid="x_1"):
    return RawJob(job_id=jid, url="http://x", title="T", company="C",
                  location="L", remote="Remote", experience="", description="")


# ── FunctionProvider ────────────────────────────────────────────────────────────

def test_function_provider_search_delegates():
    meta = ProviderMeta(id="demo", prefix="dm_")
    p = FunctionProvider(meta, lambda s: [_job("dm_1")])
    out = p.search(SearchConfig(name="t", source="demo", query="q", location="l"))
    assert len(out) == 1 and out[0].job_id == "dm_1"

def test_function_provider_describe_default_empty():
    p = FunctionProvider(ProviderMeta(id="demo", prefix="dm_"), lambda s: [])
    assert p.get_details("http://x") == ""          # no describe_fn → ""

def test_function_provider_describe_delegates():
    p = FunctionProvider(ProviderMeta(id="demo", prefix="dm_"),
                         lambda s: [], describe_fn=lambda url: f"DESC:{url}")
    assert p.get_details("http://x") == "DESC:http://x"

def test_function_provider_describe_swallows_errors():
    def boom(url): raise RuntimeError("fail")
    p = FunctionProvider(ProviderMeta(id="demo", prefix="dm_"), lambda s: [], describe_fn=boom)
    assert p.get_details("http://x") == ""

def test_capability_query():
    meta = ProviderMeta(id="demo", prefix="dm_",
                        capabilities=frozenset({Capability.SALARY_DATA}))
    p = FunctionProvider(meta, lambda s: [])
    assert p.has_capability(Capability.SALARY_DATA)
    assert not p.has_capability(Capability.FULL_DESCRIPTION)


# ── ProviderRegistry ──────────────────────────────────────────────────────────

def test_registry_register_and_get():
    r = ProviderRegistry()
    p = FunctionProvider(ProviderMeta(id="a", prefix="a_"), lambda s: [])
    r.register(p)
    assert r.get("a") is p
    assert r.get("missing") is None

def test_registry_rejects_duplicate_id():
    r = ProviderRegistry()
    r.register(FunctionProvider(ProviderMeta(id="a", prefix="a_"), lambda s: []))
    with pytest.raises(ValueError):
        r.register(FunctionProvider(ProviderMeta(id="a", prefix="b_"), lambda s: []))

def test_registry_rejects_prefix_collision():
    r = ProviderRegistry()
    r.register(FunctionProvider(ProviderMeta(id="a", prefix="x_"), lambda s: []))
    with pytest.raises(ValueError):
        r.register(FunctionProvider(ProviderMeta(id="b", prefix="x_"), lambda s: []))

def test_registry_by_prefix():
    r = ProviderRegistry()
    r.register(FunctionProvider(ProviderMeta(id="li", prefix="li_"), lambda s: []))
    r.register(FunctionProvider(ProviderMeta(id="gh", prefix="gh_"), lambda s: []))
    assert r.by_prefix("li_123").meta.id == "li"
    assert r.by_prefix("gh_x").meta.id == "gh"
    assert r.by_prefix("zz_1") is None

def test_registry_enable_disable():
    r = ProviderRegistry()
    r.register(FunctionProvider(ProviderMeta(id="a", prefix="a_"), lambda s: []))
    assert r.is_enabled("a")
    r.set_enabled("a", False)
    assert not r.is_enabled("a")
    assert "a" not in [p.meta.id for p in r.enabled()]
    r.set_enabled("a", True)
    assert r.is_enabled("a")

def test_registry_with_capability():
    r = ProviderRegistry()
    r.register(FunctionProvider(ProviderMeta(id="a", prefix="a_",
               capabilities=frozenset({Capability.SALARY_DATA})), lambda s: []))
    r.register(FunctionProvider(ProviderMeta(id="b", prefix="b_"), lambda s: []))
    assert [p.meta.id for p in r.with_capability(Capability.SALARY_DATA)] == ["a"]


# ── App registry populated from SOURCE_REGISTRY ─────────────────────────────────

def test_app_registry_has_all_sources():
    import job.fetcher as ft
    ids = {p.meta.id for p in app_registry.all()}
    assert ids == {s.id for s in ft.SOURCE_REGISTRY}

def test_app_registry_prefixes_resolve():
    assert app_registry.by_prefix("li_1").meta.id == "linkedin"
    assert app_registry.by_prefix("ss_1").meta.id == "stepstone"

def test_app_registry_full_description_matches_describe_sources():
    caps = {p.meta.id for p in app_registry.with_capability(Capability.FULL_DESCRIPTION)}
    assert caps == {"linkedin", "stepstone"}
