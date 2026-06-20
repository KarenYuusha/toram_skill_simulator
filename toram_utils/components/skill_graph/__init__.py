from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components


_FRONTEND_PATH = Path(__file__).parents[3] / "components" / "skill_graph" / "frontend"

_component_func = components.declare_component(
    "skill_graph",
    path=str(_FRONTEND_PATH),
)


def skill_graph(
    skills: list[dict[str, Any]],
    levels: dict[str, int],
    total_points: int,
    remaining_points: int,
    settings: dict[str, Any],
    key: str | None = None,
) -> dict[str, Any] | None:
    return _component_func(
        skills=skills,
        levels=levels,
        total_points=total_points,
        remaining_points=remaining_points,
        settings=settings,
        key=key,
        default=None,
    )
