from __future__ import annotations

import base64
import binascii
import json
import zlib
from typing import Any


BUILD_PACKAGE_VERSION = 1


class BuildPackageError(ValueError):
    pass


def build_package(
    build: dict[str, Any],
    settings: dict[str, Any],
    name: str = "",
    description: str = "",
) -> dict[str, Any]:
    return {
        "version": BUILD_PACKAGE_VERSION,
        "name": name.strip(),
        "description": description.strip(),
        "build": build,
        "settings": settings,
    }


def unpack_build_package(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, str, str]:
    if not isinstance(data, dict):
        raise BuildPackageError("Build data must be a JSON object")

    if "build" not in data and "levels" in data:
        return data, None, "", ""

    if data.get("version") != BUILD_PACKAGE_VERSION:
        raise BuildPackageError("Unsupported build package version")
    if not isinstance(data.get("build"), dict):
        raise BuildPackageError("Build package must contain a build object")

    settings = data.get("settings") if isinstance(data.get("settings"), dict) else None
    return data["build"], settings, str(data.get("name") or ""), str(data.get("description") or "")


def build_package_json(package: dict[str, Any]) -> str:
    return json.dumps(package, ensure_ascii=False, indent=2)


def encode_build_code(package: dict[str, Any]) -> str:
    raw = json.dumps(package, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")


def encode_compact_build_code(package: dict[str, Any], tree: Any) -> str:
    return encode_binary_build_code(package, tree)


def decode_build_code(code: str, tree: Any | None = None) -> dict[str, Any]:
    compact = "".join(code.split())
    if not compact:
        raise BuildPackageError("Build code is empty")
    padding = "=" * (-len(compact) % 4)
    try:
        encoded = base64.urlsafe_b64decode((compact + padding).encode("ascii"))
        if encoded.startswith(b"T3"):
            if tree is None:
                raise BuildPackageError("Compact build code requires skill-tree data")
            return decode_binary_build_code(encoded, tree)
        try:
            raw = zlib.decompress(encoded)
        except zlib.error:
            raw = encoded
        data = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BuildPackageError("Invalid build code") from exc
    if not isinstance(data, dict):
        raise BuildPackageError("Invalid build code")
    if data.get("v") == 2:
        if tree is None:
            raise BuildPackageError("Compact build code requires skill-tree data")
        return expand_compact_build_package(data, tree)
    return data


def encode_binary_build_code(package: dict[str, Any], tree: Any) -> str:
    skill_ids = [skill.id for skill in tree.config.skills]
    skill_index = {skill_id: index for index, skill_id in enumerate(skill_ids)}
    levels = package.get("build", {}).get("levels", {})
    indexed_levels = {
        skill_index[skill_id]: level
        for skill_id, level in levels.items()
        if skill_id in skill_index and isinstance(level, int) and 0 < level <= 15
    }
    settings = package.get("settings") if isinstance(package.get("settings"), dict) else {}
    total_points = settings.get("total_points") if isinstance(settings.get("total_points"), int) else tree.config.total_points

    sparse = bytearray(b"T3")
    sparse.append(0)
    sparse.extend(encode_varint(total_points))
    sparse.extend(encode_varint(len(indexed_levels)))
    for index, level in sorted(indexed_levels.items()):
        sparse.extend(encode_varint(index))
        sparse.append(level)

    packed = bytearray(b"T3")
    packed.append(1)
    packed.extend(encode_varint(total_points))
    for index in range(0, len(skill_ids), 2):
        low = indexed_levels.get(index, 0)
        high = indexed_levels.get(index + 1, 0) if index + 1 < len(skill_ids) else 0
        packed.append(low | (high << 4))

    payload = bytes(sparse if len(sparse) <= len(packed) else packed)
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_binary_build_code(payload: bytes, tree: Any) -> dict[str, Any]:
    if len(payload) < 4 or not payload.startswith(b"T3"):
        raise BuildPackageError("Invalid compact build code")
    skill_ids = [skill.id for skill in tree.config.skills]
    mode = payload[2]
    offset = 3
    total_points, offset = decode_varint(payload, offset)
    levels: dict[str, int] = {}

    if mode == 0:
        count, offset = decode_varint(payload, offset)
        for _ in range(count):
            index, offset = decode_varint(payload, offset)
            if offset >= len(payload):
                raise BuildPackageError("Invalid compact build code")
            level = payload[offset]
            offset += 1
            if index < 0 or index >= len(skill_ids):
                raise BuildPackageError("Compact build references an unknown skill")
            if level > 0:
                levels[skill_ids[index]] = level
    elif mode == 1:
        expected = (len(skill_ids) + 1) // 2
        if len(payload) - offset < expected:
            raise BuildPackageError("Invalid compact build code")
        for index, value in enumerate(payload[offset : offset + expected]):
            low_index = index * 2
            high_index = low_index + 1
            low = value & 0x0F
            high = value >> 4
            if low and low_index < len(skill_ids):
                levels[skill_ids[low_index]] = low
            if high and high_index < len(skill_ids):
                levels[skill_ids[high_index]] = high
    else:
        raise BuildPackageError("Unsupported compact build mode")

    return build_package(build={"version": 1, "levels": levels}, settings={"total_points": total_points})


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise BuildPackageError("Compact build values cannot be negative")
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def decode_varint(payload: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(payload):
        byte = payload[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift > 28:
            break
    raise BuildPackageError("Invalid compact build code")


def compact_build_package(package: dict[str, Any], tree: Any) -> dict[str, Any]:
    skill_ids = [skill.id for skill in tree.config.skills]
    skill_index = {skill_id: index for index, skill_id in enumerate(skill_ids)}
    tree_names = sorted({skill.category or "Skills" for skill in tree.config.skills})
    tree_index = {name: index for index, name in enumerate(tree_names)}
    levels = package.get("build", {}).get("levels", {})
    settings = package.get("settings") if isinstance(package.get("settings"), dict) else {}

    compact: dict[str, Any] = {
        "v": 2,
        "l": [
            [skill_index[skill_id], level]
            for skill_id, level in levels.items()
            if skill_id in skill_index and isinstance(level, int) and level > 0
        ],
    }
    if package.get("name"):
        compact["n"] = str(package["name"])
    if package.get("description"):
        compact["d"] = str(package["description"])

    compact_settings: dict[str, Any] = {}
    if isinstance(settings.get("total_points"), int):
        compact_settings["p"] = settings["total_points"]
    if isinstance(settings.get("tree_order"), list):
        compact_settings["o"] = [tree_index[name] for name in settings["tree_order"] if name in tree_index]
    if isinstance(settings.get("collapsed_trees"), dict):
        compact_settings["c"] = [
            [tree_index[name], 1 if collapsed else 0]
            for name, collapsed in settings["collapsed_trees"].items()
            if name in tree_index
        ]
    if isinstance(settings.get("auto_allocate"), bool):
        compact_settings["a"] = 1 if settings["auto_allocate"] else 0
    if isinstance(settings.get("show_skill_tooltips"), bool):
        compact_settings["h"] = 1 if settings["show_skill_tooltips"] else 0
    if isinstance(settings.get("edge_color"), str):
        compact_settings["e"] = settings["edge_color"]
    if compact_settings:
        compact["s"] = compact_settings
    return compact


def expand_compact_build_package(data: dict[str, Any], tree: Any) -> dict[str, Any]:
    skill_ids = [skill.id for skill in tree.config.skills]
    tree_names = sorted({skill.category or "Skills" for skill in tree.config.skills})
    raw_levels = data.get("l")
    if not isinstance(raw_levels, list):
        raise BuildPackageError("Compact build code is missing levels")

    levels: dict[str, int] = {}
    for item in raw_levels:
        if not isinstance(item, list) or len(item) != 2:
            raise BuildPackageError("Invalid compact build level entry")
        index, level = item
        if not isinstance(index, int) or index < 0 or index >= len(skill_ids):
            raise BuildPackageError("Compact build references an unknown skill")
        if not isinstance(level, int):
            raise BuildPackageError("Compact build level must be an integer")
        levels[skill_ids[index]] = level

    settings: dict[str, Any] = {}
    raw_settings = data.get("s") if isinstance(data.get("s"), dict) else {}
    if isinstance(raw_settings.get("p"), int):
        settings["total_points"] = raw_settings["p"]
    if isinstance(raw_settings.get("o"), list):
        settings["tree_order"] = [tree_names[index] for index in raw_settings["o"] if isinstance(index, int) and 0 <= index < len(tree_names)]
    if isinstance(raw_settings.get("c"), list):
        collapsed_trees = {}
        for item in raw_settings["c"]:
            if not isinstance(item, list) or len(item) != 2:
                continue
            index, collapsed = item
            if isinstance(index, int) and 0 <= index < len(tree_names):
                collapsed_trees[tree_names[index]] = bool(collapsed)
        settings["collapsed_trees"] = collapsed_trees
    if "a" in raw_settings:
        settings["auto_allocate"] = bool(raw_settings["a"])
    if "h" in raw_settings:
        settings["show_skill_tooltips"] = bool(raw_settings["h"])
    if isinstance(raw_settings.get("e"), str):
        settings["edge_color"] = raw_settings["e"]

    return build_package(
        build={"version": 1, "levels": levels},
        settings=settings,
        name=str(data.get("n") or ""),
        description=str(data.get("d") or ""),
    )
