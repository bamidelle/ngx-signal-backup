import streamlit as st
from supabase import create_client, Client
import os


@st.cache_resource
def get_supabase() -> Client:
    """Anon client — for all user-facing operations"""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def get_supabase_admin() -> Client:
    """
    Service role client — only for server-side scripts
    (scrapers, brief generator, GitHub Actions)
    Never expose this in Streamlit frontend
    """
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or st.secrets.get("SUPABASE_SERVICE_KEY")
    return create_client(url, key)
