"""Provider package. Exposes the JobProvider interface, capability system,
and the shared registry singleton.

The registry is populated by job.fetcher (which knows the concrete fetchers),
keeping this package free of imports from individual providers.
"""
from .base import JobProvider, FunctionProvider, ProviderMeta, Capability
from .registry import ProviderRegistry

# Single shared registry for the app.
registry = ProviderRegistry()

__all__ = ["JobProvider", "FunctionProvider", "ProviderMeta", "Capability",
           "ProviderRegistry", "registry"]
