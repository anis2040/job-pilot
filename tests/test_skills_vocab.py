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
