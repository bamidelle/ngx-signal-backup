from signal_engine import run_batch
from app.utils.supabase_client import get_supabase

sb = get_supabase()
run_batch(sb)