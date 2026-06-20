from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import streamlit as st

from toram_utils.data.build_store import load_user_builds, load_user_preferences
from toram_utils.data.supabase_client import SupabaseConfigError, create_supabase_client, supabase_configured


def initialize_auth_state() -> None:
    st.session_state.setdefault("authenticated_user", None)
    st.session_state.setdefault("authenticated_user_id", None)
    st.session_state.setdefault("supabase_access_token", None)
    st.session_state.setdefault("supabase_refresh_token", None)
    st.session_state.setdefault("login_email", "")
    st.session_state.setdefault("login_password", "")


def is_logged_in() -> bool:
    return bool(st.session_state.get("authenticated_user_id"))


def apply_auth_session(response) -> None:
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if session is None or user is None:
        raise SupabaseConfigError("Check your email to confirm the account before logging in")

    user_id = getattr(user, "id", None)
    email = getattr(user, "email", None) or f"guest:{user_id or 'anonymous'}"
    st.session_state.authenticated_user = email
    st.session_state.authenticated_user_id = user_id
    st.session_state.supabase_access_token = session.access_token
    st.session_state.supabase_refresh_token = session.refresh_token
    st.session_state.saved_builds = load_user_builds(email)
    st.session_state.pending_user_preferences = load_user_preferences(email)


def auth_redirect_url() -> str | None:
    try:
        configured = st.secrets.get("AUTH_REDIRECT_URL") or st.secrets.get("APP_URL")
    except (FileNotFoundError, KeyError):
        configured = None

    if configured:
        return str(configured).rstrip("/") + "/"

    context = getattr(st, "context", None)
    current_url = getattr(context, "url", None) if context is not None else None
    if not current_url:
        return None

    parts = urlsplit(str(current_url))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def clear_auth_session() -> None:
    st.session_state.authenticated_user = None
    st.session_state.authenticated_user_id = None
    st.session_state.supabase_access_token = None
    st.session_state.supabase_refresh_token = None
    st.session_state.saved_builds = []


def render_login_controls() -> None:
    st.sidebar.header("Account")
    user = st.session_state.get("authenticated_user")
    if user:
        st.sidebar.success(f"Logged in as {user}")
        if st.sidebar.button("Log out", use_container_width=True):
            try:
                create_supabase_client().auth.sign_out()
            except SupabaseConfigError:
                pass
            clear_auth_session()
            st.session_state.message = "Logged out"
            st.rerun()
        return

    if not supabase_configured():
        st.sidebar.warning("Supabase Auth is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets.")
        return

    with st.sidebar.form("login_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        col_login, col_signup = st.columns(2)
        login_submitted = col_login.form_submit_button("Log in", use_container_width=True)
        signup_submitted = col_signup.form_submit_button("Sign up", use_container_width=True)
    reset_submitted = st.sidebar.button("Reset password", use_container_width=True)
    guest_submitted = st.sidebar.button("Continue as guest", use_container_width=True)

    if not login_submitted and not signup_submitted and not reset_submitted and not guest_submitted:
        st.sidebar.caption("Log in to save builds and preferences. Shared links can still be opened without logging in.")
        return

    if guest_submitted:
        try:
            response = create_supabase_client().auth.sign_in_anonymously()
            apply_auth_session(response)
            st.session_state.message = "Signed in as guest"
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Guest sign-in failed: {exc}")
        return

    if not email.strip():
        st.sidebar.error("Email is required")
        return

    if reset_submitted:
        try:
            options = {}
            redirect_url = auth_redirect_url()
            if redirect_url:
                options["redirect_to"] = redirect_url
            auth = create_supabase_client().auth
            if options:
                auth.reset_password_for_email(email.strip(), options)
            else:
                auth.reset_password_for_email(email.strip())
            st.sidebar.success("Password reset email sent")
        except Exception as exc:
            st.sidebar.error(f"Password reset failed: {exc}")
        return

    if not password:
        st.sidebar.error("Password is required")
        return

    try:
        client = create_supabase_client()
        if login_submitted:
            response = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
            apply_auth_session(response)
            st.session_state.message = f"Logged in as {email.strip()}"
        else:
            payload = {"email": email.strip(), "password": password}
            redirect_url = auth_redirect_url()
            if redirect_url:
                payload["options"] = {"email_redirect_to": redirect_url}
            response = client.auth.sign_up(payload)
            apply_auth_session(response)
            st.session_state.message = f"Signed up as {email.strip()}"
        st.rerun()
    except Exception as exc:
        st.sidebar.error(f"Authentication failed: {exc}")
