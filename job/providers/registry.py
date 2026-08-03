"""Provider registry — the single lookup point for all job providers.

Formalizes the old SOURCE_REGISTRY tuple list into an object with lifecycle:
register, look up by id, resolve a stored job to its provider by id-prefix,
list enabled providers, and query by capability.
"""
from __future__ import annotations

from .base import JobProvider, Capability


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, JobProvider] = {}
        self._disabled: set[str] = set()

    # ── registration ──
    def register(self, provider: JobProvider) -> None:
        pid = provider.meta.id
        if pid in self._providers:
            raise ValueError(f"Provider '{pid}' already registered")
        # Prefixes must be unique so by_prefix() can resolve a job unambiguously.
        for existing in self._providers.values():
            if existing.meta.prefix == provider.meta.prefix:
                raise ValueError(
                    f"Prefix '{provider.meta.prefix}' collides: "
                    f"{existing.meta.id} vs {pid}")
        self._providers[pid] = provider

    # ── lookup ──
    def get(self, provider_id: str) -> JobProvider | None:
        return self._providers.get(provider_id)

    def by_prefix(self, job_id: str) -> JobProvider | None:
        """Resolve a stored job_id (e.g. 'li_123') to its provider."""
        for p in self._providers.values():
            if job_id.startswith(p.meta.prefix):
                return p
        return None

    def all(self) -> list[JobProvider]:
        return list(self._providers.values())

    def enabled(self) -> list[JobProvider]:
        return [p for pid, p in self._providers.items() if pid not in self._disabled]

    def with_capability(self, cap: Capability) -> list[JobProvider]:
        return [p for p in self.enabled() if p.has_capability(cap)]

    # ── enable / disable (runtime kill-switch, no redeploy) ──
    def set_enabled(self, provider_id: str, enabled: bool) -> bool:
        if provider_id not in self._providers:
            return False
        if enabled:
            self._disabled.discard(provider_id)
        else:
            self._disabled.add(provider_id)
        return True

    def is_enabled(self, provider_id: str) -> bool:
        return provider_id in self._providers and provider_id not in self._disabled
