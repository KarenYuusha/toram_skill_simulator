from __future__ import annotations

from typing import Any

import streamlit as st

from toram_utils.core import SkillTree, SkillTreeError


def apply_skill_event(tree: SkillTree, event: dict[str, Any]) -> tuple[dict[str, int], str]:
    skill_id = event.get("skill_id")
    action = event.get("action")

    if not isinstance(skill_id, str):
        return st.session_state.levels, "Invalid graph event"

    try:
        if action == "increment":
            if tree.is_unlocked(skill_id, st.session_state.levels):
                return tree.increment_skill(skill_id, st.session_state.levels, st.session_state.total_points)
            if st.session_state.auto_allocate:
                return tree.auto_allocate_and_increment(skill_id, st.session_state.levels, st.session_state.total_points)
            missing = tree.calculate_missing_prerequisites(skill_id, st.session_state.levels)
            detail = ", ".join(
                f"{tree.get_skill(parent_id).name} needs {amount} more point(s)"
                for parent_id, amount in missing.items()
            )
            return st.session_state.levels, f"{tree.get_skill(skill_id).name} is locked: {detail}"
        if action == "decrement":
            return tree.decrement_skill_cascade(skill_id, st.session_state.levels)
        return st.session_state.levels, "Unknown graph action"
    except SkillTreeError as exc:
        return st.session_state.levels, str(exc)


def apply_event(tree: SkillTree, event: dict[str, Any] | None) -> bool:
    if not event or event.get("event_id") == st.session_state.last_event_id:
        return False
    st.session_state.last_event_id = event.get("event_id")
    skill_id = event.get("skill_id")
    action = event.get("action")

    if action == "toggle_tree":
        tree_name = event.get("tree")
        if isinstance(tree_name, str):
            collapsed = dict(st.session_state.collapsed_trees)
            target = event.get("collapsed")
            collapsed[tree_name] = bool(target) if isinstance(target, bool) else not collapsed.get(tree_name, True)
            st.session_state.collapsed_trees = collapsed
            return True
        return False
    if action == "reset_tree":
        tree_name = event.get("tree")
        if isinstance(tree_name, str):
            levels = dict(st.session_state.levels)
            reset_count = 0
            for skill in tree.config.skills:
                if (skill.category or "Skills") != tree_name:
                    continue
                if levels.get(skill.id, 0) > 0:
                    reset_count += 1
                levels[skill.id] = 0
            st.session_state.levels = levels
            st.session_state.message = f"Reset {tree_name} tree ({reset_count} skill(s) cleared)"
            return True
        return False
    if action == "reorder_trees":
        order = event.get("tree_order")
        if isinstance(order, list) and all(isinstance(item, str) for item in order):
            known = {skill.category or "Skills" for skill in tree.config.skills}
            st.session_state.tree_order = [item for item in order if item in known]
            st.session_state.tree_order.extend(sorted(known - set(st.session_state.tree_order)))
            return True
        return False
    if action == "skill_batch":
        events = event.get("events")
        if not isinstance(events, list):
            st.session_state.message = "Invalid graph event"
            return True
        message = st.session_state.message
        for item in events:
            if not isinstance(item, dict):
                continue
            levels, message = apply_skill_event(tree, item)
            st.session_state.levels = levels
        st.session_state.message = message
        return True

    levels, message = apply_skill_event(tree, event)
    st.session_state.levels = levels
    st.session_state.message = message
    return True
