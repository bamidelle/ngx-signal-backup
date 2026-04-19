import os
from supabase import create_client
from signal_engine import run_batch

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

sb = create_client(url, key)
run_batch(sb)