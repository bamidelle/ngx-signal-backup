import streamlit as st
from app.utils.supabase_client import get_supabase


def get_current_user():
    return st.session_state.get("user", None)


def get_current_profile():
    return st.session_state.get("profile", None)


def load_profile(user_id: str) -> dict:
    try:
        sb = get_supabase()
        res = sb.table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data if res.data else {}
    except Exception as e:
        st.error(f"Could not load profile: {e}")
        return {}


def refresh_profile():
    """Reload profile from DB into session state"""
    user = st.session_state.get("user")
    if user:
        profile = load_profile(user.id)
        st.session_state.profile = profile


def sign_out():
    try:
        sb = get_supabase()
        sb.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.session_state.profile = None
    st.session_state.current_page = "home"
    st.rerun()
