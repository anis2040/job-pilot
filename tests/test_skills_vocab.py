"""Tests for job/skills_vocab.py — deterministic JD keyword detection."""
from job.skills_vocab import detect_keywords, SKILLS_VOCAB


def test_detects_present_skills():
    text = "We need Angular, TypeScript and Kubernetes experience."
    found = detect_keywords(text)
    assert "Angular" in found and "TypeScript" in found and "Kubernetes" in found


def test_handles_special_char_skills():
    found = detect_keywords("Strong C++ and C# and Node.js and CI/CD skills")
    assert "C++" in found and "C#" in found and "Node.js" in found and "CI/CD" in found


def test_no_substring_false_positive():
    # "Go" must not match inside "Django" or "golang"; "R" not inside "React"
    found = detect_keywords("We use Django and React heavily.")
    assert "Go" not in found
    assert "R" not in found
    assert "Django" in found and "React" in found


def test_empty_text():
    assert detect_keywords("") == []
    assert detect_keywords(None) == []


def test_order_stable_and_deduped():
    text = "Angular Angular Python"
    found = detect_keywords(text)
    assert found == [s for s in SKILLS_VOCAB if s in found]  # vocab order
    assert len(found) == len(set(found))  # deduped


# ── synonyms / aliases (canonicalization) ─────────────────────────────────────

def test_aliases_canonicalize():
    assert "React" in detect_keywords("Deep ReactJS experience")
    assert "PostgreSQL" in detect_keywords("We run Postgres in prod")
    assert "Kubernetes" in detect_keywords("Deploy to K8s")
    assert "Go" in detect_keywords("Backend in golang")
    assert "Tailwind" in detect_keywords("Styled with TailwindCSS")


def test_alias_and_canonical_dedupe_to_one():
    found = detect_keywords("We use React and ReactJS interchangeably")
    assert found.count("React") == 1


def test_expanded_terms_detected():
    for term, jd in [("Spring Boot", "Spring Boot services"),
                     ("Snowflake", "data in Snowflake"),
                     ("Terraform", "infra as code with Terraform"),
                     (".NET", "built on .NET")]:
        assert term in detect_keywords(jd), f"{term} not detected"


def test_german_aliases_and_english_tokens_in_german():
    assert "Test Automation" in detect_keywords("Erfahrung mit Testautomatisierung")
    assert "Accessibility" in detect_keywords("Fokus auf Barrierefreiheit")
    assert "API" in detect_keywords("Entwicklung von Schnittstellen")
    # English skill names inside German compounds still match via boundary regex
    found = detect_keywords("React-Entwickler mit Kubernetes-Erfahrung")
    assert "React" in found and "Kubernetes" in found
