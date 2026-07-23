"""Recipient profile for Zeel's Daily.

Stored as JSON so the production agent can read it without editing code, and
so we can audit the assumptions being made about the reader.
"""
from __future__ import annotations

import json
from pathlib import Path

ZEEL_PROFILE_PATH = Path("/var/www/briefs/ZEEL_PROFILE.json")


DEFAULT_PROFILE = {
    "name": "Zeel Patel",
    "role": "Senior Experience Designer at Autodesk",
    "interests": [
        "experience design",
        "product design",
        "UX",
        "UI",
        "design systems",
        "accessibility",
        "design research",
    ],
    "tone_preference": "design language, simple explanations, less AI jargon",
    "reading_window_local": "19:00 America/Toronto",
}


def load_profile(path: Path | None = None) -> dict:
    p = path or ZEEL_PROFILE_PATH
    if p.exists():
        return json.loads(p.read_text())
    return dict(DEFAULT_PROFILE)


def write_default_profile(path: Path | None = None) -> Path:
    p = path or ZEEL_PROFILE_PATH
    p.write_text(json.dumps(DEFAULT_PROFILE, indent=2))
    p.chmod(0o644)
    return p
