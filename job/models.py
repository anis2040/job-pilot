from __future__ import annotations
from dataclasses import dataclass


class RemoteType:
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ONSITE = "On-site"
    ALL = [REMOTE, HYBRID, ONSITE]


DEFAULT_BLACKLIST = ["internship", "junior", "unpaid", "staffing"]

JOB_STATUSES = ["pending", "applied", "skipped"]


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
    employment_type: str = ""   # e.g. "Full-time", "Contract", "Part-time"
    salary_range: str = ""      # e.g. "$80k–$120k" or "€60,000–€80,000"
