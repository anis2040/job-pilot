from .models import RawJob

# Keywords that signal a strong fit for a Product Owner role
_SENIOR_SIGNALS = ["senior", "lead", "principal", "staff", "head of product", "sr."]
_REMOTE_BONUS = ["remote", "work from home", "wfh"]
_PO_SIGNALS = ["product owner", "scrum", "agile", "backlog", "sprint", "safe", "pi planning",
               "user story", "stakeholder", "roadmap", "product vision"]
_NEGATIVE_SIGNALS = ["10+ years", "15+ years", "director", "vp of", "vice president",
                     "c-level", "executive", "clearance required", "security clearance"]


def score_job(job: RawJob) -> int:
    """Return a fit score 0-100. Higher = better match."""
    score = 50  # baseline
    text = (job.title + " " + job.description + " " + job.experience).lower()

    # PO-specific signals
    po_hits = sum(1 for kw in _PO_SIGNALS if kw in text)
    score += min(po_hits * 5, 20)

    # Remote bonus
    if job.remote == "Remote":
        score += 10
    elif job.remote == "Hybrid":
        score += 5

    # Seniority — prefer mid/senior but not exec
    if any(s in text for s in _SENIOR_SIGNALS):
        score += 10

    # Salary signal — higher salary = better opportunity
    if job.salary_min and job.salary_min >= 120000:
        score += 10
    elif job.salary_min and job.salary_min >= 90000:
        score += 5

    # Negatives
    if any(n in text for n in _NEGATIVE_SIGNALS):
        score -= 20

    # Has a description (more info = more reliable score)
    if job.description and len(job.description) > 200:
        score += 5

    return max(0, min(100, score))
