"""Shared tech-skill vocabulary and keyword detection.

Single source of truth for the skill list used to (a) score job↔profile match
and (b) steer the resume prompt toward the skills a JD emphasizes. Deterministic,
zero LLM tokens. This module is THE canonical vocabulary — the UI reads detected
skills from server-side match data, not its own copy.
"""
from __future__ import annotations
import re

# Ordered roughly by category. Single-letter "R" is intentionally omitted — it
# matches "R&D", "R&B", and stray letters in prose far more than the language,
# poisoning the match signal. Multi-char names (Go, C#, C++) are boundary-safe.
SKILLS_VOCAB: list[str] = [
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++", "C#",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", ".NET", "Elixir", "Perl",
    # Frontend
    "React", "Vue", "Angular", "Next.js", "Svelte", "HTML", "CSS", "Sass",
    "Tailwind", "GraphQL", "Redux", "NgRx", "NGXS", "RxJS", "Lit", "Vite",
    "Webpack", "Storybook", "Micro-frontends", "Web Components", "Jest",
    "Cypress", "Playwright", "Vitest",
    # Backend
    "Node.js", "Deno", "Django", "Flask", "FastAPI", "Spring", "Spring Boot",
    "Laravel", "Rails", "Express", "NestJS", "ASP.NET", ".NET Core", "gRPC",
    # Data / ML
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Kafka",
    "RabbitMQ", "Spark", "Hadoop", "Snowflake", "Airflow", "dbt", "Databricks",
    "Pandas", "NumPy", "TensorFlow", "PyTorch", "scikit-learn", "Kubernetes",
    # Cloud / Infra / DevOps
    "AWS", "GCP", "Azure", "Docker", "Terraform", "Ansible", "Pulumi",
    "CI/CD", "GitHub Actions", "GitLab CI", "Jenkins", "CircleCI", "ArgoCD",
    "Helm", "Prometheus", "Grafana", "Linux", "Bash", "AWS Serverless",
    "Lambda", "Serverless",
    # Tools / Concepts
    "REST", "API", "Microservices", "Git", "Agile", "Scrum", "Kanban",
    "Jira", "Figma", "OAuth", "WebSockets", "Kubernetes",
]
# (dedupe while preserving order — a couple of terms fit >1 category above)
SKILLS_VOCAB = list(dict.fromkeys(SKILLS_VOCAB))

# Common variants → canonical vocab term. Detection returns the canonical form,
# so "ReactJS" in a JD counts as "React", aligning JD and profile phrasing.
_ALIASES: dict[str, str] = {
    "reactjs": "React", "react.js": "React",
    "vuejs": "Vue", "vue.js": "Vue",
    "nodejs": "Node.js", "node": "Node.js", "node js": "Node.js",
    "nextjs": "Next.js", "next js": "Next.js",
    "nuxt": "Vue", "nuxtjs": "Vue",
    "golang": "Go",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "k8s": "Kubernetes", "kube": "Kubernetes",
    "gcp": "GCP", "google cloud": "GCP", "google cloud platform": "GCP",
    "aws lambda": "Lambda",
    "tailwindcss": "Tailwind", "tailwind css": "Tailwind",
    "restful": "REST", "rest api": "REST", "rest apis": "REST",
    "ci cd": "CI/CD", "cicd": "CI/CD", "continuous integration": "CI/CD",
    "dotnet": ".NET", ".net core": ".NET Core",
    "spring boot": "Spring Boot",
    "typescript": "TypeScript", "ts": "TypeScript",  # 'ts' guarded by boundary
    "js": "JavaScript",
    "es6": "JavaScript", "es2015": "JavaScript",
    "gha": "GitHub Actions",
    "elastic": "Elasticsearch", "elasticsearch": "Elasticsearch",
    "scikit learn": "scikit-learn", "sklearn": "scikit-learn",
    "microfrontends": "Micro-frontends", "micro frontends": "Micro-frontends",
    "web sockets": "WebSockets", "websocket": "WebSockets",
}
# Note: very short aliases (ts, js) still require the non-alnum boundary in the
# regex below, so they won't fire inside longer words.


def _skill_pattern(token: str) -> re.Pattern:
    """Match a token as a whole term. \\b fails around +/#/./space, so use an
    explicit non-alphanumeric boundary on both sides."""
    return re.compile(rf"(^|[^a-z0-9]){re.escape(token.lower())}([^a-z0-9]|$)")


# (search-token, canonical-skill) pairs: every vocab term maps to itself, plus
# each alias maps to its canonical. Longer tokens first so 'spring boot' wins
# over 'spring' when both could match (canonical result is deduped anyway).
_COMPILED: list[tuple[re.Pattern, str]] = [
    (_skill_pattern(tok), canon)
    for tok, canon in sorted(
        {**{s.lower(): s for s in SKILLS_VOCAB}, **_ALIASES}.items(),
        key=lambda kv: -len(kv[0]),
    )
]

# Canonical order for stable output.
_ORDER = {s: i for i, s in enumerate(SKILLS_VOCAB)}


def detect_keywords(text: str) -> list[str]:
    """Return the canonical skills mentioned in `text`, in vocab order.

    Alias-aware ('ReactJS' -> 'React'), deduplicated, order-stable. Used by the
    match signal and the resume-prompt keyword hint.
    """
    if not text:
        return []
    low = text.lower()
    found = {canon for pat, canon in _COMPILED if pat.search(low)}
    return sorted(found, key=lambda s: _ORDER.get(s, 1_000_000))
