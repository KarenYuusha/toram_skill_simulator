from __future__ import annotations

import re

import streamlit as st
import streamlit.components.v1 as components

from toram_utils.core import SkillTree, SkillTreeError
from toram_utils.data.skill_details import (
    compact_key,
    raw_block_heading,
    raw_skill_heading_keys,
    raw_skill_tree_path,
    skill_detail_keys,
    trim_raw_skill_block,
)
from toram_utils.paths import ROOT
from toram_utils.ui.html import escape_html


def render_skill_docs_page(tree: SkillTree, tree_name: str, skill_id: str) -> None:
    try:
        skill = tree.get_skill(skill_id)
    except SkillTreeError as exc:
        st.error(str(exc))
        return
    path = raw_skill_tree_path(tree_name)
    st.title(f"{tree_name} Skill Details")
    st.caption(f"Highlighted skill: {skill.name}")

    if not path.exists():
        st.error(f"Raw skill tree file not found: {path.relative_to(ROOT)}")
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    target_keys = skill_detail_keys(skill_id)
    compact_target_keys = {key.replace("_", "").rstrip("s") for key in target_keys}
    target_ranges: list[tuple[int, int]] = []
    previous_marker = -1
    for index, line in enumerate(lines):
        marker = re.match(r"^(.+?)\s*\|\s*#?", line)
        if not marker:
            continue
        marker_name = marker.group(1).strip()
        marker_key = compact_key(marker_name)
        block_start = previous_marker + 1
        block = lines[block_start:index]
        trimmed = trim_raw_skill_block(marker_name, block)
        heading = raw_block_heading(trimmed)
        heading_key = compact_key(heading) if heading else ""
        if marker_key in compact_target_keys or heading_key in compact_target_keys:
            start = block_start + len(block) - len(trimmed)
            end = index + 1
            target_ranges.append((start, end))
            if skill_id != "multiple_hunt":
                break
        previous_marker = index

    if not target_ranges:
        heading_keys = raw_skill_heading_keys()
        starts = [index for index, line in enumerate(lines) if compact_key(line) in heading_keys]
        for position, start in enumerate(starts):
            heading_skill_id = heading_keys[compact_key(lines[start])]
            if not skill_detail_keys(heading_skill_id).intersection(target_keys):
                continue
            end = starts[position + 1] if position + 1 < len(starts) else len(lines)
            target_ranges.append((start, end))
            break

    html_lines = []
    has_target = bool(target_ranges)
    for index, line in enumerate(lines):
        classes = []
        in_target = any(start <= index < end for start, end in target_ranges)
        is_target_start = any(index == start for start, _end in target_ranges)
        if is_target_start:
            classes.append("target-start")
        if in_target:
            classes.append("target-block")
        class_attr = f' class="{" ".join(classes)}"' if classes else ""
        anchor = ' id="target-skill"' if has_target and index == target_ranges[0][0] else ""
        html_lines.append(f"<div{anchor}{class_attr}>{escape_html(line) or '&nbsp;'}</div>")

    st.markdown(
        """
        <style>
          .raw-skill-doc {
            background: #0b1020;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 14px;
            color: #eaf0ff;
            font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
            font-size: 0.92rem;
            line-height: 1.45;
            padding: 18px;
            white-space: pre-wrap;
          }
          .raw-skill-doc .target-block {
            background: rgba(255, 209, 102, 0.14);
            border-left: 3px solid #ffd166;
            padding-left: 10px;
          }
          .raw-skill-doc .target-start {
            color: #ffd166;
            font-weight: 800;
            scroll-margin-top: 24px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="raw-skill-doc">{"".join(html_lines)}</div>', unsafe_allow_html=True)
    if has_target:
        components.html(
            """
            <script>
              let attempts = 0;
              const parentDocument = () => {
                try {
                  return window.parent && window.parent.document;
                } catch {
                  return null;
                }
              };
              const scrollToTarget = () => {
                attempts += 1;
                const doc = parentDocument();
                let target = doc ? doc.getElementById("target-skill") : null;
                if (!target && doc) {
                  target = doc.querySelector('[id="target-skill"]');
                }
                if (!target) target = document.getElementById("target-skill");
                if (target) {
                  target.scrollIntoView({ block: "center", behavior: "smooth" });
                  return;
                }
                if (attempts < 80) setTimeout(scrollToTarget, 100);
              };
              requestAnimationFrame(scrollToTarget);
            </script>
            """,
            height=0,
        )


def render_jump_to_top() -> None:
    st.markdown(
        """
        <style>
          .jump-top {
            align-items: center;
            background: rgba(8, 12, 22, 0.92);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 999px;
            bottom: 22px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
            color: #f5f7fb !important;
            display: flex;
            font-weight: 800;
            height: 44px;
            justify-content: center;
            position: fixed;
            right: 22px;
            text-decoration: none !important;
            width: 72px;
            z-index: 9999;
          }
          .jump-top:hover {
            border-color: rgba(92, 200, 255, 0.7);
            box-shadow: 0 0 18px rgba(92, 200, 255, 0.35);
          }
        </style>
        <a class="jump-top" href="#top">Top</a>
        """,
        unsafe_allow_html=True,
    )
