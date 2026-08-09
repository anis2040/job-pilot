from __future__ import annotations
"""
Profile management for multi-profile, multi-user support.

Layout:
  profiles/<user_id>/.active
  profiles/<user_id>/.env
  profiles/<user_id>/<slug>/profile.md, config.yaml, state.db, ...
"""

import sys
import re
import hashlib
import shutil
from pathlib import Path
from typing import NamedTuple

from .user_context import LOCAL_USER_ID, get_current_user_id

_BASE = Path(__file__).parent.parent
PROFILES_DIR = _BASE / "profiles"

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_USER_ID_RE = re.compile(r"^[a-zA-Z0-9_.:|-]+$")

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


def validate_slug(slug: str) -> bool:
    return bool(slug) and bool(_SLUG_RE.match(slug)) and not slug.startswith(".")


def validate_user_id(user_id: str) -> bool:
    if not user_id or user_id.startswith(".") or ".." in user_id or "/" in user_id or "\\" in user_id:
        return False
    return bool(_USER_ID_RE.match(user_id))


def user_profiles_dir(user_id: str | None = None) -> Path:
    uid = user_id or get_current_user_id()
    if not validate_user_id(uid):
        raise ValueError(f"Invalid user id: {uid!r}")
    return PROFILES_DIR / uid


def ensure_user_dir(user_id: str | None = None) -> Path:
    d = user_profiles_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def active_file(user_id: str | None = None) -> Path:
    return user_profiles_dir(user_id) / ".active"


def user_env_path(user_id: str | None = None) -> Path:
    return user_profiles_dir(user_id) / ".env"


def _is_inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def safe_profile_dir(slug: str, user_id: str | None = None) -> Path | None:
    """Return profiles/<user>/<slug> if it exists and stays inside the user root."""
    if not validate_slug(slug):
        return None
    root = user_profiles_dir(user_id)
    candidate = (root / slug).resolve()
    if not _is_inside(root, candidate):
        return None
    if not candidate.is_dir():
        return None
    return candidate


def safe_under_user(rel_path: str | Path, user_id: str | None = None) -> Path | None:
    """Resolve a relative path under the user root; None if it escapes."""
    root = user_profiles_dir(user_id).resolve()
    candidate = (root / Path(rel_path)).resolve()
    if not _is_inside(root, candidate) and candidate != root:
        return None
    return candidate


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


def set_label(slug: str, label: str, user_id: str | None = None) -> bool:
    """Set (or clear, if empty) the display label for a profile. Slug is never
    touched — it remains the permanent internal ID."""
    import json
    profile_dir = safe_profile_dir(slug, user_id)
    if not profile_dir:
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


def list_profiles(user_id: str | None = None) -> list[ProfileInfo]:
    root = user_profiles_dir(user_id)
    if not root.exists():
        return []
    return [
        _profile_info(e)
        for e in sorted(root.iterdir())
        if e.is_dir() and not e.name.startswith(".") and validate_slug(e.name)
    ]


def has_any_profiles(user_id: str | None = None) -> bool:
    return bool(list_profiles(user_id))


def get_active_slug(user_id: str | None = None) -> str | None:
    af = active_file(user_id)
    if not af.exists():
        return None
    slug = af.read_text(encoding="utf-8").strip()
    if slug and safe_profile_dir(slug, user_id):
        return slug
    return None


def get_active_profile(user_id: str | None = None) -> ProfileInfo | None:
    slug = get_active_slug(user_id)
    if not slug:
        return None
    d = safe_profile_dir(slug, user_id)
    return _profile_info(d) if d else None


def set_active(slug: str, user_id: str | None = None) -> bool:
    profile_dir = safe_profile_dir(slug, user_id)
    if not profile_dir:
        # allow activating a just-created dir that exists under user root
        if not validate_slug(slug):
            return False
        root = ensure_user_dir(user_id)
        profile_dir = root / slug
        if not profile_dir.is_dir() or not _is_inside(root, profile_dir.resolve()):
            return False
    ensure_user_dir(user_id)
    active_file(user_id).write_text(slug, encoding="utf-8")
    _update_symlinks(profile_dir)
    return True


def _update_symlinks(profile_dir: Path) -> None:
    """Best-effort skill refs for CLI tools. Not a security boundary."""
    profile_md = profile_dir / "profile.md"
    for skill in ["resume-skill", "cover-letter-skill"]:
        refs = _BASE / skill / "references"
        refs.mkdir(parents=True, exist_ok=True)
        link = refs / "profile.md"
        if link.is_symlink() or link.exists():
            link.unlink()
        if sys.platform == "win32":
            if profile_md.exists():
                shutil.copy2(profile_md, link)
        else:
            if profile_md.exists():
                link.symlink_to(profile_md)


def create_profile(name: str, user_id: str | None = None) -> str:
    root = ensure_user_dir(user_id)
    slug = slugify(name)
    if not validate_slug(slug):
        slug = "default"
    profile_dir = root / slug
    counter = 1
    while profile_dir.exists():
        slug = f"{slugify(name)}-{counter}"
        profile_dir = root / slug
        counter += 1
    profile_dir.mkdir(parents=True, exist_ok=True)

    config_path = profile_dir / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            "searches: []\nblacklist: []\ncompany_blacklist: []\ntitle_filter: []\n",
            encoding="utf-8",
        )

    return slug


