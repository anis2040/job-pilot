"""Provider interface + capability system (Phase 1 of the provider architecture).

See docs/PROVIDER_ARCHITECTURE.md. This introduces the JobProvider abstraction
without rewriting the working fetchers: existing `fetch_<x>` functions are
wrapped by FunctionProvider, while new providers can subclass JobProvider
directly. Everything above a provider talks only to this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ..config import SearchConfig
from ..models import RawJob


class Capability(str, Enum):
    """What a provider can do. Business logic queries these instead of
    hardcoding provider identities."""
    SEARCH_REMOTE_FILTER = "remote_filter"     # honors a remote-only search filter
    FULL_DESCRIPTION     = "full_description"  # get_details / on-demand description
    COMPANY_INFO         = "company_info"      # get_company enrichment
    SALARY_DATA          = "salary_data"       # populates salary_range
    POSTED_DATE          = "posted_date"       # populates posted_at


@dataclass(frozen=True)
class ProviderMeta:
    """Everything the app needs to know about a provider without importing it."""
    id: str                                    # source key used in SearchConfig.source
    prefix: str                                # job_id namespace, e.g. "li_"
    default_pages: int = 3
    capabilities: frozenset[Capability] = field(default_factory=frozenset)


class JobProvider(ABC):
    """Common interface for every job source.

    Subclass this for new providers. Existing free-function fetchers are adapted
    via FunctionProvider so no rewrite is required.
    """
    meta: ProviderMeta

    @abstractmethod
    def search(self, search: SearchConfig) -> list[RawJob]:
        """Fetch and normalize jobs for a search. Returns canonical RawJob list."""
        ...

    def get_details(self, job_url: str) -> str:
        """On-demand full description. Default: unsupported → empty string.
        Providers with Capability.FULL_DESCRIPTION override this."""
        return ""

    def has_capability(self, cap: Capability) -> bool:
        return cap in self.meta.capabilities


class FunctionProvider(JobProvider):
    """Adapts an existing `fetch_<x>(search) -> list[RawJob]` function (and its
    optional `fetch_description`) to the JobProvider interface. This is the
    Phase-1 bridge that lets the current fetchers participate in the registry
    without being rewritten."""

    def __init__(self, meta: ProviderMeta, search_fn: Callable[[SearchConfig], list[RawJob]],
                 describe_fn: Callable[[str], str] | None = None):
        self.meta = meta
        self._search_fn = search_fn
        self._describe_fn = describe_fn

    def search(self, search: SearchConfig) -> list[RawJob]:
        return self._search_fn(search)

    def get_details(self, job_url: str) -> str:
        if not self._describe_fn or not job_url:
            return ""
        try:
            return self._describe_fn(job_url) or ""
        except Exception:
            return ""
