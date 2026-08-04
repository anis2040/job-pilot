from __future__ import annotations
"""
Profile management for multi-profile support.
"""

import sys
import re
import hashlib
import shutil
from pathlib import Path
from typing import NamedTuple

_BASE = Path(__file__).parent.parent
PROFILES_DIR = _BASE / "profiles"
ACTIVE_FILE = PROFILES_DIR / ".active"

_PALETTE = [
    "#3b82f6", "#8b5cf6", "#ec4899", "#f97316", "#14b8a6",
    "#84cc16", "#ef4444", "#06b6d4", "#f59e0b", "#6366f1",
]


class ProfileInfo(NamedTuple):
    slug: str
    name: str          # candidate name (from profile.md H1)
    initials: str
    color: str
    label: str         # user-editable display label; defaults to `name`


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"['\"]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "default"


def _meta_path(profile_dir: Path) -> Path:
    return profile_dir / "meta.json"


def _read_label(profile_dir: Path) -> str | None:
    """Read the user-set display label from meta.json, or None if unset."""
    mp = _meta_path(profile_dir)
    if mp.exists():
        try:
            import json
            data = json.loads(mp.read_text(encoding="utf-8"))
            label = (data.get("label") or "").strip()
            return label or None
        except Exception:
            pass
    return None


def set_label(slug: str, label: str) -> bool:
    """Set (or clear, if empty) the display label for a profile. Slug is never
    touched — it remains the permanent internal ID."""
    import json
    profile_dir = PROFILES_DIR / slug
    if not profile_dir.is_dir():
        return False
    mp = _meta_path(profile_dir)
    data = {}
    if mp.exists():
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    label = (label or "").strip()
    if label:
        data["label"] = label
    else:
        data.pop("label", None)
    mp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def name_from_markdown(text: str) -> str | None:
    """Extract the candidate name from the first H1 heading in profile.md text.
    Returns None if no usable heading is found."""
    for line in text.splitlines():
        if line.startswith("#"):
            name = line.lstrip("#").split("—")[0].split("-")[0].strip()
            if name:
                return name
    return None


def _split_sections(text: str) -> dict[str, str]:
    """Split profile.md into a {section-title: body} map by '## ' headings."""
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip().lower()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def parse_profile_md(text: str) -> dict:
    """Parse profile.md into structured JSON, deterministically (no LLM).

    Matches the format the setup wizard writes. Missing sections yield empty
    values. This is a derived cache of profile.md (the source of truth) — used
    for cheaper prompts and structural fabrication checks.
    """
    secs = _split_sections(text)

    def _bullets(body: str) -> list[str]:
        out = []
        for ln in body.splitlines():
            s = ln.strip()
            # Real list markers only: "- x" or "* x" — NOT "**bold**" (starts with **).
            if re.match(r"^[-*]\s+", s) and not s.startswith("**"):
                out.append(re.sub(r"^[-*]\s+", "", s).strip())
        return out

    contact = {"location": "", "phone": "", "email": "", "linkedin": "", "auth": ""}
    for ln in secs.get("contact", "").splitlines():
        m = re.match(r"^-\s*([\w ]+?):\s*(.+)$", ln.strip())
        if not m:
            continue
        key, val = m.group(1).strip().lower(), m.group(2).strip()
        if key == "location": contact["location"] = val
        elif key == "phone": contact["phone"] = val
        elif key == "email": contact["email"] = val
        elif key == "linkedin": contact["linkedin"] = val
        elif key.startswith("work auth"): contact["auth"] = val

    # Experience: '### Title — Employer' blocks with Location/Dates/Bullets.
    experience = []
    exp_body = secs.get("professional experience", "")
    for block in re.split(r"(?=^###\s)", exp_body, flags=re.MULTILINE):
        block = block.strip()
        if not block.startswith("###"):
            continue
        head = block.splitlines()[0].lstrip("#").strip()
        title, employer = (head.split("—", 1) + [""])[:2] if "—" in head else (head, "")
        loc = re.search(r"\*\*Location:\*\*\s*(.+)", block)
        dates = re.search(r"\*\*Dates:\*\*\s*(.+)", block)
        experience.append({
            "title": title.strip(),
            "employer": employer.strip(),
            "location": loc.group(1).strip() if loc else "",
            "dates": dates.group(1).strip() if dates else "",
            "bullets": _bullets(block),
        })

    # Education: '### Degree' blocks with Institution/Location/Year.
    education = []
    for block in re.split(r"(?=^###\s)", secs.get("education", ""), flags=re.MULTILINE):
        block = block.strip()
        if not block.startswith("###"):
            continue
        degree = block.splitlines()[0].lstrip("#").strip()
        inst = re.search(r"\*\*Institution:\*\*\s*(.+)", block)
        year = re.search(r"\*\*Year conferred:\*\*\s*(.+)", block)
        education.append({
            "degree": degree,
            "institution": inst.group(1).strip() if inst else "",
            "year": year.group(1).strip() if year else "",
        })

    return {
        "name": name_from_markdown(text) or "",
        "contact": contact,
        "summary": secs.get("professional summary", ""),
        "competencies": _bullets(secs.get("core competencies", "")),
        "experience": experience,
        "education": education,
        "certifications": _bullets(secs.get("certifications", "")),
    }