def delete_profile(slug: str, user_id: str | None = None) -> bool:
    if slug == get_active_slug(user_id):
        return False
    profile_dir = safe_profile_dir(slug, user_id)
    if not profile_dir:
        return False
    shutil.rmtree(profile_dir)
    return True


def active_profile_dir(user_id: str | None = None) -> Path | None:
    slug = get_active_slug(user_id)
    return safe_profile_dir(slug, user_id) if slug else None


def _active_profile_subpath(filename: str, user_id: str | None = None) -> Path | None:
    d = active_profile_dir(user_id)
    return d / filename if d else None


def get_profile_path(user_id: str | None = None) -> Path | None:
    return _active_profile_subpath("profile.md", user_id)


def get_profile_json_path(user_id: str | None = None) -> Path | None:
    return _active_profile_subpath("profile.json", user_id)


def get_config_path(user_id: str | None = None) -> Path | None:
    return _active_profile_subpath("config.yaml", user_id)


def get_db_path(user_id: str | None = None) -> str | None:
    d = active_profile_dir(user_id)
    return str(d / "state.db") if d else None


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


def get_profile_json(user_id: str | None = None) -> dict | None:
    """Return the active profile's structured JSON, or None if unavailable.

    Self-healing: regenerates profile.json when profile.md is newer (covers the
    case where the user edits profile.md directly in the IDE without going through
    the web UI, which is the only path that calls write_profile_json).
    """
    import json as _json
    p = get_profile_json_path(user_id)
    md = get_profile_path(user_id)
    if p and p.exists() and md and md.exists():
        try:
            if md.stat().st_mtime > p.stat().st_mtime:
                # profile.md was edited after profile.json was last written — regenerate
                write_profile_json(p.parent)
        except Exception:
            pass
    if p and p.exists():
        try:
            return _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    if md and md.exists():
        try:
            return parse_profile_md(md.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def get_resumes_path(user_id: str | None = None) -> Path | None:
    return active_profile_dir(user_id)


def company_resumes_path(company: str, user_id: str | None = None) -> Path | None:
    d = active_profile_dir(user_id)
    return d / company / "resumes" if d else None


def company_cover_letters_path(company: str, user_id: str | None = None) -> Path | None:
    d = active_profile_dir(user_id)
    return d / company / "cover-letters" if d else None


def _is_legacy_profile_dir(path: Path) -> bool:
    """True if path looks like a pre-multi-user profile directory.

    Skips volume system dirs (e.g. Fly/ext ``lost+found``) and ignores
    PermissionError from root-owned entries on mounted disks.
    """
    if not path.is_dir() or path.name.startswith(".") or path.name == LOCAL_USER_ID:
        return False
    # ext* volumes always create this; app user cannot read it
    if path.name == "lost+found":
        return False
    if path.name.startswith("new-profile-"):
        return True
    try:
        return (
            (path / "profile.md").exists()
            or (path / "config.yaml").exists()
            or (path / "state.db").exists()
        )
    except OSError:
        return False


def migrate_legacy_profiles_layout() -> bool:
    """Move flat profiles/<slug>/ layout into profiles/_local/<slug>/.

    Returns True if a migration ran. Idempotent.
    """
    if not PROFILES_DIR.exists():
        return False

    local = PROFILES_DIR / LOCAL_USER_ID
    # Already migrated if _local exists with profile dirs or .active
    if local.is_dir() and (
        (local / ".active").exists()
        or any(e.is_dir() and validate_slug(e.name) for e in local.iterdir())
    ):
        return False

    # Detect legacy: profile-looking dirs or .active directly under PROFILES_DIR
    legacy_active = PROFILES_DIR / ".active"
    legacy_dirs = [e for e in PROFILES_DIR.iterdir() if _is_legacy_profile_dir(e)]
    if not legacy_dirs and not legacy_active.exists():
        return False

    local.mkdir(parents=True, exist_ok=True)
    for d in legacy_dirs:
        dest = local / d.name
        if not dest.exists():
            shutil.move(str(d), str(dest))
    if legacy_active.exists() and not (local / ".active").exists():
        shutil.move(str(legacy_active), str(local / ".active"))
    # Move root AI .env into user dir if present and user .env missing
    root_env = _BASE / ".env"
    user_env = local / ".env"
    if root_env.exists() and not user_env.exists():
        # Copy AI-related keys only into user .env; leave root for server config
        ai_keys = {
            "ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
            "ANTHROPIC_AUTH_TOKEN", "PREFERRED_PROVIDER", "GROQ_MODEL",
            "ANTHROPIC_MODEL", "GEMINI_MODEL", "SEMANTIC_MATCH",
            "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
        }
        lines = []
        for line in root_env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k = line.split("=", 1)[0].strip()
                if k in ai_keys:
                    lines.append(line)
        if lines:
            user_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True
