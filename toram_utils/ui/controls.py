from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st

from toram_utils.core import SkillTree, SkillTreeError
from toram_utils.data.builds import (
    BuildPackageError,
    build_package,
    encode_build_code,
    unpack_build_package,
)
from toram_utils.data.build_store import save_user_builds, save_user_preferences
from toram_utils.ui.auth import is_logged_in, render_login_controls
from toram_utils.ui.state import (
    apply_build_settings,
    current_build_settings,
    sort_trees_by_group,
    sort_trees_by_spent,
    tree_names,
)
from toram_utils.ui.html import iframe_html


def import_packaged_or_raw_build(data: dict, tree: SkillTree) -> None:
    build, settings, name, description = unpack_build_package(data)
    apply_build_settings(settings, tree)
    st.session_state.levels = tree.import_build(build, st.session_state.total_points)
    if name:
        st.session_state.save_build_name = name
    st.session_state.save_build_description = description


def share_url_from_code(code: str) -> str:
    try:
        base_url = st.context.url.split("?", 1)[0]
    except Exception:
        return f"?build={code}"
    return f"{base_url}?{urlencode({'build': code})}"


def render_share_button(share_text: str, disabled: bool) -> None:
    disabled_attr = "disabled" if disabled else ""
    iframe_html(
        f"""
        <button id="share-build" type="button" {disabled_attr}>Share current build</button>
        <span id="share-status" role="status" aria-live="polite"></span>
        <style>
          body {{
            background: transparent;
            color: #f5f7fb;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
          }}
          #share-build {{
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 999px;
            color: #f5f7fb;
            cursor: pointer;
            font-weight: 900;
            padding: 0.65rem 1.15rem;
          }}
          #share-build:not(:disabled):hover {{
            background: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 255, 255, 0.3);
          }}
          #share-build:disabled {{
            cursor: not-allowed;
            opacity: 0.45;
          }}
          #share-status {{
            display: inline-block;
            font-size: 0.9rem;
            font-weight: 800;
            margin-left: 0.75rem;
          }}
        </style>
        <script>
          const shareText = {share_text!r};
          const button = document.getElementById("share-build");
          const status = document.getElementById("share-status");

          async function copyText(value) {{
            if (navigator.clipboard && window.isSecureContext) {{
              await navigator.clipboard.writeText(value);
              return;
            }}
            const textarea = document.createElement("textarea");
            textarea.value = value;
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            document.execCommand("copy");
            textarea.remove();
          }}

          button.addEventListener("click", async () => {{
            if (button.disabled) return;
            try {{
              await copyText(shareText);
              status.textContent = "Saved to clipboard";
              setTimeout(() => {{ status.textContent = ""; }}, 1800);
            }} catch (error) {{
              status.textContent = "Copy failed";
              setTimeout(() => {{ status.textContent = ""; }}, 2200);
            }}
          }});
        </script>
        """,
        height=54,
    )


def sidebar(tree: SkillTree) -> None:
    spent = tree.spent_points(st.session_state.levels)

    render_login_controls()
    st.sidebar.divider()
    st.sidebar.header("Build Controls")
    st.sidebar.number_input("Total points available", min_value=0, step=1, key="total_points_input")
    st.session_state.total_points = st.session_state.total_points_input
    point_color = "#ff6b6b" if spent > st.session_state.total_points else "inherit"
    st.sidebar.markdown(
        f'<div style="font-size: 1.35rem; font-weight: 700; color: {point_color};">'
        f'Points spent: {spent}/{st.session_state.total_points}'
        "</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Refund mode: Cascade. Downstream skills are automatically refunded when prerequisites become invalid.")
    st.sidebar.toggle(
        "Auto-allocate prerequisites",
        key="auto_allocate",
        help="When enabled, clicking a locked skill fills the minimum missing prerequisite points first.",
    )
    st.sidebar.toggle(
        "Show skill details on hover",
        key="show_skill_tooltips",
        help="When enabled, hovering a skill shows its description, level, and prerequisites.",
    )
    st.sidebar.color_picker(
        "Unlocked/preview edge color",
        key="edge_color",
        help="Used for unlocked prerequisite edges and highlighted prerequisite preview paths.",
    )

    col_a, col_b = st.sidebar.columns(2)
    if col_a.button("Reset", use_container_width=True):
        st.session_state.levels = tree.reset_tree()
        st.session_state.message = "Tree reset"
        st.rerun()
    if col_b.button("Refund all", use_container_width=True):
        st.session_state.levels = tree.reset_tree()
        st.session_state.message = "All points refunded"
        st.rerun()


