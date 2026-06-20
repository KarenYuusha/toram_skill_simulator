from __future__ import annotations

from urllib.parse import quote

import streamlit as st


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def iframe_html(html: str, height: int = 0) -> None:
    src = "data:text/html;charset=utf-8," + quote(html)
    st.iframe(src, height=height)
