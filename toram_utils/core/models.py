from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Skill:
    id: str
    name: str
    description: str
    icon: str
    max_level: int
    required_points: int
    prerequisites: tuple[str, ...]
    x: int
    y: int
    category: str | None = None
    point_cost_per_level: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        required = {
            "id",
            "name",
            "description",
            "icon",
            "max_level",
            "required_points",
            "prerequisites",
            "x",
            "y",
        }
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Skill is missing required fields: {', '.join(sorted(missing))}")

        if not isinstance(data["id"], str) or not data["id"].strip():
            raise ValueError("Skill id must be a non-empty string")
        if int(data["max_level"]) < 1:
            raise ValueError(f"Skill {data['id']} has max_level less than 1")
        if int(data["required_points"]) < 0:
            raise ValueError(f"Skill {data['id']} has negative required_points")
        if int(data["x"]) < 0 or int(data["y"]) < 0:
            raise ValueError(f"Skill {data['id']} has negative coordinates")
        if int(data.get("point_cost_per_level", 1)) < 1:
            raise ValueError(f"Skill {data['id']} has point_cost_per_level less than 1")
        if not isinstance(data["prerequisites"], list):
            raise ValueError(f"Skill {data['id']} prerequisites must be a list")

        return cls(
            id=data["id"],
            name=str(data["name"]),
            description=str(data["description"]),
            icon=str(data["icon"]),
            max_level=int(data["max_level"]),
            required_points=int(data["required_points"]),
            prerequisites=tuple(str(item) for item in data["prerequisites"]),
            x=int(data["x"]),
            y=int(data["y"]),
            category=data.get("category") or data.get("branch"),
            point_cost_per_level=int(data.get("point_cost_per_level", 1)),
        )

    def to_component_dict(self, icon_data_uri: str | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "icon_data_uri": icon_data_uri,
            "max_level": self.max_level,
            "required_points": self.required_points,
            "prerequisites": list(self.prerequisites),
            "x": self.x,
            "y": self.y,
            "category": self.category,
            "point_cost_per_level": self.point_cost_per_level,
        }


@dataclass(frozen=True, slots=True)
class SkillTreeConfig:
    skills: tuple[Skill, ...]
    total_points: int = 427
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillTreeConfig":
        if "skills" not in data or not isinstance(data["skills"], list):
            raise ValueError("Configuration must contain a skills list")
        total_points = int(data.get("total_points", 427))
        if total_points < 0:
            raise ValueError("total_points cannot be negative")
        return cls(
            skills=tuple(Skill.from_dict(item) for item in data["skills"]),
            total_points=total_points,
            metadata=dict(data.get("metadata", {})),
        )