def top_controls(tree: SkillTree) -> None:
    names = tree_names(tree)
    col_reset, col_expand, col_collapse, col_sort = st.columns(4)
    if col_reset.button("Reset all", use_container_width=True):
        st.session_state.levels = tree.reset_tree()
        st.session_state.message = "Tree reset"
        st.rerun()
    if col_expand.button("Expand all", use_container_width=True):
        st.session_state.collapsed_trees = {name: False for name in names}
        st.session_state.message = "Expanded all trees"
        st.rerun()
    if col_collapse.button("Collapse all", use_container_width=True):
        st.session_state.collapsed_trees = {name: True for name in names}
        st.session_state.message = "Collapsed all trees"
        st.rerun()
    with col_sort:
        with st.popover("Sort", use_container_width=True):
            if st.button("Alphabetical", use_container_width=True):
                st.session_state.tree_order = names
                st.session_state.message = "Sorted trees alphabetically"
                st.rerun()
            if st.button("By group", use_container_width=True):
                st.session_state.tree_order = sort_trees_by_group(names)
                st.session_state.message = "Sorted trees by raw skill group"
                st.rerun()
            if st.button("By points spent", use_container_width=True):
                st.session_state.tree_order = sort_trees_by_spent(tree, names)
                st.session_state.message = "Sorted trees by points spent"
                st.rerun()


def build_management_sections(tree: SkillTree) -> None:
    st.subheader("Load builds")
    saved_builds = st.session_state.saved_builds
    build_options = [build["name"] for build in saved_builds]
    selected_name = st.selectbox(
        "Saved builds",
        build_options,
        index=None,
        placeholder="No saved builds yet",
        disabled=not build_options,
    )
    selected_build = next((build for build in saved_builds if build["name"] == selected_name), None)
    share_package = (
        build_package(
            build=selected_build["build"],
            settings=selected_build.get("settings", {}),
            name=selected_build["name"],
            description=selected_build.get("description", ""),
        )
        if selected_build is not None
        else None
    )
    share_url = share_url_from_code(encode_build_code(share_package)) if share_package else ""
    render_share_button(share_url, selected_build is None)
    if selected_build is None:
        st.caption("Choose a saved build before sharing.")

    col_load, col_delete = st.columns(2)
    if col_load.button("Load build", use_container_width=True):
        try:
            if selected_build is None:
                raise SkillTreeError("Choose a saved build")
            imported = selected_build["build"]
            st.session_state.save_build_name = selected_build["name"]
            st.session_state.save_build_description = selected_build.get("description", "")
            apply_build_settings(selected_build.get("settings"), tree)
            st.session_state.levels = tree.import_build(imported, st.session_state.total_points)
            st.session_state.message = "Build loaded"
            st.rerun()
        except (SkillTreeError, TypeError, BuildPackageError) as exc:
            st.session_state.message = f"Load failed: {exc}"
            st.rerun()
    if col_delete.button("Delete", use_container_width=True):
        if selected_name is None:
            st.session_state.message = "Choose a saved build to delete"
        else:
            st.session_state.saved_builds = [build for build in saved_builds if build["name"] != selected_name]
            if st.session_state.authenticated_user:
                save_user_builds(st.session_state.authenticated_user, st.session_state.saved_builds)
            st.session_state.message = f"Deleted {selected_name}"
        st.rerun()

    st.subheader("Saved builds")
    if not is_logged_in():
        st.info("Log in to save builds. You can still allocate skills, load builds, and share selected builds without logging in.")
    with st.form("save_build_form"):
        name = st.text_input("Name", key="save_build_name")
        description = st.text_area("Description", height=90, key="save_build_description")
        if st.form_submit_button("Save", use_container_width=True, disabled=not is_logged_in()):
            if not name.strip():
                st.session_state.message = "Build name is required"
                st.rerun()
            build = {
                "name": name.strip(),
                "description": description.strip(),
                "build": tree.export_build(st.session_state.levels),
                "settings": current_build_settings(),
            }
            st.session_state.saved_builds = [item for item in saved_builds if item["name"] != build["name"]]
            st.session_state.saved_builds.append(build)
            save_user_builds(st.session_state.authenticated_user, st.session_state.saved_builds)
            st.session_state.message = f"Saved {build['name']}"
            st.rerun()

    if st.session_state.authenticated_user:
        save_user_preferences(st.session_state.authenticated_user, current_build_settings())