def _initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else "??"


def _color(name: str) -> str:
    h = int(hashlib.md5(name.lower().encode()).hexdigest(), 16)
    return _PALETTE[h % len(_PALETTE)]


def _read_name(profile_dir: Path) -> str:
    profile_md = profile_dir / "profile.md"
    if profile_md.exists():
        try:
            name = name_from_markdown(profile_md.read_text(encoding="utf-8"))
            if name:
                return name
        except Exception:
            pass
    return profile_dir.name.replace("-", " ").title()


def _profile_info(profile_dir: Path) -> ProfileInfo:
    name = _read_name(profile_dir)
    label = _read_label(profile_dir) or name
    # Avatar initials/color follow the label so two profiles for the same
    # candidate name but different labels are visually distinguishable.
    return ProfileInfo(
        slug=profile_dir.name,
        name=name,
        initials=_initials(label),
        color=_color(label),
        label=label,
    )


def list_profiles() -> list[ProfileInfo]:
    if not PROFILES_DIR.exists():
        return []
    return [
        _profile_info(e)
        for e in sorted(PROFILES_DIR.iterdir())
        if e.is_dir() and not e.name.startswith(".")
    ]


def has_any_profiles() -> bool:
    return bool(list_profiles())


def get_active_slug() -> str | None:
    if not ACTIVE_FILE.exists():
        return None
    slug = ACTIVE_FILE.read_text(encoding="utf-8").strip()
    if slug and (PROFILES_DIR / slug).is_dir():
        return slug
    return None


def get_active_profile() -> ProfileInfo | None:
    slug = get_active_slug()
    if not slug:
        return None
    return _profile_info(PROFILES_DIR / slug)


def set_active(slug: str) -> bool:
    profile_dir = PROFILES_DIR / slug
    if not profile_dir.is_dir():
        return False
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text(slug, encoding="utf-8")
    _update_symlinks(profile_dir)
    return True


def _update_symlinks(profile_dir: Path) -> None:
    profile_md = profile_dir / "profile.md"
    for skill in ["resume-skill", "cover-letter-skill"]:
        refs = _BASE / skill / "references"
        refs.mkdir(parents=True, exist_ok=True)
        link = refs / "profile.md"
        if link.is_symlink() or link.exists():
            link.unlink()
        if sys.platform == "win32":
            # Symlinks require admin/Developer Mode on Windows — copy instead
            if profile_md.exists():
                shutil.copy2(profile_md, link)
        else:
            link.symlink_to(profile_md)


def create_profile(name: str) -> str:
    slug = slugify(name)
    profile_dir = PROFILES_DIR / slug
    counter = 1
    while profile_dir.exists():
        slug = f"{slugify(name)}-{counter}"
        profile_dir = PROFILES_DIR / slug
        counter += 1
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Write a minimal config.yaml so fetch doesn't fail on a brand-new profile
    config_path = profile_dir / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            "searches: []\nblacklist: []\ncompany_blacklist: []\ntitle_filter: []\n",
            encoding="utf-8",
        )

    return slug


def delete_profile(slug: str) -> bool:
    if slug == get_active_slug():
        return False
    profile_dir = PROFILES_DIR / slug
    if not profile_dir.is_dir():
        return False
    shutil.rmtree(profile_dir)
    return True


def active_profile_dir() -> Path | None:
    slug = get_active_slug()
    return PROFILES_DIR / slug if slug else None


def _active_profile_subpath(filename: str) -> Path | None:
    d = active_profile_dir()
    return d / filename if d else None


def get_profile_path() -> Path | None:  return _active_profile_subpath("profile.md")
def get_profile_json_path() -> Path | None:  return _active_profile_subpath("profile.json")
def get_config_path()  -> Path | None:  return _active_profile_subpath("config.yaml")
def get_db_path()      -> str  | None:  return str(_active_profile_subpath("state.db")) if active_profile_dir() else None


def write_profile_json(profile_dir: Path) -> None:
    """Parse profile.md in profile_dir and write the derived profile.json beside
    it. Best-effort — a parse failure must never block saving the profile."""
    import json as _json
    md = profile_dir / "profile.md"
    if not md.exists():
        return
    try:
        data = parse_profile_md(md.read_text(encoding="utf-8"))
        (profile_dir / "profile.json").write_text(
            _json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_profile_json() -> dict | None:
    """Return the active profile's structured JSON, or None if unavailable.
    Regenerates from profile.md if profile.json is missing/stale-safe fallback."""
    import json as _json
    p = get_profile_json_path()
    if p and p.exists():
        try:
            return _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    md = get_profile_path()
    if md and md.exists():
        try:
            return parse_profile_md(md.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None

def get_resumes_path() -> Path | None:
    d = active_profile_dir()
    return d if d else None

def company_resumes_path(company: str) -> Path | None:
    d = active_profile_dir()
    return d / company / "resumes" if d else None

def company_cover_letters_path(company: str) -> Path | None:
    d = active_profile_dir()
    return d / company / "cover-letters" if d else None
