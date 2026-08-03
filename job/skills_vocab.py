"""Shared tech-skill vocabulary and keyword detection.

Single source of truth for the skill list used to (a) tag jobs in the UI and
(b) detect which requirements a job description emphasizes, so the resume
prompt can be steered toward covering them (ATS keyword matching).

Kept in code — deterministic, zero LLM tokens.
"""
from __future__ import annotations
import re

# Ordered roughly by category. Keep in sync with the JS SKILLS_LIST in
# templates/job_detail.html (that copy drives the on-page skill chips).
SKILLS_VOCAB: list[str] = [
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++", "C#",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R",
    # Frontend
    "React", "Vue", "Angular", "Next.js", "Svelte", "HTML", "CSS", "Tailwind",
    "GraphQL", "Redux", "NgRx", "NGXS", "Lit", "Micro-frontends",
    # Backend
    "Node.js", "Django", "Flask", "FastAPI", "Spring", "Laravel", "Rails", "Express",
    # Data / ML
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Kafka",
    "Spark", "Pandas", "NumPy", "TensorFlow", "PyTorch", "scikit-learn", "dbt",
    # Cloud / Infra
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD",
    "GitHub Actions", "Linux", "Bash",
    # Tools / Concepts
    "REST", "API", "Microservices", "Git", "Agile", "Scrum", "Jira", "Figma",
]


def _skill_pattern(skill: str) -> re.Pattern:
    """Match a skill as a whole token. \\b fails around +/#/. so use an explicit
    non-alphanumeric boundary (mirrors the JS extractSkills logic)."""
    return re.compile(rf"(^|[^a-z0-9]){re.escape(skill.lower())}([^a-z0-9]|$)")


_COMPILED = [(s, _skill_pattern(s)) for s in SKILLS_VOCAB]


def detect_keywords(text: str) -> list[str]:
    """Return the skills from SKILLS_VOCAB that appear in `text`, in vocab order.

    Deterministic, order-stable, deduplicated. Used to build a compact
    'requirements detected' hint for the resume prompt.
    """
    if not text:
        return []
    low = text.lower()
    return [s for s, pat in _COMPILED if pat.search(low)]
