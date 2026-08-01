import re


def parse_experience(text: str) -> str:
    """Extract years of experience from a job description string."""
    if not text:
        return ""
    t = text.lower()
    # e.g. "5+ years", "3-5 years", "minimum 3 years", "at least 2 years"
    m = re.search(r"(\d+)\s*[\-–]\s*(\d+)\s*\+?\s*years?", t)
    if m:
        return f"{m.group(1)}-{m.group(2)} years"
    m = re.search(r"(\d+)\s*\+\s*years?", t)
    if m:
        return f"{m.group(1)}+ years"
    m = re.search(r"(?:minimum|at least|min\.?)\s+(\d+)\s*years?", t)
    if m:
        return f"{m.group(1)}+ years"
    m = re.search(r"(\d+)\s*years?\s*(?:of\s+)?(?:experience|exp\.?)", t)
    if m:
        return f"{m.group(1)}+ years"
    if "senior" in t:
        return "5+ years (inferred)"
    if "lead" in t or "principal" in t:
        return "7+ years (inferred)"
    return ""
