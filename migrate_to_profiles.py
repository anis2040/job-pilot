#!/usr/bin/env python3
"""
Migrate existing job-scraper data to the multi-profile structure.

Run once after updating the code:
    python migrate_to_profiles.py
"""

import re
import shutil
from pathlib import Path

BASE = Path(__file__).parent
PROFILES_DIR = BASE / "profiles"

OLD_PROFILE = BASE / "resume-skill" / "references" / "profile.md"
OLD_CONFIG = BASE / "config.yaml"
OLD_DB = BASE / "state.db"
OLD_RESUMES = BASE / "resumes"


def _get_name(profile_path: Path) -> str:
    if not profile_path.exists():
        return "default"
    try:
        for line in profile_path.read_text().splitlines():
            if line.startswith("#"):
                name = line.lstrip("#").split("—")[0].split("-")[0].strip()
                if name:
                    return name
    except Exception:
        pass
    return "default"


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"['\"]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "default"


def migrate():
    # Skip if profiles dir already has content
    if PROFILES_DIR.exists() and any(e for e in PROFILES_DIR.iterdir() if e.is_dir() and not e.name.startswith(".")):
        print("profiles/ already has content — skipping migration.")
        return

    has_data = OLD_PROFILE.exists() or OLD_CONFIG.exists() or OLD_DB.exists()
    if not has_data:
        print("No existing data found — fresh install, no migration needed.")
        return

    name = _get_name(OLD_PROFILE)
    slug = _slugify(name)
    profile_dir = PROFILES_DIR / slug
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Migrating data to profile: {name!r} ({slug})")

    if OLD_PROFILE.exists() and not OLD_PROFILE.is_symlink():
        shutil.copy2(OLD_PROFILE, profile_dir / "profile.md")
        print("  Copied profile.md")

    if OLD_CONFIG.exists():
        shutil.move(str(OLD_CONFIG), str(profile_dir / "config.yaml"))
        print("  Moved config.yaml")

    if OLD_DB.exists():
        shutil.move(str(OLD_DB), str(profile_dir / "state.db"))
        print("  Moved state.db")

    if OLD_RESUMES.exists() and OLD_RESUMES.is_dir():
        shutil.move(str(OLD_RESUMES), str(profile_dir / "resumes"))
        print("  Moved resumes/")
    else:
        (profile_dir / "resumes").mkdir(exist_ok=True)

    # Write .active
    (PROFILES_DIR / ".active").write_text(slug)
    print(f"  Set as active profile")

    # Update symlinks
    profile_md = profile_dir / "profile.md"
    for skill in ["resume-skill", "cover-letter-skill"]:
        refs = BASE / skill / "references"
        refs.mkdir(parents=True, exist_ok=True)
        link = refs / "profile.md"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(profile_md)
        print(f"  Updated {skill}/references/profile.md symlink")

    print(f"\nDone! Data is at: {profile_dir}")
    print("Restart the app: python web.py")


if __name__ == "__main__":
    migrate()
