from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT = PACKAGE_ROOT.parent

DATA_PATH = ROOT / "data" / "skills.json"
RESTRICTION_DIR = ROOT / "doc" / "skill_restriction"
CORYN_SKILLS_DIR = ROOT / "doc" / "coryn_skills"
RAW_SKILLS_DIR = ROOT / "doc" / "raw_skills"
ASSET_DIR = ROOT / "assets"
