from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RawJob:
    job_id: str
    url: str
    title: str
    company: str
    location: str
    remote: str          # "Remote" | "Hybrid" | "On-site" | "Unknown"
    experience: str      # e.g. "3-5 years" or ""
    description: str
    posted_at: str | None = None
