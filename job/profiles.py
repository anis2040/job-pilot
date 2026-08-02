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
    name: str
    initials: str
    color: str


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"['\"]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "default"


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
            for line in profile_md.read_text().splitlines():
                if line.startswith("#"):
                    name = line.lstrip("#").split("—")[0].split("-")[0].strip()
                    if name:
                        return name
        except Exception:
            pass
    return profile_dir.name.replace("-", " ").title()


def _profile_info(profile_dir: Path) -> ProfileInfo:
    name = _read_name(profile_dir)
    return ProfileInfo(slug=profile_dir.name, name=name, initials=_initials(name), color=_color(name))


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
    slug = ACTIVE_FILE.read_text().strip()
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
    ACTIVE_FILE.write_text(slug)
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
    (profile_dir / "resumes").mkdir(exist_ok=True)
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
def get_config_path()  -> Path | None:  return _active_profile_subpath("config.yaml")
def get_db_path()      -> str  | None:  return str(_active_profile_subpath("state.db")) if active_profile_dir() else None
def get_resumes_path() -> Path | None:  return _active_profile_subpath("resumes")
