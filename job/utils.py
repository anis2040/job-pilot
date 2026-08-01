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


# Country name → common signals that appear in job location strings
_COUNTRY_SIGNALS: dict[str, list[str]] = {
    "united states": ["united states", "usa", " us,", ", us", "(us)", "u.s.",
                      "remote us", "remote - us", "us remote", "remote-us",
                      ", al", ", ak", ", az", ", ar", ", ca", ", co", ", ct",
                      ", dc", ", fl", ", ga", ", hi", ", id", ", il", ", in",
                      ", ia", ", ks", ", ky", ", la", ", me", ", md", ", ma",
                      ", mi", ", mn", ", ms", ", mo", ", mt", ", ne", ", nv",
                      ", nh", ", nj", ", nm", ", ny", ", nc", ", nd", ", oh",
                      ", ok", ", or", ", pa", ", ri", ", sc", ", sd", ", tn",
                      ", tx", ", ut", ", vt", ", va", ", wa", ", wv", ", wi", ", wy"],
    "germany": ["germany", "deutschland", "berlin", "munich", "münchen",
                "hamburg", "frankfurt", "cologne", "köln", "düsseldorf", "de,", ", de"],
    "united kingdom": ["united kingdom", "uk", "england", "london", "manchester",
                       "birmingham", "glasgow", "edinburgh", "great britain"],
    "france": ["france", "paris", "lyon", "marseille", "toulouse"],
    "canada": ["canada", "ontario", "toronto", "vancouver", "montreal", "quebec",
               "alberta", "calgary"],
    "australia": ["australia", "sydney", "melbourne", "brisbane", "perth"],
    "netherlands": ["netherlands", "holland", "amsterdam", "rotterdam"],
    "spain": ["spain", "españa", "madrid", "barcelona"],
    "india": ["india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "pune"],
    "singapore": ["singapore"],
    "ireland": ["ireland", "dublin"],
    "poland": ["poland", "warsaw", "krakow"],
    "sweden": ["sweden", "stockholm"],
    "denmark": ["denmark", "copenhagen"],
    "norway": ["norway", "oslo"],
    "switzerland": ["switzerland", "zurich", "geneva"],
    "austria": ["austria", "vienna", "wien"],
    "belgium": ["belgium", "brussels"],
    "brazil": ["brazil", "são paulo", "rio de janeiro"],
    "israel": ["israel", "tel aviv"],
    "japan": ["japan", "tokyo"],
    "china": ["china", "beijing", "shanghai"],
    "hong kong": ["hong kong"],
    "mexico": ["mexico", "ciudad de mexico"],
}


def _normalise(location: str) -> str:
    return location.lower().strip()


def location_matches(job_location: str, search_location: str) -> bool:
    """Return True if job_location is consistent with the search_location config value.

    Handles 'worldwide' / 'remote' as always matching.
    Falls back to substring match for locations not in the known signals map.
    """
    if not search_location:
        return True

    sl = _normalise(search_location)

    # Worldwide / remote-anywhere searches accept everything
    if sl in ("anywhere", "worldwide", "remote", ""):
        return True

    jl = _normalise(job_location)

    # A job with no location info, or explicitly worldwide — don't filter
    if not jl or jl in ("remote", "worldwide", "anywhere", "global"):
        return True

    # "Remote" with a country appended is NOT global — fall through to country matching
    # e.g. "Remote US", "Remote - US", "US Remote" should be treated as US jobs

    # Find which canonical country the search_location maps to
    target_key = None
    for key in _COUNTRY_SIGNALS:
        if sl == key or sl in _COUNTRY_SIGNALS[key]:
            target_key = key
            break
    if target_key is None:
        # Unknown country — fall back to substring match
        return sl in jl or jl in sl

    signals = _COUNTRY_SIGNALS[target_key]

    # Explicit exclusion: if the job location clearly matches a *different* known country, reject
    for other_key, other_signals in _COUNTRY_SIGNALS.items():
        if other_key == target_key:
            continue
        if any(s in jl for s in other_signals):
            return False

    # Check if job location contains any signal for the target country.
    # Do NOT use bare "remote" as a wildcard here — that already passed above.
    return any(s in jl for s in signals)
