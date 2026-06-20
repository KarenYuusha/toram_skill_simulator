from __future__ import annotations

from pathlib import Path

from toram_utils.core import SkillTree, skill_tree_from_restriction_files
from toram_utils.paths import DATA_PATH, RESTRICTION_DIR, ROOT


def restriction_paths() -> list[Path]:
    return sorted(RESTRICTION_DIR.glob("*.json"))


def restriction_version() -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (str(path.relative_to(ROOT)), path.stat().st_mtime_ns, path.stat().st_size)
        for path in restriction_paths()
    )


def load_skill_tree(total_points: int = 427) -> SkillTree:
    paths = restriction_paths()
    if paths:
        return skill_tree_from_restriction_files(paths, total_points=total_points)
    return SkillTree.from_json_file(DATA_PATH)
