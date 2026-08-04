from __future__ import annotations
from dataclasses import dataclass, field
import yaml


@dataclass
class SearchConfig:
    name: str
    source: str
    query: str
    location: str = "United States"
    remote: bool = True
    max_pages: int = 3
    companies: list = field(default_factory=list)
    work_styles: list[str] = field(default_factory=list)
    group_id: str | None = None


@dataclass
class Config:
    searches: list[SearchConfig]
    blacklist: list[str] = field(default_factory=list)
    company_blacklist: list[str] = field(default_factory=list)
    title_filter: list[str] = field(default_factory=list)


def load_config(path: str | None = None) -> Config:
    if path is None:
        from .profiles import get_config_path
        config_path = get_config_path()
        if not config_path:
            raise ValueError("No active profile")
        path = str(config_path)
    with open(path) as f:
        data = yaml.safe_load(f)

    searches = [SearchConfig(**s) for s in data.get("searches", [])]
    if not searches:
        raise ValueError("config.yaml must have at least one search entry")

    blacklist = [kw.lower() for kw in data.get("blacklist", [])]
    company_blacklist = [c.lower() for c in data.get("company_blacklist", [])]
    title_filter = [kw.lower() for kw in data.get("title_filter", [])]
    return Config(searches=searches, blacklist=blacklist, company_blacklist=company_blacklist, title_filter=title_filter)
