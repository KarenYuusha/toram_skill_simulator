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


def decode_build_code(code: str) -> dict[str, Any]:
    compact = "".join(code.split())
    if not compact:
        raise BuildPackageError("Build code is empty")
    padding = "=" * (-len(compact) % 4)
    try:
        encoded = base64.urlsafe_b64decode((compact + padding).encode("ascii"))
        try:
            raw = zlib.decompress(encoded)
        except zlib.error:
            raw = encoded
        data = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BuildPackageError("Invalid build code") from exc
    if not isinstance(data, dict):
        raise BuildPackageError("Invalid build code")
    return data
