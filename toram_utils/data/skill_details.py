from __future__ import annotations

import json
import re
from pathlib import Path

from toram_utils.paths import CORYN_SKILLS_DIR, RAW_SKILLS_DIR, RESTRICTION_DIR, ROOT


def load_coryn_details() -> dict[str, str]:
    details: dict[str, str] = {}
    for folder in CORYN_SKILLS_DIR.glob("*"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            if path.name == "index.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            raw_text = str(data.get("raw_text") or "").strip()
            if raw_text:
                details[str(data.get("slug") or path.stem)] = raw_text
    return details


def load_raw_skill_details() -> dict[str, str]:
    details: dict[str, str] = {}
    heading_keys = raw_skill_heading_keys()
    for path in RAW_SKILLS_DIR.glob("**/*_skills.txt"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        if not any(re.match(r"^(.+?)\s*\|\s*#?", line) for line in lines):
            load_markerless_raw_skill_details(lines, heading_keys, details)
            continue
        block: list[str] = []
        for line in lines:
            marker = re.match(r"^(.+?)\s*\|\s*#?", line)
            if marker:
                name = marker.group(1).strip()
                skill_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
                compact_skill_id = re.sub(r"[^a-z0-9]+", "", name.lower())
                if block:
                    trimmed = trim_raw_skill_block(name, block)
                    text = "\n".join(item for item in trimmed if item.strip()).strip()
                    detail_keys = [(skill_id, compact_skill_id)]
                    heading = raw_block_heading(trimmed)
                    if heading:
                        heading_id = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")
                        heading_compact_id = re.sub(r"[^a-z0-9]+", "", heading.lower())
                        detail_keys.append((heading_id, heading_compact_id))
                    for detail_id, compact_detail_id in detail_keys:
                        if detail_id == "multiple_hunt" and detail_id in details:
                            details[detail_id] = f"{details[detail_id]}\n\n{text}"
                            details[compact_detail_id] = f"{details[compact_detail_id]}\n\n{text}"
                        else:
                            details.setdefault(detail_id, text)
                            details.setdefault(compact_detail_id, text)
                block = []
            else:
                block.append(line)
    return details


def raw_skill_heading_keys() -> dict[str, str]:
    keys: dict[str, str] = {
        "privateanvil": "private_anvil",
        "technicalsynthesis": "technical_synthesis_i",
    }
    for path in RESTRICTION_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for item in data.get("skills") or []:
            name = str(item.get("name") or "")
            skill_id = str(item.get("id") or "")
            if name and skill_id:
                keys[compact_key(name)] = skill_id
    return keys


def load_markerless_raw_skill_details(lines: list[str], heading_keys: dict[str, str], details: dict[str, str]) -> None:
    starts = [index for index, line in enumerate(lines) if compact_key(line) in heading_keys]
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:end]
        text = "\n".join(item for item in block if item.strip()).strip()
        if not text:
            continue
        skill_id = heading_keys[compact_key(lines[start])]
        details.setdefault(skill_id, text)
        details.setdefault(skill_id.replace("_", ""), text)


def compact_key(value: str) -> str:
    value = re.sub(r"^\s*\d+\s*[.)-]\s*", "", value)
    return re.sub(r"[^a-z0-9]+", "", value.lower()).rstrip("s")


def trim_raw_skill_block(name: str, block: list[str]) -> list[str]:
    marker_key = compact_key(name)
    start = 0
    for index, line in enumerate(block):
        line_key = compact_key(line)
        if line_key == marker_key:
            start = index
    return block[start:]


def raw_block_heading(block: list[str]) -> str | None:
    return next((line.strip() for line in block if line.strip()), None)


def detail_lookup(details: dict[str, str], skill_id: str) -> str | None:
    candidates = skill_detail_keys(skill_id)
    return next((details[key] for key in candidates if key in details), None)


def raw_skill_tree_path(tree_name: str) -> Path:
    for path in RESTRICTION_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("skill_tree") != tree_name or not data.get("raw_skill_file"):
            continue
        raw_path = RAW_SKILLS_DIR / str(data["raw_skill_file"])
        if raw_path.exists():
            return raw_path

    slug = re.sub(r"[^a-z0-9]+", "_", tree_name.lower()).strip("_")
    aliases = {
        "alchemy": "alchemist",
        "bare_hand": "barehand",
        "dark_power": "dark_energy",
        "magic_blade": "magic_warrior",
        "smith": "blacksmith",
    }
    slug = aliases.get(slug, slug)
    return next(RAW_SKILLS_DIR.glob(f"**/{slug}_skills.txt"), RAW_SKILLS_DIR / "weapon_class_skills" / f"{slug}_skills.txt")


def skill_detail_keys(skill_id: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", "_", skill_id.lower()).strip("_")
    compact = re.sub(r"[^a-z0-9]+", "", skill_id.lower())
    aliases = {
        "bless": ["bless_advanced_bless", "blessadvancedbless"],
        "cyclon_arrow": ["cyclone_arrow", "cyclonearrow"],
        "enhanced_bless": ["bless_advanced_bless", "blessadvancedbless"],
        "gatling_knife": ["gattling_knife", "gattlingknife"],
        "hidden_arm": ["hidden_arm_intensive_knife", "hiddenarmintensiveknife"],
        "intensive_knife": ["hidden_arm_intensive_knife", "hiddenarmintensiveknife"],
        "kunai_throw": ["kunai"],
        "meikyo_shisui": ["meikyo_shishui", "meikyoshishui"],
        "novices_anvil": ["private_anvil", "privateanvil"],
        "technical_synthesis_i": ["technical_synthesis", "technicalsynthesis"],
        "parabola_cannon": ["parabola_shot", "parabolashot"],
        "resurrection": ["ressurection"],
        "siphon_recall": ["drain_recall", "drainrecall"],
    }
    keys = {normalized, compact, *aliases.get(normalized, [])}
    for key in list(keys):
        if key.endswith("s"):
            keys.add(key[:-1])
        else:
            keys.add(f"{key}s")
    return keys


def relative_to_root(path: Path) -> Path:
    return path.relative_to(ROOT)
