from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from toram_utils.core.models import Skill, SkillTreeConfig


class SkillTreeError(ValueError):
    pass


class SkillTree:
    def __init__(self, config: SkillTreeConfig):
        self.config = config
        self.skills: dict[str, Skill] = {skill.id: skill for skill in config.skills}
        self.children: dict[str, list[str]] = defaultdict(list)
        self._validate_config()
        for skill in config.skills:
            for parent_id in skill.prerequisites:
                self.children[parent_id].append(skill.id)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SkillTree":
        with Path(path).open("r", encoding="utf-8") as file:
            return cls(SkillTreeConfig.from_dict(json.load(file)))

    def _validate_config(self) -> None:
        ids = [skill.id for skill in self.config.skills]
        duplicates = sorted({skill_id for skill_id in ids if ids.count(skill_id) > 1})
        if duplicates:
            raise SkillTreeError(f"Duplicate skill IDs: {', '.join(duplicates)}")
        for skill in self.config.skills:
            for parent_id in skill.prerequisites:
                if parent_id not in self.skills:
                    raise SkillTreeError(f"Skill {skill.id} references missing prerequisite {parent_id}")
                if skill.required_points > self.skills[parent_id].max_level:
                    raise SkillTreeError(
                        f"Skill {skill.id} requires {skill.required_points} points in {parent_id}, "
                        f"but {parent_id} maxes at {self.skills[parent_id].max_level}"
                    )
        self._topological_order()

    def _topological_order(self) -> list[str]:
        indegree = {skill_id: 0 for skill_id in self.skills}
        adjacency: dict[str, list[str]] = defaultdict(list)
        for skill in self.config.skills:
            for parent_id in skill.prerequisites:
                adjacency[parent_id].append(skill.id)
                indegree[skill.id] += 1

        queue = deque(skill_id for skill_id, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while queue:
            skill_id = queue.popleft()
            order.append(skill_id)
            for child_id in adjacency[skill_id]:
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    queue.append(child_id)
        if len(order) != len(self.skills):
            raise SkillTreeError("Skill graph must be a directed acyclic graph; cycle detected")
        return order

    def empty_levels(self) -> dict[str, int]:
        return {skill_id: 0 for skill_id in self.skills}

    def normalize_levels(self, levels: dict[str, int] | None) -> dict[str, int]:
        normalized = self.empty_levels()
        if levels:
            normalized.update({skill_id: int(level) for skill_id, level in levels.items()})
        return normalized

    def get_skill(self, skill_id: str) -> Skill:
        try:
            return self.skills[skill_id]
        except KeyError as exc:
            raise SkillTreeError(f"Unknown skill ID: {skill_id}") from exc

    def get_parents(self, skill_id: str) -> list[str]:
        return list(self.get_skill(skill_id).prerequisites)

    def get_children(self, skill_id: str) -> list[str]:
        self.get_skill(skill_id)
        return list(self.children.get(skill_id, []))

    def get_ancestors(self, skill_id: str) -> set[str]:
        self.get_skill(skill_id)
        ancestors: set[str] = set()
        stack = list(self.get_parents(skill_id))
        while stack:
            parent_id = stack.pop()
            if parent_id in ancestors:
                continue
            ancestors.add(parent_id)
            stack.extend(self.get_parents(parent_id))
        return ancestors

    def get_descendants(self, skill_id: str) -> set[str]:
        self.get_skill(skill_id)
        descendants: set[str] = set()
        stack = list(self.get_children(skill_id))
        while stack:
            child_id = stack.pop()
            if child_id in descendants:
                continue
            descendants.add(child_id)
            stack.extend(self.get_children(child_id))
        return descendants

    def spent_points(self, levels: dict[str, int]) -> int:
        levels = self.normalize_levels(levels)
        return sum(levels[skill_id] * skill.point_cost_per_level for skill_id, skill in self.skills.items())

    def remaining_points(self, levels: dict[str, int], total_points: int) -> int:
        return total_points - self.spent_points(levels)

    def is_unlocked(self, skill_id: str, levels: dict[str, int]) -> bool:
        levels = self.normalize_levels(levels)
        skill = self.get_skill(skill_id)
        return all(levels[parent_id] >= skill.required_points for parent_id in skill.prerequisites)

    def calculate_missing_prerequisites(self, skill_id: str, levels: dict[str, int]) -> dict[str, int]:
        levels = self.normalize_levels(levels)
        skill = self.get_skill(skill_id)
        return {
            parent_id: skill.required_points - levels[parent_id]
            for parent_id in skill.prerequisites
            if levels[parent_id] < skill.required_points
        }

    def can_increment(self, skill_id: str, levels: dict[str, int]) -> tuple[bool, str]:
        levels = self.normalize_levels(levels)
        skill = self.get_skill(skill_id)
        if not self.is_unlocked(skill_id, levels):
            missing = self.calculate_missing_prerequisites(skill_id, levels)
            details = ", ".join(f"{parent}: need {amount} more" for parent, amount in missing.items())
            return False, f"Locked: {details}"
        if levels[skill_id] >= skill.max_level:
            return False, f"{skill.name} is already at max level"
        return True, ""

    def increment_skill(self, skill_id: str, levels: dict[str, int], total_points: int) -> tuple[dict[str, int], str]:
        levels = self.normalize_levels(levels)
        ok, message = self.can_increment(skill_id, levels)
        if not ok:
            return levels, message
        levels[skill_id] += 1
        return levels, f"Added 1 point to {self.get_skill(skill_id).name}"

    def can_decrement(self, skill_id: str, levels: dict[str, int]) -> tuple[bool, str]:
        levels = self.normalize_levels(levels)
        if levels[self.get_skill(skill_id).id] <= 0:
            return False, f"{self.get_skill(skill_id).name} is already at zero"
        return True, ""

    def _invalid_allocated_skills(self, levels: dict[str, int]) -> list[str]:
        return [skill_id for skill_id, level in levels.items() if level > 0 and not self.is_unlocked(skill_id, levels)]

    def decrement_skill_strict(self, skill_id: str, levels: dict[str, int]) -> tuple[dict[str, int], str]:
        levels = self.normalize_levels(levels)
        ok, message = self.can_decrement(skill_id, levels)
        if not ok:
            return levels, message
        candidate = dict(levels)
        candidate[skill_id] -= 1
        invalid = self._invalid_allocated_skills(candidate)
        if invalid:
            names = ", ".join(self.get_skill(item).name for item in invalid)
            return levels, f"Cannot refund {self.get_skill(skill_id).name}; allocated descendant depends on it: {names}"
        return candidate, f"Removed 1 point from {self.get_skill(skill_id).name}"

    def decrement_skill_cascade(self, skill_id: str, levels: dict[str, int]) -> tuple[dict[str, int], str]:
        levels = self.normalize_levels(levels)
        ok, message = self.can_decrement(skill_id, levels)
        if not ok:
            return levels, message
        levels[skill_id] -= 1
        refunded = 0
        while True:
            invalid = self._invalid_allocated_skills(levels)
            if not invalid:
                break
            for invalid_id in invalid:
                refunded += levels[invalid_id] * self.get_skill(invalid_id).point_cost_per_level
                levels[invalid_id] = 0
        base_refund = self.get_skill(skill_id).point_cost_per_level
        total_refund = refunded + base_refund
        return levels, f"Refunded {total_refund} point(s); invalid downstream skills were reset"

    def auto_allocate_and_increment(
        self, skill_id: str, levels: dict[str, int], total_points: int
    ) -> tuple[dict[str, int], str]:
        levels = self.normalize_levels(levels)
        skill = self.get_skill(skill_id)
        if levels[skill_id] >= skill.max_level:
            return levels, f"{skill.name} is already at max level"

        candidate = dict(levels)
        relevant = self.get_ancestors(skill_id) | {skill_id}
        for node_id in self._topological_order():
            if node_id not in relevant:
                continue
            node = self.get_skill(node_id)
            for parent_id in node.prerequisites:
                missing = node.required_points - candidate[parent_id]
                if missing <= 0:
                    continue
                parent = self.get_skill(parent_id)
                if candidate[parent_id] + missing > parent.max_level:
                    return levels, f"Cannot satisfy prerequisite {parent.name} for {node.name}"
                candidate[parent_id] += missing

        if not self.is_unlocked(skill_id, candidate):
            return levels, "Could not satisfy all prerequisites"
        candidate[skill_id] += 1
        if candidate[skill_id] > skill.max_level:
            return levels, f"{skill.name} is already at max level"
        return candidate, f"Auto-allocated prerequisites and added 1 point to {skill.name}"

    def validate_build(self, levels: dict[str, int], total_points: int | None = None) -> tuple[bool, list[str]]:
        errors: list[str] = []
        levels = dict(levels)
        for skill_id, level in levels.items():
            if skill_id not in self.skills:
                errors.append(f"Unknown skill ID in build: {skill_id}")
                continue
            if not isinstance(level, int):
                errors.append(f"Level for {skill_id} must be an integer")
                continue
            if level < 0 or level > self.skills[skill_id].max_level:
                errors.append(f"Level for {skill_id} is out of range")
        normalized = self.normalize_levels({k: v for k, v in levels.items() if k in self.skills and isinstance(v, int)})
        for skill_id, level in normalized.items():
            if level > 0 and not self.is_unlocked(skill_id, normalized):
                errors.append(f"{self.skills[skill_id].name} has points but its prerequisites are not satisfied")
        return not errors, errors

    def reset_tree(self) -> dict[str, int]:
        return self.empty_levels()

    def export_build(self, levels: dict[str, int]) -> dict[str, Any]:
        normalized = self.normalize_levels(levels)
        return {"version": 1, "levels": {skill_id: level for skill_id, level in normalized.items() if level > 0}}

    def import_build(self, data: dict[str, Any], total_points: int) -> dict[str, int]:
        if data.get("version") != 1:
            raise SkillTreeError("Unsupported build version")
        if not isinstance(data.get("levels"), dict):
            raise SkillTreeError("Build must contain a levels object")
        levels = self.normalize_levels(data["levels"])
        ok, errors = self.validate_build(levels, total_points)
        if not ok:
            raise SkillTreeError("; ".join(errors))
        return levels

    def component_payload(self, levels: dict[str, int]) -> list[dict[str, Any]]:
        levels = self.normalize_levels(levels)
        payload: list[dict[str, Any]] = []
        for skill in self.config.skills:
            item = skill.to_component_dict()
            item["level"] = levels[skill.id]
            item["unlocked"] = self.is_unlocked(skill.id, levels)
            item["missing"] = self.calculate_missing_prerequisites(skill.id, levels)
            payload.append(item)
        return payload


TREE_SLUG_OVERRIDES = {
    "Dark Power": "darkpower",
    "Dual Sword": "dualsword",
}


def skill_tree_slug(tree_name: str) -> str:
    return TREE_SLUG_OVERRIDES.get(tree_name, tree_name.lower().replace(" ", ""))


def skill_tree_from_restriction_files(paths: list[str | Path], total_points: int = 427) -> SkillTree:
    skills: list[dict[str, Any]] = []
    for path in paths:
        path = Path(path)
        if not path.read_text(encoding="utf-8").strip():
            continue
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        tree_name = str(data["skill_tree"])
        icon_folder = str(data.get("tree_slug") or skill_tree_slug(tree_name))
        for item in data["skills"]:
            row, column = item["position"]
            skill_id = str(item["id"])
            skills.append(
                {
                    "id": skill_id,
                    "name": item["name"],
                    "description": f"{item['name']} from the {tree_name} skill tree.",
                    "icon": f"assets/skill_tree/{icon_folder}/{skill_id}.png",
                    "max_level": 10,
                    "required_points": 5 if item.get("prerequisites") else 0,
                    "prerequisites": item.get("prerequisites", []),
                    "x": 90 + int(column) * 145,
                    "y": 95 + int(row) * 118,
                    "category": tree_name,
                }
            )
    return SkillTree(SkillTreeConfig.from_dict({"total_points": total_points, "skills": skills}))
