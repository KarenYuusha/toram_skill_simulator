from __future__ import annotations

from typing import Any

import streamlit as st

from toram_utils.core import SkillTree
from toram_utils.data.skill_details import raw_skill_tree_path


def tree_names(tree: SkillTree) -> list[str]:
    return sorted({skill.category or "Skills" for skill in tree.config.skills})


def tree_raw_group(tree_name: str) -> str:
    path = raw_skill_tree_path(tree_name)
    return path.parent.name if path.exists() else "weapon_class_skills"


def sort_trees_by_group(names: list[str]) -> list[str]:
    group_order = {
        "weapon_class_skills": 0,
        "sub_weapon_skills": 1,
        "assist_skills": 2,
        "other_skill_trees": 3,
    }
    return sorted(names, key=lambda name: (group_order.get(tree_raw_group(name), 99), name))


def sort_trees_by_spent(tree: SkillTree, names: list[str]) -> list[str]:
    return sorted(
        names,
        key=lambda name: (
            -sum(
                st.session_state.levels.get(skill.id, 0)
                for skill in tree.config.skills
                if (skill.category or "Skills") == name
            ),
            name,
        ),
    )


def current_build_settings() -> dict[str, Any]:
    return {
        "total_points": st.session_state.total_points,
        "tree_order": st.session_state.tree_order,
        "collapsed_trees": st.session_state.collapsed_trees,
        "auto_allocate": st.session_state.auto_allocate,
        "show_skill_tooltips": st.session_state.show_skill_tooltips,
        "edge_color": st.session_state.edge_color,
    }


def apply_build_settings(
    settings: dict[str, Any] | None,
    tree: SkillTree,
    *,
    defer_widget_settings: bool = False,
) -> None:
    if not isinstance(settings, dict):
        return
    names = tree_names(tree)
    if isinstance(settings.get("total_points"), int) and settings["total_points"] >= 0:
        st.session_state.total_points = settings["total_points"]
        st.session_state.pending_total_points_widget_sync = settings["total_points"]
    if isinstance(settings.get("tree_order"), list):
        order = [name for name in settings["tree_order"] if isinstance(name, str) and name in names]
        order.extend(name for name in names if name not in order)
        st.session_state.tree_order = order
    if isinstance(settings.get("collapsed_trees"), dict):
        st.session_state.collapsed_trees = {
            name: bool(settings["collapsed_trees"].get(name, st.session_state.collapsed_trees.get(name, True)))
            for name in names
        }
    widget_settings: dict[str, Any] = {}
    if isinstance(settings.get("auto_allocate"), bool):
        widget_settings["auto_allocate"] = settings["auto_allocate"]
    if isinstance(settings.get("show_skill_tooltips"), bool):
        widget_settings["show_skill_tooltips"] = settings["show_skill_tooltips"]
    if isinstance(settings.get("edge_color"), str) and settings["edge_color"].startswith("#"):
        widget_settings["edge_color"] = settings["edge_color"]
    if defer_widget_settings:
        st.session_state.pending_widget_settings = widget_settings
    else:
        st.session_state.update(widget_settings)


def initialize_state(tree: SkillTree) -> None:
    st.session_state.setdefault("levels", tree.empty_levels())
    st.session_state.setdefault("total_points", tree.config.total_points)
    if "pending_total_points_widget_sync" in st.session_state:
        st.session_state.total_points_input = st.session_state.pending_total_points_widget_sync
        del st.session_state.pending_total_points_widget_sync
    else:
        st.session_state.setdefault("total_points_input", st.session_state.total_points)
    st.session_state.setdefault("auto_allocate", True)
    st.session_state.setdefault("show_skill_tooltips", False)
    st.session_state.setdefault("edge_color", "#5cc8ff")
    if isinstance(st.session_state.get("pending_widget_settings"), dict):
        st.session_state.update(st.session_state.pending_widget_settings)
        del st.session_state.pending_widget_settings
    st.session_state.setdefault("last_event_id", None)
    st.session_state.setdefault("message", "")
    st.session_state.setdefault("saved_builds", [])
    st.session_state.setdefault("save_build_name", "")
    st.session_state.setdefault("save_build_description", "")
    st.session_state.setdefault("loaded_build_name", None)
    st.session_state.setdefault("authenticated_user", None)
    names = tree_names(tree)
    st.session_state.setdefault("tree_order", names)
    st.session_state.setdefault("collapsed_trees", {name: True for name in names})
    st.session_state.collapsed_trees = {
        name: bool(st.session_state.collapsed_trees.get(name, True)) for name in names
    }
    st.session_state.tree_order = [name for name in st.session_state.tree_order if name in names]
    st.session_state.tree_order.extend(name for name in names if name not in st.session_state.tree_order)
