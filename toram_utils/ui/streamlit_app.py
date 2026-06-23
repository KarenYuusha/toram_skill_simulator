from __future__ import annotations

import streamlit as st

from toram_utils.components.skill_graph import skill_graph
from toram_utils.core import SkillTree, SkillTreeError
from toram_utils.data.builds import BuildPackageError, decode_build_code
from toram_utils.data.restrictions import load_skill_tree, restriction_version
from toram_utils.data.skill_details import detail_lookup, load_raw_skill_details
from toram_utils.ui.assets import icon_data_uri
from toram_utils.ui.controls import build_management_sections, import_packaged_or_raw_build, sidebar, top_controls
from toram_utils.ui.docs import render_jump_to_top, render_skill_docs_page
from toram_utils.ui.events import apply_event
from toram_utils.ui.html import escape_html
from toram_utils.ui.state import apply_build_settings, initialize_state


@st.cache_resource
def load_tree(restriction_version_key: tuple[tuple[str, int, int], ...]) -> SkillTree:
    return load_skill_tree(total_points=427)


@st.cache_data
def cached_raw_skill_details() -> dict[str, str]:
    return load_raw_skill_details()


@st.cache_data
def cached_component_skill_metadata(restriction_version_key: tuple[tuple[str, int, int], ...]) -> list[dict]:
    tree = load_tree(restriction_version_key)
    details = cached_raw_skill_details()
    payload = []
    for skill in tree.config.skills:
        item = skill.to_component_dict()
        item["icon_data_uri"] = icon_data_uri(item["icon"])
        item["description"] = detail_lookup(details, item["id"]) or item["description"]
        payload.append(item)
    return payload


def component_skills(tree: SkillTree, restriction_version_key: tuple[tuple[str, int, int], ...]) -> list[dict]:
    levels = tree.normalize_levels(st.session_state.levels)
    payload = []
    for item in cached_component_skill_metadata(restriction_version_key):
        skill_id = item["id"]
        skill = tree.get_skill(skill_id)
        next_item = dict(item)
        next_item["level"] = levels[skill_id]
        next_item["unlocked"] = all(levels[parent_id] >= skill.required_points for parent_id in skill.prerequisites)
        next_item["missing"] = {
            parent_id: skill.required_points - levels[parent_id]
            for parent_id in skill.prerequisites
            if levels[parent_id] < skill.required_points
        }
        payload.append(next_item)
    return payload


def render_message() -> None:
    message_html = escape_html(st.session_state.message) if st.session_state.message else "&nbsp;"
    st.markdown(
        f"""
        <div style="min-height: 3.25rem; margin-bottom: 0.5rem;">
          <div style="
            background: rgba(76, 110, 245, 0.12);
            border: 1px solid rgba(76, 110, 245, 0.28);
            border-radius: 0.5rem;
            color: inherit;
            padding: 0.75rem 1rem;
            visibility: {'visible' if st.session_state.message else 'hidden'};
          ">{message_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_shared_build_from_url(tree: SkillTree) -> None:
    code = st.query_params.get("build")
    if not isinstance(code, str) or not code or st.session_state.get("loaded_build_code") == code:
        return
    try:
        import_packaged_or_raw_build(decode_build_code(code), tree)
        st.session_state.loaded_build_code = code
        name = st.session_state.save_build_name
        st.session_state.message = f"Loaded shared build: {name}" if name else "Loaded shared build"
    except (BuildPackageError, SkillTreeError, TypeError) as exc:
        st.session_state.loaded_build_code = code
        st.session_state.message = f"Shared build link failed: {exc}"


def main() -> None:
    st.set_page_config(page_title="RPG Skill Tree Simulator", layout="wide")
    st.markdown('<span id="top"></span>', unsafe_allow_html=True)
    render_jump_to_top()
    doc_tree = st.query_params.get("doc_tree")
    doc_skill = st.query_params.get("skill")

    try:
        version_key = restriction_version()
        tree = load_tree(version_key)
    except (OSError, ValueError, SkillTreeError) as exc:
        st.error(f"Skill-tree validation failed: {exc}")
        st.stop()

    if isinstance(doc_tree, str) and isinstance(doc_skill, str):
        render_skill_docs_page(tree, doc_tree, doc_skill)
        return

    st.title("RPG Skill Tree Simulator")

    initialize_state(tree)
    if isinstance(st.session_state.get("pending_user_preferences"), dict):
        apply_build_settings(st.session_state.pending_user_preferences, tree)
        del st.session_state.pending_user_preferences
        if "pending_total_points_widget_sync" in st.session_state:
            st.session_state.total_points_input = st.session_state.pending_total_points_widget_sync
            del st.session_state.pending_total_points_widget_sync
    apply_shared_build_from_url(tree)
    pending_event = st.session_state.get("skill_graph")
    if isinstance(pending_event, dict):
        apply_event(tree, pending_event)

    ok, errors = tree.validate_build(st.session_state.levels)
    if not ok:
        st.error("Current build is invalid: " + "; ".join(errors))
        st.session_state.levels = tree.reset_tree()

    sidebar(tree)

    spent = tree.spent_points(st.session_state.levels)
    remaining = tree.remaining_points(st.session_state.levels, st.session_state.total_points)
    st.caption(
        "Left-click a skill to add a level. Right-click a skill to refund one level. "
        "Ctrl+left-click opens the raw skill-tree details in a new tab. "
        "Python session state is the source of truth for every allocation."
    )
    top_controls(tree)
    build_management_sections(tree)
    render_message()

    event = skill_graph(
        skills=component_skills(tree, version_key),
        levels=st.session_state.levels,
        total_points=st.session_state.total_points,
        remaining_points=remaining,
        settings={
            "decrement_mode": "Cascade",
            "auto_allocate": st.session_state.auto_allocate,
            "show_skill_tooltips": st.session_state.show_skill_tooltips,
            "edge_color": st.session_state.edge_color,
            "spent_points": spent,
            "tree_order": st.session_state.tree_order,
            "collapsed_trees": st.session_state.collapsed_trees,
        },
        key="skill_graph",
    )
    apply_event(tree, event)


if __name__ == "__main__":
    main()
