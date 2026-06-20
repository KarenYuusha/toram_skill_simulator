from __future__ import annotations

from typing import Any

import streamlit as st


class SupabaseConfigError(RuntimeError):
    pass


def supabase_configured() -> bool:
    try:
        return bool(st.secrets.get("SUPABASE_URL") and st.secrets.get("SUPABASE_ANON_KEY"))
    except (FileNotFoundError, KeyError):
        return False


def create_supabase_client(access_token: str | None = None, refresh_token: str | None = None) -> Any:
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SupabaseConfigError("Install supabase>=2.10.0 to use Supabase storage") from exc

    try:
        url = st.secrets["SUPABASE_URL"]
        anon_key = st.secrets["SUPABASE_ANON_KEY"]
    except (FileNotFoundError, KeyError) as exc:
        raise SupabaseConfigError("Supabase secrets are not configured") from exc

    client = create_client(str(url), str(anon_key))
    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)
    return client


def current_auth_tokens() -> tuple[str | None, str | None]:
    return st.session_state.get("supabase_access_token"), st.session_state.get("supabase_refresh_token")


def current_user_id() -> str | None:
    return st.session_state.get("authenticated_user_id")


def authenticated_supabase_client() -> Any:
    access_token, refresh_token = current_auth_tokens()
    if not access_token or not refresh_token:
        raise SupabaseConfigError("No Supabase auth session is active")
    return create_supabase_client(access_token, refresh_token)
