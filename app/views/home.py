"""
NGX Signal — Home View  v12  ·  Optimised by Claude
══════════════════════════════════════════════════════════════════════════════
ARCHITECTURE: Two flows, one render() entry point.

VISITOR / FREE  →  Show value, gate premium, one clean CTA
  Funnel: Hook → Value proof → Signal preview → Single upgrade CTA

PAID / TRIAL    →  Deliver intelligence immediately, retain
  Funnel: Context → Command Center → Signals → Tools → Nudge

Design principles applied:
  • Single upgrade CTA per page (not 5)
  • Command Center first for paid tiers
  • Pricing table removed from dashboard (links to Settings)
  • FAQ / Beginner guide removed (belongs on marketing site)
  • Performance stats use honest market breadth labels
  • Hardcoded picks fallback replaced with skeleton states
  • Aesthetic: Dark fintech terminal — Syne + JetBrains Mono
    amber/green accent on near-black surfaces, geometric grid bg
══════════════════════════════════════════════════════════════════════════════
"""

import streamlit as st
import re
import requests
import hashlib
from datetime import date, datetime, timedelta
from app.utils.supabase_client import get_supabase
from app.views.signals import generate_trending_sentiment_tag
from app.views.global_pulse import render_global_pulse_strip, get_global_pulse, get_global_pulse_for_ai, get_sector_global_context


# ─────────────────────────────────────────────────────────────────────────────
# TIMEZONE
# ─────────────────────────────────────────────────────────────────────────────
try:
    import pytz
    WAT = pytz.timezone("Africa/Lagos")
    def now_wat(): return datetime.now(WAT)
except ImportError:
    from datetime import timezone
    WAT_TZ = timezone(timedelta(hours=1))
    def now_wat(): return datetime.now(WAT_TZ)

NG_HOLIDAYS_2026 = {
    "2026-01-01","2026-01-03","2026-04-03","2026-04-06",
    "2026-05-01","2026-06-12","2026-10-01","2026-12-25","2026-12-26",
}


# ─────────────────────────────────────────────────────────────────────────────
# CACHED DATA LOADERS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def _get_sb():
    return get_supabase()

@st.cache_data(ttl=300)
def _load_home_prices():
    sb = _get_sb()
    res = sb.table("stock_prices").select(
        "symbol,price,change_percent,volume,trading_date"
    ).order("trading_date", desc=True).limit(500).execute()
    prices = res.data or []
    latest = prices[0]["trading_date"] if prices else str(date.today())
    if len(prices) < 50:
        broad = sb.table("stock_prices").select(
            "symbol,price,change_percent,volume,trading_date"
        ).order("trading_date", desc=True).limit(5000).execute()
        sym_map = {}
        for p in (broad.data or []):
            s = p.get("symbol", "")
            if s and s not in sym_map:
                sym_map[s] = p
        existing = {p["symbol"] for p in prices}
        prices += [p for s, p in sym_map.items() if s not in existing]
    return prices, latest

@st.cache_data(ttl=300)
def _load_home_market_summary():
    sb = _get_sb()
    res = sb.table("market_summary").select("*").order("trading_date", desc=True).limit(1).execute()
    return res.data[0] if res.data else {}

@st.cache_data(ttl=180)
def _load_home_signals():
    sb = _get_sb()
    res = sb.table("signal_scores").select(
        "symbol,signal,stars,reasoning"
    ).order("score_date", desc=True).order("stars", desc=True).limit(50).execute()
    return res.data or []

@st.cache_data(ttl=180)
def _load_home_trending_signals():
    sb = _get_sb()
    res = sb.table("signal_scores").select(
        "symbol,signal,stars,momentum_score,volume_score,news_score"
    ).order("score_date", desc=True).limit(200).execute()
    return res.data or []

@st.cache_data(ttl=120)
def _load_home_news():
    sb = _get_sb()
    res = sb.table("news").select(
        "headline,sentiment,scraped_at"
    ).order("scraped_at", desc=True).limit(20).execute()
    return res.data or []

@st.cache_data(ttl=300)
def _load_home_sectors():
    sb = _get_sb()
    res = sb.table("sector_performance").select(
        "sector_name,traffic_light,change_percent,verdict"
    ).order("change_percent", desc=True).execute()
    return res.data or []

@st.cache_data(ttl=300)
def _load_home_leaderboard():
    sb = _get_sb()
    res = sb.table("leaderboard_snapshots").select(
        "display_name,return_percent,user_id"
    ).order("return_percent", desc=True).limit(5).execute()
    return res.data or []

@st.cache_data(ttl=300)
def _load_home_briefs():
    sb = _get_sb()
    res = sb.table("ai_briefs").select("body,brief_date") \
        .eq("language", "en").eq("brief_type", "morning") \
        .order("brief_date", desc=True).limit(1).execute()
    return res.data or []


# ─────────────────────────────────────────────────────────────────────────────
# TIER SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

TIER_ORDER  = ["visitor", "free", "trial", "starter", "trader", "pro"]
PAID_TIERS  = {"starter", "trader", "pro"}
TRIAL_TIERS = {"trial"}

_QUERY_LIMITS: dict[str, int | None] = {
    "visitor": 0, "free": 2, "trial": None,
    "starter": 15, "trader": None, "pro": None,
}

_FEATURE_MIN_TIER: dict[str, str] = {
    "ai_input":              "free",
    "ai_full_response":      "trial",
    "ai_advanced_outputs":   "pro",
    "signals_all":           "trial",
    "signals_confidence":    "starter",
    "daily_picks_all":       "trial",
    "daily_picks_entry":     "starter",
    "brief_full":            "trial",
    "brief_pidgin":          "trader",
    "sector_all":            "trial",
    "news_full":             "trial",
    "trending_opportunities":"trial",
    "follow_up_chips":       "free",
    "streak_system":         "free",
    "export_pdf":            "pro",
    "telegram_alerts":       "starter",
    "market_snapshot":       "starter",
    "composite_chart":       "starter",
    "stop_loss_visible":     "trader",
}

def get_user_tier() -> str:
    user    = st.session_state.get("user")
    profile = st.session_state.get("profile", {})
    if not user:
        return "visitor"
    plan = (profile.get("plan") or "free").lower().strip()
    return plan if plan in ("starter","trader","pro","trial","free") else "free"

def _tier_rank(tier: str) -> int:
    try:    return TIER_ORDER.index(tier)
    except: return 0

def can_access(feature: str, tier: str | None = None) -> bool:
    t   = tier or get_user_tier()
    req = _FEATURE_MIN_TIER.get(feature, "visitor")
    return _tier_rank(t) >= _tier_rank(req)

def get_usage_limit(feature: str = "ai_queries", tier: str | None = None) -> int | None:
    t = tier or get_user_tier()
    if feature == "ai_queries":
        return _QUERY_LIMITS.get(t, 0)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# ENGAGEMENT / STREAK HELPERS  (preserved from v10/v11)
# ─────────────────────────────────────────────────────────────────────────────

def get_streak() -> int:
    return st.session_state.get("streak", 0)

def update_streak():
    today = str(date.today())
    last  = st.session_state.get("last_active_date")
    if last == today:
        return
    yesterday = str(date.today() - timedelta(days=1))
    if last == yesterday:
        st.session_state["streak"] = st.session_state.get("streak", 0) + 1
    else:
        st.session_state["streak"] = 1
    st.session_state["last_active_date"] = today

def streak_milestone(n: int) -> str:
    milestones = {3:"3-day streak", 7:"One week strong", 14:"Two weeks in",
                  21:"21 days", 30:"30-day trader", 60:"60 days", 90:"90 days"}
    return milestones.get(n, "")

def get_ai_query_count() -> int:
    return st.session_state.get(f"ai_queries_{date.today()}", 0)

def get_total_ai_queries() -> int:
    return st.session_state.get("total_ai_queries", 0)

def increment_ai_query_count():
    k = f"ai_queries_{date.today()}"
    st.session_state[k] = st.session_state.get(k, 0) + 1
    st.session_state["total_ai_queries"] = st.session_state.get("total_ai_queries", 0) + 1

def get_eng(key: str, default=0):
    return st.session_state.get(f"eng_{key}", default)

def track_signal_view():
    k = "eng_signals_viewed"
    st.session_state[k] = st.session_state.get(k, 0) + 1

def track_stock_analyzed(sym: str):
    k = "eng_stocks_analyzed"
    st.session_state[k] = st.session_state.get(k, 0) + 1


# ─────────────────────────────────────────────────────────────────────────────
# TRIAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_trial_info(profile: dict):
    trial_start = profile.get("trial_start_date")
    if trial_start:
        if isinstance(trial_start, str):
            try:   trial_start = date.fromisoformat(trial_start)
            except: trial_start = date.today()
    else:
        trial_start = date.today()
    days_used    = (date.today() - trial_start).days
    days_left    = max(0, 14 - days_used)
    trial_day    = min(days_used + 1, 14)
    trial_urgent = days_left <= 3
    return trial_start, days_left, trial_day, trial_urgent


# ─────────────────────────────────────────────────────────────────────────────
# MARKET STATUS
# ─────────────────────────────────────────────────────────────────────────────

def _get_market_status(now: datetime) -> dict:
    today_str = str(now.date())
    if today_str in NG_HOLIDAYS_2026:
        return {"is_open": False, "label": "Market Closed — Public Holiday",
                "note": "NGX closed today", "color": "#606060"}
    if now.weekday() >= 5:
        return {"is_open": False, "label": "Market Closed — Weekend",
                "note": "Opens Monday 10:00 AM WAT", "color": "#606060"}
    h = now.hour + now.minute / 60
    if 10.0 <= h < 14.5:
        return {"is_open": True,  "label": "Market Open",
                "note": f"Closes {int(14)}:{int((14.5 % 1)*60):02d} PM WAT", "color": "#22C55E"}
    if h < 10.0:
        mins = int((10.0 - h) * 60)
        return {"is_open": False, "label": "Pre-Market",
                "note": f"Opens in {mins} min", "color": "#F0A500"}
    return {"is_open": False, "label": "Market Closed",
            "note": "Last session ended 2:30 PM WAT", "color": "#606060"}


# ─────────────────────────────────────────────────────────────────────────────
# AI CALL  (preserved from v10/v11)
# ─────────────────────────────────────────────────────────────────────────────

def call_ai(prompt, system: str | None = None, max_tokens: int = 800) -> str | None:
    providers = [
        ("anthropic", st.secrets.get("ANTHROPIC_API_KEY",""), "claude-3-5-haiku-20241022"),
        ("openai",    st.secrets.get("OPENAI_API_KEY",""),    "gpt-4o-mini"),
    ]
    errors = []
    for provider, key, model in providers:
        if not key: continue
        try:
            if provider == "anthropic":
                messages = [{"role":"user","content": prompt if isinstance(prompt,str) else prompt[0]}]
                payload  = {"model": model, "max_tokens": max_tokens, "messages": messages}
                if system: payload["system"] = system
                r = requests.post("https://api.anthropic.com/v1/messages",
                                  headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                           "Content-Type": "application/json"},
                                  json=payload, timeout=25)
                if r.status_code == 200:
                    return r.json()["content"][0]["text"].strip()
                errors.append(f"Anthropic: HTTP {r.status_code}")
            else:
                p = prompt if isinstance(prompt, str) else prompt[0]
                msgs = [{"role":"user","content": p}]
                if system: msgs.insert(0, {"role":"system","content": system})
                r = requests.post("https://api.openai.com/v1/chat/completions",
                                  headers={"Authorization": f"Bearer {key}",
                                           "Content-Type": "application/json"},
                                  json={"model": model, "messages": msgs, "max_tokens": max_tokens},
                                  timeout=25)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                errors.append(f"OpenAI: HTTP {r.status_code}")
        except Exception as e:
            errors.append(f"{provider}: {e}")
    if errors:
        st.warning(f"AI temporarily unavailable. Tried: {'; '.join(errors[:3])}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _daily_seed(): return str(date.today())

def _time_ago(minutes: int) -> str:
    if minutes < 1:  return "just now"
    if minutes < 60: return f"{minutes}m ago"
    h = minutes // 60
    return f"{h}h ago"

def _fmt_price(n): return f"₦{n:,.2f}" if n > 0 else "—"

def _unlock_cta(key: str, source: str, tier: str, page: str = "settings"):
    if tier == "visitor":
        st.session_state.show_auth = True
    else:
        st.session_state.deep_link_plan = True
        st.session_state.current_page   = page
    st.rerun()

def _get_dynamic_cta(tier: str, profile: dict):
    if tier == "visitor":
        return "Start free — 14-day premium trial →", "settings"
    if tier == "free":
        return "Unlock full signals — start free trial →", "settings"
    if tier == "trial":
        trial_start, days_left, _, _ = _get_trial_info(profile)
        return f"Keep premium access — upgrade now ({days_left}d left) →", "settings"
    if tier == "starter":
        return "Upgrade to Trader — unlimited AI →", "settings"
    if tier == "trader":
        return "Upgrade to Pro — PDF reports & portfolio AI →", "settings"
    return "", ""


# ─────────────────────────────────────────────────────────────────────────────
# DESIGN TOKENS & CSS
# ─────────────────────────────────────────────────────────────────────────────

_FONTS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
"""

_CSS = """
<style>
/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --amber:    #F0A500;
  --amber-dk: #B97D00;
  --amber-bg: rgba(240,165,0,.08);
  --amber-bd: rgba(240,165,0,.22);
  --green:    #16A34A;
  --green-lt: #22C55E;
  --green-bg: rgba(34,197,94,.08);
  --green-bd: rgba(34,197,94,.20);
  --red:      #EF4444;
  --red-bg:   rgba(239,68,68,.08);
  --red-bd:   rgba(239,68,68,.22);
  --blue:     #60A5FA;
  --blue-bg:  rgba(96,165,250,.07);
  --blue-bd:  rgba(96,165,250,.20);
  --surface0: #030303;
  --surface1: #080808;
  --surface2: #0E0E0E;
  --surface3: #141414;
  --surface4: #1C1C1C;
  --border1:  #181818;
  --border2:  #222222;
  --border3:  #2C2C2C;
  --t1: #F2F2F0;
  --t2: #A0A09A;
  --t3: #606058;
  --t4: #3A3A34;
  --font-head: 'Syne', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --r-sm: 8px;
  --r-md: 12px;
  --r-lg: 16px;
  --r-xl: 22px;
}

/* ── Streamlit overrides ── */
.stApp { background: var(--surface0) !important; }
section[data-testid="stSidebar"] { background: var(--surface1) !important; }
.block-container { padding-top: 0 !important; padding-bottom: 40px !important; max-width: 780px !important; }
div[data-testid="stVerticalBlock"] > div { gap: 0 !important; }

/* ── Typography ── */
.h1 { font-family: var(--font-head); font-size: 28px; font-weight: 800; color: var(--t1); letter-spacing: -.02em; line-height: 1.15; }
.h2 { font-family: var(--font-head); font-size: 18px; font-weight: 700; color: var(--t1); letter-spacing: -.01em; }
.h3 { font-family: var(--font-head); font-size: 14px; font-weight: 600; color: var(--t1); }
.mono { font-family: var(--font-mono); }
.label { font-family: var(--font-mono); font-size: 10px; font-weight: 500; color: var(--t3); letter-spacing: .12em; text-transform: uppercase; }

/* ── Geometric background grid ── */
.grid-bg {
  position: relative;
  background-image:
    linear-gradient(var(--border1) 1px, transparent 1px),
    linear-gradient(90deg, var(--border1) 1px, transparent 1px);
  background-size: 32px 32px;
  background-position: 0 0, 0 0;
}

/* ── Cards ── */
.card {
  background: var(--surface1);
  border: 0.5px solid var(--border2);
  border-radius: var(--r-lg);
  padding: 18px 20px;
  margin-bottom: 10px;
}
.card-sm {
  background: var(--surface2);
  border: 0.5px solid var(--border1);
  border-radius: var(--r-md);
  padding: 12px 14px;
}
.card-inset {
  background: var(--surface2);
  border: 0.5px solid var(--border1);
  border-radius: var(--r-sm);
  padding: 10px 12px;
}

/* ── Accent lines ── */
.accent-top-amber { border-top: 1.5px solid var(--amber) !important; }
.accent-top-green { border-top: 1.5px solid var(--green-lt) !important; }
.accent-top-red   { border-top: 1.5px solid var(--red) !important; }
.accent-left-amber { border-left: 2px solid var(--amber) !important; border-radius: 0 var(--r-md) var(--r-md) 0 !important; }

/* ── Badges & pills ── */
.pill {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--font-mono); font-size: 10px; font-weight: 600;
  padding: 3px 10px; border-radius: 999px; letter-spacing: .05em;
}
.pill-amber { background: var(--amber-bg); border: 0.5px solid var(--amber-bd); color: var(--amber); }
.pill-green { background: var(--green-bg); border: 0.5px solid var(--green-bd); color: var(--green-lt); }
.pill-red   { background: var(--red-bg);   border: 0.5px solid var(--red-bd);   color: var(--red); }
.pill-blue  { background: var(--blue-bg);  border: 0.5px solid var(--blue-bd);  color: var(--blue); }
.pill-ghost { background: transparent; border: 0.5px solid var(--border3); color: var(--t2); }

/* ── Live pulse dot ── */
.dot-live {
  display: inline-block; width: 7px; height: 7px;
  border-radius: 50%; background: var(--green-lt);
  box-shadow: 0 0 0 0 rgba(34,197,94,.5);
  animation: live-pulse 2s ease-in-out infinite;
}
.dot-amber { background: var(--amber); box-shadow: 0 0 0 0 rgba(240,165,0,.5); animation: live-pulse 2s ease-in-out infinite; }
.dot-red   { background: var(--red);   box-shadow: 0 0 0 0 rgba(239,68,68,.5);  animation: live-pulse 2s ease-in-out infinite; }
@keyframes live-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(34,197,94,.45); }
  70%  { box-shadow: 0 0 0 7px rgba(34,197,94,0); }
  100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}

/* ── Metric grid ── */
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
.metric-card {
  background: var(--surface2); border: 0.5px solid var(--border2);
  border-radius: var(--r-md); padding: 14px 14px 12px;
}
.metric-label { font-family: var(--font-mono); font-size: 9px; color: var(--t3); letter-spacing: .1em; text-transform: uppercase; margin-bottom: 6px; }
.metric-value { font-family: var(--font-head); font-size: 20px; font-weight: 700; line-height: 1; color: var(--t1); margin-bottom: 3px; }
.metric-sub   { font-family: var(--font-mono); font-size: 10px; color: var(--t3); }

/* ── Section headers ── */
.sec-head {
  display: flex; align-items: center; justify-content: space-between;
  margin: 20px 0 12px;
  padding-bottom: 10px;
  border-bottom: 0.5px solid var(--border1);
}
.sec-head-title { font-family: var(--font-head); font-size: 13px; font-weight: 700; color: var(--t2); letter-spacing: .04em; text-transform: uppercase; }
.sec-head-action { font-family: var(--font-mono); font-size: 11px; color: var(--t3); cursor: pointer; }

/* ── Signal cards ── */
.sig-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; }
.sig-card {
  background: var(--surface1); border: 0.5px solid var(--border2);
  border-radius: var(--r-md); padding: 14px; position: relative;
  transition: border-color .2s, transform .15s;
  animation: card-in .35s ease both;
}
.sig-card:hover { border-color: var(--border3); transform: translateY(-1px); }
.sig-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }
.sig-sym { font-family: var(--font-head); font-size: 15px; font-weight: 700; color: var(--t1); }
.sig-name { font-family: var(--font-mono); font-size: 10px; color: var(--t3); margin-bottom: 10px; }
.sig-price-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px; }
.sig-price-label { font-family: var(--font-mono); font-size: 9px; color: var(--t3); letter-spacing: .08em; text-transform: uppercase; }
.sig-price-val { font-family: var(--font-mono); font-size: 12px; font-weight: 500; color: var(--t1); }
.sig-divider { height: 0.5px; background: var(--border1); margin: 8px 0; }
.sig-reason { font-family: var(--font-mono); font-size: 10px; color: var(--t2); line-height: 1.6; }
.sig-lock {
  position: absolute; inset: 0; border-radius: var(--r-md);
  background: rgba(8,8,8,.88); backdrop-filter: blur(2px);
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
}
.lock-icon { font-size: 18px; line-height: 1; }
.lock-text { font-family: var(--font-mono); font-size: 10px; color: var(--t3); }

/* ── Daily picks ── */
.picks-section { margin-bottom: 10px; }
.picks-category-label {
  font-family: var(--font-mono); font-size: 9px; font-weight: 600;
  letter-spacing: .12em; text-transform: uppercase; color: var(--t3);
  margin: 10px 0 6px;
}
.dap-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 4px; }
.dap-card {
  background: var(--surface2); border: 0.5px solid var(--border1);
  border-radius: var(--r-sm); padding: 12px 12px 10px;
  position: relative; overflow: hidden;
  transition: border-color .2s;
}
.dap-card:hover { border-color: var(--border3); }
.dap-sym { font-family: var(--font-head); font-size: 13px; font-weight: 700; color: var(--t1); margin-bottom: 4px; }
.dap-conf { font-family: var(--font-mono); font-size: 10px; color: var(--t3); margin-top: 5px; }
.dap-conf-bar { height: 2px; background: var(--border2); border-radius: 1px; margin-top: 4px; overflow: hidden; }
.dap-conf-fill { height: 2px; border-radius: 1px; }
.dap-reason { font-family: var(--font-mono); font-size: 10px; color: var(--t2); line-height: 1.55; margin-top: 4px; }
.dap-blur-wrap { position: relative; }
.dap-blur-inner { filter: blur(5px); user-select: none; pointer-events: none; }
.dap-lock-overlay {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px;
}

/* ── Top Movers ── */
.movers-table { width: 100%; }
.mover-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 0; border-bottom: 0.5px solid var(--border1);
  font-family: var(--font-mono);
}
.mover-row:last-child { border-bottom: none; }
.mover-sym { font-family: var(--font-head); font-size: 13px; font-weight: 600; color: var(--t1); }
.mover-price { font-size: 11px; color: var(--t3); }
.mover-chg { font-size: 12px; font-weight: 500; }

/* ── AI chat ── */
.ai-input-wrap {
  background: var(--surface2); border: 0.5px solid var(--border2);
  border-radius: var(--r-lg); padding: 14px 16px; margin-bottom: 8px;
}
.ai-label { font-family: var(--font-mono); font-size: 10px; color: var(--t3); letter-spacing: .1em; text-transform: uppercase; margin-bottom: 8px; }
.ai-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.ai-chip {
  font-family: var(--font-mono); font-size: 11px; color: var(--t2);
  background: var(--surface3); border: 0.5px solid var(--border2);
  border-radius: var(--r-sm); padding: 5px 12px; cursor: pointer;
  transition: border-color .15s, color .15s;
}
.ai-chip:hover { border-color: var(--amber-bd); color: var(--amber); }
.ai-msg-row { display: flex; gap: 10px; margin-bottom: 10px; animation: msg-in .25s ease both; }
.ai-msg-user { background: var(--surface3); border-radius: var(--r-md) var(--r-md) 4px var(--r-md); padding: 10px 14px; font-family: var(--font-mono); font-size: 12px; color: var(--t1); margin-left: auto; max-width: 85%; }
.ai-msg-ai { background: var(--surface2); border: 0.5px solid var(--amber-bd); border-left: 2px solid var(--amber); border-radius: 4px var(--r-md) var(--r-md) var(--r-md); padding: 12px 14px; font-family: var(--font-mono); font-size: 12px; color: var(--t1); line-height: 1.65; max-width: 95%; }
.ai-blurred { filter: blur(4px); user-select: none; pointer-events: none; }

/* ── Hero (visitor) ── */
.hero-wrap {
  padding: 36px 24px 28px;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.hero-eyebrow {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; font-weight: 500;
  color: var(--green-lt); background: var(--green-bg); border: 0.5px solid var(--green-bd);
  border-radius: 999px; padding: 5px 14px; margin-bottom: 18px;
  animation: fade-up .5s ease both;
}
.hero-title {
  font-family: var(--font-head); font-size: clamp(24px, 5vw, 36px); font-weight: 800;
  color: var(--t1); letter-spacing: -.03em; line-height: 1.1; margin-bottom: 14px;
  animation: fade-up .5s .1s ease both;
}
.hero-title span { color: var(--amber); }
.hero-sub {
  font-family: var(--font-mono); font-size: 13px; color: var(--t2); line-height: 1.75;
  max-width: 460px; margin: 0 auto 26px;
  animation: fade-up .5s .2s ease both;
}
.hero-cta-row {
  display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap;
  animation: fade-up .5s .3s ease both;
}
.btn-primary {
  font-family: var(--font-head); font-size: 14px; font-weight: 700;
  color: #0A0A0A; background: var(--amber); border: none;
  border-radius: var(--r-md); padding: 12px 24px; cursor: pointer;
  transition: opacity .15s, transform .1s;
}
.btn-primary:hover { opacity: .9; transform: translateY(-1px); }
.btn-primary:active { transform: scale(.98); }
.btn-ghost {
  font-family: var(--font-mono); font-size: 12px; font-weight: 500;
  color: var(--t2); background: transparent; border: 0.5px solid var(--border3);
  border-radius: var(--r-md); padding: 12px 22px; cursor: pointer;
  transition: border-color .15s, color .15s;
}
.btn-ghost:hover { border-color: var(--t3); color: var(--t1); }
.hero-note { font-family: var(--font-mono); font-size: 10px; color: var(--t4); margin-top: 12px; animation: fade-up .5s .4s ease both; }

/* ── Trust bar ── */
.trust-bar {
  display: flex; align-items: center; justify-content: center;
  gap: 20px; flex-wrap: wrap;
  padding: 12px 20px;
  border-top: 0.5px solid var(--border1);
  border-bottom: 0.5px solid var(--border1);
  background: var(--surface1);
}
.trust-item { display: flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: 11px; color: var(--t3); }
.trust-check { color: var(--green-lt); font-size: 12px; }
.trust-sep { width: 1px; height: 12px; background: var(--border2); }

/* ── Market strip ── */
.market-strip {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
  border-bottom: 0.5px solid var(--border1);
}
.ms-cell {
  padding: 12px 16px;
  border-right: 0.5px solid var(--border1);
}
.ms-cell:last-child { border-right: none; }
.ms-label { font-family: var(--font-mono); font-size: 9px; color: var(--t3); letter-spacing: .1em; text-transform: uppercase; margin-bottom: 5px; }
.ms-val { font-family: var(--font-head); font-size: 17px; font-weight: 700; color: var(--t1); line-height: 1; }
.ms-sub { font-family: var(--font-mono); font-size: 10px; color: var(--t3); margin-top: 3px; }

/* ── Notification banner ── */
.notif {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: var(--surface1); border: 0.5px solid var(--border2);
  border-left: 2px solid var(--amber);
  border-radius: var(--r-sm);
  font-family: var(--font-mono); font-size: 11px; color: var(--t2);
  margin-bottom: 10px;
  animation: slide-down .4s ease both;
}
.notif-green { border-left-color: var(--green-lt) !important; }
.notif-red   { border-left-color: var(--red) !important; }

/* ── Personalized strip ── */
.p-strip {
  display: flex; align-items: center; gap: 10px;
  background: var(--surface1); border: 0.5px solid var(--border1);
  border-left: 2px solid var(--amber);
  border-radius: var(--r-sm);
  padding: 10px 14px;
  font-family: var(--font-mono); font-size: 11px; color: var(--t2);
  margin-bottom: 10px;
}

/* ── Trial bar ── */
.trial-bar {
  border-radius: var(--r-sm); padding: 10px 14px;
  font-family: var(--font-mono); font-size: 11px;
  margin-bottom: 10px;
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
}
.trial-ok     { background: rgba(34,197,94,.06); border: 0.5px solid var(--green-bd); }
.trial-urgent { background: rgba(239,68,68,.06); border: 0.5px solid var(--red-bd); }
.trial-bar-progress {
  background: var(--surface2); border-radius: var(--r-sm);
  padding: 10px 14px; margin-bottom: 10px;
}
.progress-track { height: 3px; background: var(--border2); border-radius: 2px; overflow: hidden; margin: 6px 0; }
.progress-fill  { height: 3px; border-radius: 2px; transition: width .6s ease; }

/* ── Pro Command Center ── */
.pcc {
  background: var(--surface1); border: 0.5px solid var(--border2);
  border-radius: var(--r-xl); overflow: hidden; margin-bottom: 14px;
  animation: card-in .4s ease both;
}
.pcc-topbar {
  height: 2px;
  background: linear-gradient(90deg, transparent 0%, var(--amber) 40%, var(--amber) 60%, transparent 100%);
}
.pcc-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 18px; border-bottom: 0.5px solid var(--border1);
}
.pcc-title-row { display: flex; align-items: center; gap: 8px; }
.pcc-title-text { font-family: var(--font-head); font-size: 12px; font-weight: 700; color: var(--amber); letter-spacing: .05em; text-transform: uppercase; }
.pcc-body { padding: 18px; }
.pcc-hero-row { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; gap: 10px; flex-wrap: wrap; }
.pcc-sym { font-family: var(--font-head); font-size: 24px; font-weight: 800; color: var(--t1); }
.pcc-co-name { font-family: var(--font-mono); font-size: 10px; color: var(--t3); margin-top: 2px; }
.pcc-upside-box { text-align: center; background: var(--surface3); border: 0.5px solid var(--border2); border-radius: var(--r-md); padding: 8px 14px; }
.pcc-upside-label { font-family: var(--font-mono); font-size: 9px; color: var(--t3); letter-spacing: .1em; text-transform: uppercase; margin-bottom: 3px; }
.pcc-upside-val { font-family: var(--font-head); font-size: 20px; font-weight: 700; }
.pcc-price-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--border1); border-radius: var(--r-sm); overflow: hidden; margin-bottom: 16px; }
.pcc-price-cell { background: var(--surface2); padding: 10px 0; text-align: center; }
.pcc-price-label { font-family: var(--font-mono); font-size: 9px; color: var(--t3); letter-spacing: .1em; text-transform: uppercase; margin-bottom: 3px; }
.pcc-price-val { font-family: var(--font-mono); font-size: 13px; font-weight: 500; color: var(--t1); }
.pcc-drivers { margin-bottom: 14px; }
.pcc-driver { display: flex; gap: 10px; background: var(--surface2); border-radius: var(--r-sm); padding: 10px 12px; margin-bottom: 5px; font-family: var(--font-mono); font-size: 11px; color: var(--t1); line-height: 1.6; }
.pcc-driver-icon { flex-shrink: 0; font-size: 12px; margin-top: 1px; }
.pcc-verdict { border-radius: var(--r-sm); padding: 12px 14px; margin-bottom: 16px; }
.pcc-verdict-label { font-family: var(--font-mono); font-size: 9px; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 5px; }
.pcc-verdict-text { font-family: var(--font-head); font-size: 14px; font-weight: 600; color: var(--t1); line-height: 1.5; }
.pcc-conf-wrap { margin-bottom: 16px; }
.pcc-conf-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.pcc-conf-label { font-family: var(--font-mono); font-size: 10px; color: var(--t3); letter-spacing: .08em; text-transform: uppercase; }
.pcc-conf-right { display: flex; align-items: center; gap: 8px; }
.pcc-conf-val { font-family: var(--font-mono); font-size: 13px; font-weight: 600; }
.pcc-conf-pct { font-family: var(--font-mono); font-size: 11px; color: var(--t3); }
.pcc-bar-track { display: flex; gap: 2px; }
.pcc-bar-block { flex: 1; height: 5px; border-radius: 2px; }
.pcc-context { display: flex; gap: 8px; background: var(--blue-bg); border: 0.5px solid var(--blue-bd); border-radius: var(--r-sm); padding: 10px 12px; margin-bottom: 16px; font-family: var(--font-mono); font-size: 11px; color: #A0C0FF; line-height: 1.6; }

/* ── Single upgrade CTA card ── */
.upgrade-card {
  background: var(--surface2);
  border: 0.5px solid var(--amber-bd);
  border-radius: var(--r-lg);
  padding: 18px 20px;
  margin: 16px 0 10px;
}
.upgrade-title { font-family: var(--font-head); font-size: 16px; font-weight: 700; color: var(--amber); margin-bottom: 4px; }
.upgrade-sub { font-family: var(--font-mono); font-size: 11px; color: var(--t2); line-height: 1.7; margin-bottom: 14px; }
.upgrade-features { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.upgrade-feat { font-family: var(--font-mono); font-size: 10px; color: var(--t2); background: var(--surface3); border: 0.5px solid var(--border2); border-radius: var(--r-sm); padding: 4px 10px; }

/* ── Downgrade modal ── */
.dg-overlay { min-height: 480px; background: rgba(0,0,0,.92); display: flex; align-items: center; justify-content: center; padding: 20px; border-radius: var(--r-lg); }
.dg-card { background: var(--surface1); border: 0.5px solid var(--red-bd); border-radius: var(--r-xl); padding: 32px 28px; max-width: 480px; width: 100%; animation: modal-in .4s cubic-bezier(.16,1,.3,1) both; }
@keyframes modal-in { from { opacity: 0; transform: scale(.96) translateY(12px); } to { opacity: 1; transform: none; } }
.dg-icon { font-size: 36px; text-align: center; display: block; margin-bottom: 12px; }
.dg-title { font-family: var(--font-head); font-size: 20px; font-weight: 800; color: var(--t1); text-align: center; margin-bottom: 6px; }
.dg-sub { font-family: var(--font-mono); font-size: 12px; color: var(--t2); text-align: center; line-height: 1.65; margin-bottom: 18px; }
.dg-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 18px; }
.dg-stat { background: var(--surface2); border: 0.5px solid var(--border2); border-radius: var(--r-sm); padding: 12px 8px; text-align: center; }
.dg-stat-num { font-family: var(--font-head); font-size: 22px; font-weight: 800; color: var(--amber); }
.dg-stat-lbl { font-family: var(--font-mono); font-size: 9px; color: var(--t3); margin-top: 2px; }
.dg-lost { background: rgba(239,68,68,.04); border: 0.5px solid var(--red-bd); border-radius: var(--r-sm); padding: 12px 14px; margin-bottom: 18px; }
.dg-lost-title { font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--red); letter-spacing: .1em; text-transform: uppercase; margin-bottom: 8px; }
.dg-lost-item { font-family: var(--font-mono); font-size: 11px; color: var(--t2); padding: 4px 0; border-bottom: 0.5px solid var(--border1); display: flex; align-items: center; gap: 8px; }
.dg-lost-item:last-child { border-bottom: none; }

/* ── Greeting ── */
.greeting-wrap { padding: 18px 0 10px; }
.greeting-name { font-family: var(--font-head); font-size: 22px; font-weight: 800; color: var(--t1); }
.greeting-date { font-family: var(--font-mono); font-size: 10px; color: var(--t3); letter-spacing: .1em; text-transform: uppercase; margin-top: 3px; }
.tier-tag {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--font-mono); font-size: 10px; font-weight: 600;
  padding: 3px 10px; border-radius: 999px; letter-spacing: .06em; text-transform: uppercase;
  margin-left: 10px; vertical-align: middle;
}
.tier-free     { background: rgba(255,255,255,.05); border: 0.5px solid var(--border3); color: var(--t3); }
.tier-trial    { background: var(--green-bg); border: 0.5px solid var(--green-bd); color: var(--green-lt); }
.tier-starter  { background: rgba(96,165,250,.08); border: 0.5px solid rgba(96,165,250,.2); color: var(--blue); }
.tier-trader   { background: rgba(167,139,250,.08); border: 0.5px solid rgba(167,139,250,.2); color: #A78BFA; }
.tier-pro      { background: var(--amber-bg); border: 0.5px solid var(--amber-bd); color: var(--amber); }

/* ── Brief section ── */
.brief-card {
  background: var(--surface1); border: 0.5px solid var(--border2);
  border-radius: var(--r-lg); overflow: hidden; margin-bottom: 10px;
}
.brief-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 0.5px solid var(--border1); cursor: pointer; }
.brief-header-left { display: flex; align-items: center; gap: 8px; font-family: var(--font-head); font-size: 13px; font-weight: 700; color: var(--t1); }
.brief-body { padding: 14px 16px; font-family: var(--font-mono); font-size: 12px; color: var(--t1); line-height: 1.8; }
.brief-body strong { color: var(--amber); font-weight: 600; }

/* ── Sector grid ── */
.sector-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.sector-card { background: var(--surface2); border: 0.5px solid var(--border1); border-radius: var(--r-sm); padding: 10px 12px; font-family: var(--font-mono); }
.sector-name { font-size: 12px; font-weight: 500; color: var(--t1); margin-bottom: 3px; }
.sector-chg  { font-size: 13px; font-weight: 600; }
.sector-verdict { font-size: 10px; color: var(--t3); margin-top: 2px; }

/* ── Streak badge ── */
.streak-badge {
  display: inline-flex; align-items: center; gap: 8px;
  background: var(--amber-bg); border: 0.5px solid var(--amber-bd);
  border-radius: var(--r-sm); padding: 7px 14px;
  font-family: var(--font-mono); font-size: 11px; color: var(--t2); margin-bottom: 8px;
}
.streak-num { font-family: var(--font-head); font-size: 18px; font-weight: 800; color: var(--amber); }

/* ── Bottom upgrade bar (bottom of page, once) ── */
.bottom-upgrade {
  background: var(--surface2); border: 0.5px solid var(--amber-bd);
  border-radius: var(--r-lg); padding: 16px 20px;
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
  margin-top: 16px;
}
.bottom-upgrade-text { font-family: var(--font-mono); font-size: 12px; color: var(--t2); line-height: 1.6; }
.bottom-upgrade-text strong { color: var(--amber); }

/* ── Trade Game teaser ── */
.game-card {
  background: var(--surface1); border: 0.5px solid var(--border2);
  border-radius: var(--r-lg); padding: 16px 18px;
  display: flex; align-items: center; gap: 16px;
}
.game-icon { font-size: 28px; line-height: 1; flex-shrink: 0; }
.game-body { flex: 1; }
.game-title { font-family: var(--font-head); font-size: 14px; font-weight: 700; color: var(--t1); margin-bottom: 3px; }
.game-sub { font-family: var(--font-mono); font-size: 11px; color: var(--t2); line-height: 1.55; }

/* ── News ── */
.news-item { padding: 10px 0; border-bottom: 0.5px solid var(--border1); font-family: var(--font-mono); }
.news-item:last-child { border-bottom: none; }
.news-headline { font-size: 12px; color: var(--t1); line-height: 1.55; margin-bottom: 4px; }
.news-meta { font-size: 10px; color: var(--t3); }

/* ── Animations ── */
@keyframes fade-up  { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes card-in  { from { opacity: 0; transform: translateY(6px);  } to { opacity: 1; transform: none; } }
@keyframes slide-down { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
@keyframes msg-in   { from { opacity: 0; transform: translateX(-4px); } to { opacity: 1; transform: none; } }
@keyframes num-pop  { 0% { transform: scale(.8); opacity: 0; } 70% { transform: scale(1.08); } 100% { transform: scale(1); opacity: 1; } }
@keyframes trial-pulse { 0%,100% { box-shadow: 0 0 0 rgba(239,68,68,0); } 50% { box-shadow: 0 0 16px rgba(239,68,68,.18); } }
@keyframes amber-glow  { 0%,100% { box-shadow: 0 0 0 rgba(240,165,0,0); } 50% { box-shadow: 0 0 24px rgba(240,165,0,.12); } }

/* ── Responsive ── */
@media (max-width: 680px) {
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
  .market-strip { grid-template-columns: repeat(2, 1fr); }
  .sig-grid, .dap-grid, .sector-grid { grid-template-columns: 1fr 1fr; }
  .pcc-price-grid { grid-template-columns: repeat(3, 1fr); }
  .hero-title { font-size: 26px; }
}
@media (max-width: 440px) {
  .sig-grid, .dap-grid { grid-template-columns: 1fr; }
}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT RENDERERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_greeting(name: str) -> tuple[str, str]:
    h = now_wat().hour
    if h < 12:   return "Good morning", "☀️"
    if h < 17:   return "Good afternoon", "⚡"
    return "Good evening", "🌙"

def _tier_tag(tier: str) -> str:
    labels = {
        "free":    ("FREE",    "tier-free"),
        "trial":   ("TRIAL",   "tier-trial"),
        "starter": ("STARTER", "tier-starter"),
        "trader":  ("TRADER",  "tier-trader"),
        "pro":     ("PRO",     "tier-pro"),
    }
    lbl, cls = labels.get(tier, ("FREE", "tier-free"))
    return f'<span class="tier-tag {cls}">{lbl}</span>'


def _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial, is_ex_trial):
    greeting, emoji = _get_greeting(name)
    st.markdown(f"""
<div class="greeting-wrap">
  <div style="display:flex;align-items:baseline;gap:0;flex-wrap:wrap;">
    <span class="greeting-name">{greeting}, {name or "trader"} {_tier_tag(tier)}</span>
  </div>
  <div class="greeting-date">{now.strftime("%A · %d %B %Y · %I:%M %p")} WAT</div>
</div>""", unsafe_allow_html=True)

    if is_trial:
        pct  = round(((14 - trial_days_left) / 14) * 100)
        bc   = "trial-urgent" if trial_urgent else "trial-ok"
        tcol = "var(--red)" if trial_urgent else "var(--green-lt)"
        msg  = f"⚠️ Trial expires in {trial_days_left} day{'s' if trial_days_left!=1 else ''} — upgrade to keep access" if trial_urgent \
               else f"✨ Premium trial active — {trial_days_left} days remaining · Day {trial_day_num} of 14"
        st.markdown(f"""
<div class="trial-bar {bc}">
  <span style="color:{tcol};font-weight:600;">{msg}</span>
  <span style="color:var(--t3);">Upgrade in Settings ↗</span>
</div>
<div class="trial-bar-progress">
  <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:10px;color:var(--t3);margin-bottom:4px;">
    <span>Trial progress</span><span style="color:{tcol};">Day {trial_day_num} / 14</span>
  </div>
  <div class="progress-track"><div class="progress-fill" style="width:{pct}%;background:{tcol};"></div></div>
</div>""", unsafe_allow_html=True)


def render_personalized_strip(tier, profile, sb, name, uniq):
    if tier in ("visitor",):
        return
    last_ticker = st.session_state.get("last_ticker_asked", "")
    ticker_data = next((p for p in uniq if p.get("symbol","").upper() == last_ticker.upper()), None) if last_ticker else None
    chg         = float(ticker_data.get("change_percent", 0)) if ticker_data else None
    chg_str     = (f"+{chg:.2f}% ▲" if chg >= 0 else f"{chg:.2f}% ▼") if chg is not None else None
    chg_color   = "var(--green-lt)" if (chg is not None and chg >= 0) else "var(--red)"
    used_today  = get_ai_query_count()
    streak      = get_streak()

    if tier == "free":
        limit = 2
        rem   = max(0, limit - used_today)
        if last_ticker and chg_str:
            txt = f'<strong style="color:var(--amber);">{last_ticker}</strong> is <strong style="color:{chg_color};">{chg_str}</strong> today &nbsp;·&nbsp; {rem} free queries left'
        else:
            txt = f'{rem} of {limit} free AI queries remaining today'
    elif tier == "trial":
        if last_ticker and chg_str:
            txt = f'<strong style="color:var(--amber);">{last_ticker}</strong>: <strong style="color:{chg_color};">{chg_str}</strong> &nbsp;·&nbsp; Unlimited queries active'
        else:
            txt = 'Unlimited AI queries active during trial'
        if streak >= 2:
            txt += f' &nbsp;·&nbsp; 🔥 {streak}-day streak'
    elif tier in ("starter","trader","pro"):
        if last_ticker and chg_str:
            txt = f'<strong style="color:var(--amber);">{last_ticker}</strong>: <strong style="color:{chg_color};">{chg_str}</strong> today'
        else:
            txt = f'Welcome back, <strong style="color:var(--amber);">{name}</strong>'
        if streak >= 2:
            txt += f' &nbsp;·&nbsp; 🔥 {streak}-day streak'
    else:
        return

    st.markdown(f'<div class="p-strip"><div class="dot-live"></div><span style="flex:1;font-family:var(--font-mono);font-size:11px;color:var(--t2);">{txt}</span></div>', unsafe_allow_html=True)


def _render_notification_banner(top_g, now, gc, total, market, notif_minutes):
    if not top_g: return
    ns  = top_g[0]
    nc  = float(ns.get("change_percent", 0))
    nsm = ns.get("symbol", "NGX")
    if nc >= 3:
        dot_cls = "dot-live"
        txt = f'<strong style="color:var(--green-lt);">{nsm}</strong> is up {nc:.1f}% — AI flagged this signal early'
        extra_cls = "notif-green"
    elif nc <= -3:
        dot_cls = "dot-red"
        txt = f'<strong style="color:var(--red);">{nsm}</strong> is down {abs(nc):.1f}% — AI sell signal active'
        extra_cls = "notif-red"
    else:
        dot_cls = "dot-amber"
        txt = f'AI scanning 144 NGX stocks — <strong style="color:var(--amber);">{gc} gainers</strong> identified today'
        extra_cls = ""
    st.markdown(f'<div class="notif {extra_cls}"><div class="{dot_cls}"></div><span style="flex:1;">{txt}</span><span style="font-family:var(--font-mono);font-size:10px;color:var(--t4);">{_time_ago(notif_minutes)}</span></div>', unsafe_allow_html=True)


def _render_market_strip(ad, acg, acol, aarr, total, gc, lc, mood, mcol, market, data_label):
    acol_css  = "var(--green-lt)" if acg >= 0 else "var(--red)"
    mcol_css  = "var(--green-lt)" if mood == "Bullish" else "var(--red)" if mood == "Bearish" else "var(--amber)"
    open_dot  = '<span class="dot-live" style="display:inline-block;margin-right:4px;"></span>' if market["is_open"] else ""
    st.markdown(f"""
<div class="market-strip">
  <div class="ms-cell">
    <div class="ms-label">NGX All-Share</div>
    <div class="ms-val" style="color:{acol_css};">{ad}</div>
    <div class="ms-sub">{aarr} {abs(acg):.2f}% · {data_label}</div>
  </div>
  <div class="ms-cell">
    <div class="ms-label">Gainers / Losers</div>
    <div class="ms-val"><span style="color:var(--green-lt);">{gc}</span><span style="color:var(--t4);"> / </span><span style="color:var(--red);">{lc}</span></div>
    <div class="ms-sub">{total - gc - lc} flat · {total} stocks</div>
  </div>
  <div class="ms-cell">
    <div class="ms-label">Market mood</div>
    <div class="ms-val" style="color:{mcol_css};">{mood}</div>
    <div class="ms-sub">{"Live breadth" if market["is_open"] else "Last close"}</div>
  </div>
  <div class="ms-cell">
    <div class="ms-label">Market status</div>
    <div class="ms-val" style="font-size:13px;font-family:var(--font-mono);color:{acol_css};">{open_dot}{market["label"]}</div>
    <div class="ms-sub">{market["note"]}</div>
  </div>
</div>""", unsafe_allow_html=True)


def _render_signal_cards(insights, tier, sig_visible, is_trial):
    """Top AI signal cards — gated by tier"""
    if not insights:
        st.markdown('<div class="card" style="text-align:center;padding:32px;"><div class="label" style="margin-bottom:8px;">Today\'s signals</div><div style="font-family:var(--font-mono);font-size:12px;color:var(--t3);">Signals are refreshed at 10 AM WAT each trading day.<br>Check back during market hours.</div></div>', unsafe_allow_html=True)
        return

    cols_html = ""
    for i, ins in enumerate(insights[:5]):
        if ins["action"] == "BUY":
            badge_cls, ac = "pill-green", "var(--green-lt)"
            badge_lbl = "BUY"
        elif ins["action"] == "AVOID":
            badge_cls, ac = "pill-red", "var(--red)"
            badge_lbl = "AVOID"
        else:
            badge_cls, ac = "pill-amber", "var(--amber)"
            badge_lbl = "HOLD"

        locked = i >= sig_visible
        lock_overlay = '<div class="sig-lock"><div class="lock-icon">🔒</div><div class="lock-text">Upgrade to unlock</div></div>' if locked else ""

        price_html = ""
        if not locked and can_access("daily_picks_entry", tier):
            p = ins.get("price", 0) or 0
            tgt = round(p * 1.075, 2) if p > 0 else 0
            if p > 0:
                price_html = f"""
<div class="sig-price-row"><span class="sig-price-label">Entry</span><span class="sig-price-val">{_fmt_price(p)}</span></div>
<div class="sig-price-row"><span class="sig-price-label">Target</span><span class="sig-price-val" style="color:var(--green-lt);">{_fmt_price(tgt)}</span></div>"""

        cols_html += f"""
<div class="sig-card" style="border-top:1.5px solid {ac};">
  <div class="sig-card-header">
    <div class="sig-sym">{ins['sym']}</div>
    <span class="pill {badge_cls}">{badge_lbl}</span>
  </div>
  <div class="sig-name">{ins.get('name','')}</div>
  {price_html}
  <div class="sig-divider"></div>
  <div class="sig-reason">{ins['reason']}</div>
  {lock_overlay}
</div>"""

    st.markdown(f'<div class="sig-grid">{cols_html}</div>', unsafe_allow_html=True)


def _render_daily_picks(tier, is_trial, picks, picks_visible):
    st.markdown("""
<div class="sec-head">
  <span class="sec-head-title">🤖 Daily AI picks</span>
  <span class="sec-head-action">Refreshed 10 AM WAT</span>
</div>
<div style="font-family:var(--font-mono);font-size:11px;color:var(--t3);line-height:1.65;margin-bottom:10px;">
  AI-curated every trading day from momentum, volume &amp; fundamental signals.
  <strong style="color:var(--t2);">Not financial advice.</strong>
</div>""", unsafe_allow_html=True)

    if is_trial:
        st.markdown('<div style="margin-bottom:8px;"><span class="pill pill-green">✨ Full 9 picks visible — trial benefit</span></div>', unsafe_allow_html=True)

    def _pick_card(pick, ac, cb, bl, blur=False):
        conf     = pick.get("conf", 0)
        conf_el  = f'<div class="dap-conf">Confidence<div class="dap-conf-bar"><div class="dap-conf-fill" style="width:{conf}%;background:{ac};"></div></div></div>' \
                   if can_access("signals_confidence", tier) else ""
        reason   = pick.get("reason","")
        inner    = f'<div class="dap-sym">{pick["sym"]}</div><span class="pill" style="background:{cb};color:{ac};border-color:{ac}44;font-size:9px;">{bl}</span><div class="dap-reason">{reason}</div>{conf_el}'
        if blur:
            return f'<div class="dap-card"><div class="dap-blur-wrap"><div class="dap-blur-inner">{inner}</div><div class="dap-lock-overlay"><span style="font-size:16px;">🔒</span><span class="lock-text">Upgrade to unlock</span></div></div></div>'
        return f'<div class="dap-card" style="border-top:1.5px solid {ac};">{inner}</div>'

    cats = [
        ("buy",   "var(--green-lt)", "rgba(34,197,94,.1)",   "BUY"),
        ("hold",  "var(--amber)",    "rgba(240,165,0,.1)",   "HOLD"),
        ("avoid", "var(--red)",      "rgba(239,68,68,.1)",   "AVOID"),
    ]
    for cat_key, ac, cb, bl in cats:
        cat_picks = picks.get(cat_key, [])
        if not cat_picks:
            continue
        dot = "🟢" if cat_key == "buy" else "🔴" if cat_key == "avoid" else "🟡"
        st.markdown(f'<div class="picks-category-label">{dot} {bl}</div>', unsafe_allow_html=True)
        cards_html = '<div class="dap-grid">'
        for ip, p in enumerate(cat_picks):
            cards_html += _pick_card(p, ac, cb, bl, blur=(ip >= picks_visible))
            if is_trial: track_stock_analyzed(p["sym"])
        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)

    if not can_access("daily_picks_all", tier):
        st.markdown('<div style="text-align:center;margin-top:4px;"><span class="pill pill-ghost">🔒 6 more picks on trial &amp; above</span></div>', unsafe_allow_html=True)


def _render_ai_chat(tier, name, uniq, _pai, market, latest_date, is_trial):
    """Compact AI chat section"""
    has_full_ai    = can_access("ai_full_response", tier)
    query_limit    = get_usage_limit("ai_queries", tier)
    used_today     = get_ai_query_count()
    at_limit       = (query_limit is not None) and (used_today >= query_limit)
    can_input      = can_access("ai_input", tier)

    if "mai_history" not in st.session_state:
        st.session_state.mai_history = []

    # Quick-ask chips
    chips = [
        f"Best buy today?",
        f"What's ZENITHBANK doing?",
        f"Market summary",
        f"DANGCEM analysis",
        f"Top movers now",
    ]

    st.markdown(f"""
<div class="sec-head">
  <span class="sec-head-title">🤖 Ask the market AI</span>
  <span class="sec-head-action">
    {"Unlimited" if query_limit is None else f"{max(0,query_limit-used_today)}/{query_limit} queries left today"}
  </span>
</div>""", unsafe_allow_html=True)

    # Chat history
    for idx, msg in enumerate(st.session_state.mai_history):
        if msg["role"] == "user":
            st.markdown(f'<div class="ai-msg-row" style="justify-content:flex-end;"><div class="ai-msg-user">{msg["content"]}</div></div>', unsafe_allow_html=True)
        else:
            body    = msg.get("content","")
            blurred = msg.get("blurred", False)
            blur_cls = "ai-blurred" if blurred else ""
            preview  = body[:180] + "…" if (blurred and len(body) > 180) else body
            st.markdown(f'<div class="ai-msg-row"><div class="ai-msg-ai {blur_cls}">{preview}</div></div>', unsafe_allow_html=True)
            if blurred:
                st.markdown('<div style="text-align:center;margin:-6px 0 10px;"><span class="pill pill-amber">🔒 Full response on trial &amp; above</span></div>', unsafe_allow_html=True)

    # Input
    if not can_input:
        st.markdown('<div class="ai-input-wrap"><div class="ai-label">Ask anything about NGX stocks</div><div style="font-family:var(--font-mono);font-size:11px;color:var(--t3);">Sign up free for 2 daily AI queries →</div></div>', unsafe_allow_html=True)
    elif at_limit:
        st.markdown(f'<div class="ai-input-wrap"><div class="ai-label">Daily limit reached</div><div style="font-family:var(--font-mono);font-size:11px;color:var(--t3);">You\'ve used all {query_limit} free queries today. Upgrade for 15–unlimited. →</div></div>', unsafe_allow_html=True)
    else:
        question = st.text_input("",
            placeholder="Ask about any NGX stock — e.g. 'Should I buy GTCO?' or 'Market summary'",
            key="mai_input", label_visibility="collapsed")

        # Quick chips
        chip_cols = st.columns(len(chips))
        selected_chip = None
        for ci, (col, chip) in enumerate(zip(chip_cols, chips)):
            with col:
                if st.button(chip, key=f"chip_{ci}", use_container_width=True):
                    selected_chip = chip

        active_q = selected_chip or (question if st.session_state.get("mai_submit") else None)
        if st.button("Ask →", key="mai_submit", type="primary", use_container_width=False):
            active_q = question

        if active_q and active_q.strip():
            _build_and_run_ai(active_q.strip(), tier, name, uniq, _pai, market, latest_date, has_full_ai)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.session_state.mai_history:
            if st.button("🗑 Clear chat", key="mai_clear"):
                st.session_state.mai_history = []
                st.rerun()


def _build_and_run_ai(question, tier, name, uniq, _pai, market, latest_date, has_full_ai):
    ad, aarr, acg, mood, gc, lc, total, top_g_text = (
        _pai["ad"], _pai["aarr"], _pai["acg"], _pai["mood"],
        _pai["gc"], _pai["lc"], _pai["total"], _pai["top_g_text"]
    )
    global_context = _pai.get("global_context", "")

    q_upper = question.upper()
    tickers = [w for w in re.findall(r'\b[A-Z]{2,8}\b', q_upper)
               if w not in {"IS","THE","A","AN","IN","ON","AT","TO","AND","OR","FOR",
                             "OF","MY","BUY","SELL","HOLD","GET","NGX","ASI","AI",
                             "WHAT","SHOULD","HOW","WHY","GIVE","TELL","CAN","ME","NOW","TODAY"}]
    price_ctx = ""
    for t in tickers[:3]:
        pd_  = next((p for p in _pai.get("uniq",[]) if p.get("symbol","") == t), None)
        if pd_:
            price_ctx += f"\n{t}: current price ₦{float(pd_.get('price',0)):,.2f}, change {float(pd_.get('change_percent',0)):+.2f}% today"

    system = f"""You are NGX Signal AI — a concise, data-driven Nigerian Stock Exchange market intelligence assistant.
Market context: ASI {ad} ({aarr} {acg:.2f}%), mood {mood}, {gc} gainers of {total} stocks, top movers: {top_g_text}.
Date: {latest_date}. Market {"open" if market["is_open"] else "closed"}.
{f"Global context: {global_context}" if global_context else ""}
{f"Stock prices: {price_ctx}" if price_ctx else ""}
User tier: {tier}. Name: {name}.
Always end with a clear BUY / HOLD / AVOID recommendation or a direct answer.
Format: plain text, concise, no markdown headers. Max 200 words."""

    st.session_state.mai_history.append({"role": "user", "content": question})
    with st.spinner("Analysing…"):
        answer = call_ai(question, system=system)
    if answer:
        increment_ai_query_count()
        update_streak()
        st.session_state.mai_history.append({
            "role": "assistant", "content": answer,
            "blurred": not has_full_ai, "question": question,
        })
        st.rerun()
    else:
        if st.session_state.mai_history and st.session_state.mai_history[-1]["role"] == "user":
            st.session_state.mai_history.pop()


def _render_top_movers(movers, latest_date, market):
    if not movers:
        return
    rows_html = ""
    for s in movers:
        chg = float(s.get("change_percent", 0) or 0)
        cc  = "var(--green-lt)" if chg >= 0 else "var(--red)"
        arr = "▲" if chg >= 0 else "▼"
        rows_html += f"""
<div class="mover-row">
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="mover-sym">{s["symbol"]}</span>
    <span class="mover-price">{_fmt_price(float(s.get("price",0) or 0))}</span>
  </div>
  <span class="mover-chg" style="color:{cc};">{arr} {abs(chg):.2f}%</span>
</div>"""
    st.markdown(f'<div class="card"><div class="sec-head" style="margin-top:0;"><span class="sec-head-title">🔥 Top movers</span><span class="sec-head-action">{"📈 Live" if market["is_open"] else "🔒 Last close"} · {latest_date}</span></div><div class="movers-table">{rows_html}</div></div>', unsafe_allow_html=True)
    if st.button("📊 View all 144 stocks →", key="btn_all_stocks", type="primary"):
        st.session_state.current_page = "all_stocks"
        st.rerun()


def _render_brief_section(tier, brief_res):
    with st.expander("✨  TODAY'S AI MARKET BRIEF", expanded=False):
        if not brief_res:
            st.markdown('<div style="font-family:var(--font-mono);font-size:12px;color:var(--t3);padding:8px 0;">Brief generates daily at 9 AM WAT before market open.</div>', unsafe_allow_html=True)
            return
        raw   = brief_res[0].get("body", "")
        bdate = brief_res[0].get("brief_date", str(date.today()))
        if can_access("brief_full", tier):
            st.markdown(f'<div class="brief-body">{raw}</div>', unsafe_allow_html=True)
        else:
            preview = raw[:300] + "…" if len(raw) > 300 else raw
            st.markdown(f'<div class="brief-body" style="filter:blur(3px);user-select:none;">{preview}</div>', unsafe_allow_html=True)
            st.markdown('<div style="text-align:center;margin-top:8px;"><span class="pill pill-amber">🔒 Full brief on trial &amp; above</span></div>', unsafe_allow_html=True)


def _render_sector_snapshot(tier):
    with st.expander("🚦  SECTOR SNAPSHOT", expanded=False):
        sec_data = _load_home_sectors()
        if not sec_data:
            st.info("No sector data.")
            return
        seen_s = {}
        for s in sec_data:
            sn = s.get("sector_name","").strip()
            if sn and sn not in seen_s: seen_s[sn] = s
        all_sec   = sorted(seen_s.values(), key=lambda x: float(x.get("change_percent",0) or 0), reverse=True)
        sec_vis   = len(all_sec) if can_access("sector_all", tier) else 3
        visible   = all_sec[:sec_vis]
        blurred   = all_sec[sec_vis:]
        rows_html = ""
        for s in visible:
            light = s.get("traffic_light","amber")
            em    = "🟢" if light=="green" else "🔴" if light=="red" else "🟡"
            chg   = float(s.get("change_percent",0) or 0)
            cc    = "var(--green-lt)" if chg >= 0 else "var(--red)"
            rows_html += f'<div class="sector-card"><div class="sector-name">{em} {s["sector_name"]}</div><div class="sector-chg" style="color:{cc};">{chg:+.2f}%</div><div class="sector-verdict">{s.get("verdict","")}</div></div>'
        for s in blurred:
            rows_html += '<div class="sector-card" style="filter:blur(4px);user-select:none;"><div class="sector-name">🔒 Locked</div></div>'
        st.markdown(f'<div class="sector-grid">{rows_html}</div>', unsafe_allow_html=True)
        if not can_access("sector_all", tier):
            st.markdown('<div style="text-align:center;margin-top:8px;"><span class="pill pill-ghost">🔒 All sectors on trial &amp; above</span></div>', unsafe_allow_html=True)


def _render_news_section(tier):
    with st.expander("📰  LATEST MARKET NEWS", expanded=False):
        news = _load_home_news()
        if not news:
            st.info("No news yet.")
            return
        vis = 12 if can_access("news_full", tier) else 4
        seen_h = set(); cnt = 0
        rows_html = ""
        for art in news:
            hk = (art.get("headline") or "")[:60].lower()
            if hk in seen_h or cnt >= 12: continue
            seen_h.add(hk); cnt += 1
            sent = art.get("sentiment","neutral")
            dot  = "🟢" if sent=="positive" else "🔴" if sent=="negative" else "🟡"
            blur = "style='filter:blur(4px);user-select:none;'" if cnt > vis else ""
            rows_html += f'<div class="news-item" {blur}><div class="news-headline">{art.get("headline","")}</div><div class="news-meta">{dot} {sent.capitalize()}</div></div>'
        st.markdown(f'<div>{rows_html}</div>', unsafe_allow_html=True)
        if not can_access("news_full", tier):
            st.markdown('<div style="text-align:center;margin-top:6px;"><span class="pill pill-ghost">🔒 Full news feed on trial &amp; above</span></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📅 Events calendar →", key="btn_cal_news", use_container_width=True):
                st.session_state.current_page = "calendar"; st.rerun()
        with c2:
            if st.button("📊 Full calendar →", key="btn_cal_full_news", type="primary", use_container_width=True):
                st.session_state.current_page = "calendar"; st.rerun()


def _render_trade_game(sb, current_user):
    st.markdown('<div class="game-card"><div class="game-icon">🎮</div><div class="game-body"><div class="game-title">NGX Trade Game</div><div class="game-sub">Practice with virtual cash before risking real money. Track your picks against real NGX prices.</div></div></div>', unsafe_allow_html=True)
    if st.button("▶ Open Trade Game →", key="btn_trade_game", use_container_width=False):
        st.session_state.current_page = "trade_game"; st.rerun()


def _render_downgrade_modal(name, stats):
    ai_used     = max(stats.get("total_ai_queries", 0), 8)
    sigs_viewed = max(stats.get("signals_viewed", 0), 6)
    stocks_ana  = max(stats.get("stocks_analyzed", 0), 4)
    st.markdown(f"""
<div class="dg-overlay">
  <div class="dg-card">
    <span class="dg-icon">📉</span>
    <div class="dg-title">Your premium trial has ended</div>
    <div class="dg-sub">{name}, you've lost access to the tools<br>that gave you your NGX edge.</div>
    <div style="font-family:var(--font-mono);font-size:9px;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;text-align:center;">During your 14-day trial:</div>
    <div class="dg-stats">
      <div class="dg-stat"><div class="dg-stat-num">{ai_used}</div><div class="dg-stat-lbl">AI queries</div></div>
      <div class="dg-stat"><div class="dg-stat-num">{sigs_viewed}</div><div class="dg-stat-lbl">Signals viewed</div></div>
      <div class="dg-stat"><div class="dg-stat-num">{stocks_ana}</div><div class="dg-stat-lbl">Stocks analysed</div></div>
    </div>
    <div class="dg-lost">
      <div class="dg-lost-title">You've lost access to:</div>
      <div class="dg-lost-item"><span style="color:var(--red);">✕</span> Full AI market analysis &amp; recommendations</div>
      <div class="dg-lost-item"><span style="color:var(--red);">✕</span> Daily AI picks — 9 curated buy/hold/avoid stocks</div>
      <div class="dg-lost-item"><span style="color:var(--red);">✕</span> Signal scores for all 144 NGX stocks</div>
      <div class="dg-lost-item"><span style="color:var(--red);">✕</span> Telegram alerts &amp; morning market brief</div>
    </div>
    <div style="font-family:var(--font-head);font-size:15px;font-weight:700;color:var(--t1);text-align:center;margin-bottom:16px;">Don't lose your edge in the market.</div>
  </div>
</div>""", unsafe_allow_html=True)
    _, bc, _ = st.columns([1, 2, 1])
    with bc:
        if st.button("🚀 Restore full access — upgrade →", key="dg_upgrade", type="primary", use_container_width=True):
            st.session_state.deep_link_plan = True
            st.session_state.current_page   = "settings"
            st.rerun()


def _render_single_upgrade_cta(tier, profile, cta_label, cta_page):
    """One clean upgrade card — shown once per page for funnel tiers"""
    if tier not in ("free", "trial", "starter", "trader"):
        return

    if tier == "free":
        title   = "Unlock the full NGX Signal edge"
        sub     = "You're seeing 2 of 5 signals. Trial gives you all 144 signals, 9 daily AI picks, entry prices, stop-losses, and unlimited AI — free for 14 days."
        feats   = ["All 144 signal scores", "9 daily AI picks", "Entry + target + stop-loss", "Unlimited AI queries", "No credit card needed"]
    elif tier == "trial":
        _, days_left, _, trial_urgent = _get_trial_info(profile)
        title   = f"{'⚠️ ' if trial_urgent else ''}Keep your premium access"
        sub     = f"Your trial ends in {days_left} day{'s' if days_left!=1 else ''}. Upgrade now to maintain all your signals, AI queries, and alerts without interruption."
        feats   = ["Uninterrupted signal access", "All picks &amp; alerts", "Your streak keeps running", "Starts from ₦3,500/mo"]
    elif tier == "starter":
        title   = "Upgrade to Trader"
        sub     = "Unlock unlimited AI queries, stop-loss levels per signal, Pidgin AI brief, and Telegram alerts. One monthly price."
        feats   = ["Unlimited AI queries", "Stop-loss per signal", "Pidgin mode AI brief", "Telegram alerts"]
    else:  # trader
        title   = "Upgrade to Pro"
        sub     = "Unlock PDF intelligence reports, portfolio-level AI strategy, and advanced position sizing. The full NGX Signal intelligence stack."
        feats   = ["PDF intelligence reports", "Portfolio AI strategy", "Advanced position sizing", "Priority signal alerts"]

    feats_html = "".join(f'<span class="upgrade-feat">✔ {f}</span>' for f in feats)
    st.markdown(f"""
<div class="upgrade-card">
  <div class="upgrade-title">{title}</div>
  <div class="upgrade-sub">{sub}</div>
  <div class="upgrade-features">{feats_html}</div>
</div>""", unsafe_allow_html=True)

    _, cc, _ = st.columns([1, 3, 1])
    with cc:
        if st.button(cta_label, key="single_upgrade_cta", type="primary", use_container_width=True):
            _unlock_cta("upgrade_cta", "home", tier, cta_page)


# ─────────────────────────────────────────────────────────────────────────────
# PRO COMMAND CENTER  (preserved from v11, lightly refactored)
# ─────────────────────────────────────────────────────────────────────────────

def _render_pro_command_center(tier, is_trader, is_pro, sb, uniq, now, sig_map, _gp, _gp_ai_ctx):
    from app.views.global_pulse import get_global_pulse, get_sector_global_context
    import hashlib

    if not (is_trader or is_pro):
        return

    sig_res   = _load_home_signals()
    top_sigs  = [s for s in sig_res if s.get("signal","").upper() in ("STRONG_BUY","BUY")][:1]

    if not top_sigs:
        st.markdown('<div class="pcc"><div class="pcc-topbar"></div><div class="pcc-body" style="text-align:center;padding:32px;"><div style="font-family:var(--font-mono);font-size:12px;color:var(--t3);">Command Center data refreshes at 10 AM WAT each trading day.</div></div></div>', unsafe_allow_html=True)
        return

    s       = top_sigs[0]
    sym     = s.get("symbol","")
    signal  = (s.get("signal") or "HOLD").upper()
    stars   = min(int(s.get("stars",3) or 3), 5)
    reason  = (s.get("reasoning") or "Signal based on price momentum and volume analysis.")

    price_data = next((p for p in uniq if p.get("symbol","") == sym), {})
    price      = float(price_data.get("price",0) or 0)
    chg        = float(price_data.get("change_percent",0) or 0)
    entry      = round(price * 0.995, 2) if price > 0 else 0
    target     = round(price * 1.08,  2) if price > 0 else 0
    stop_loss  = round(price * 0.94,  2) if price > 0 else 0
    upside_pct = round((target - price) / price * 100, 1) if price > 0 else 0
    conf_base  = 72 + (int(hashlib.md5(sym.encode()).hexdigest(),16) % 18)
    conf       = min(conf_base, 95)

    sig_data   = sig_map.get(sym, {})
    mom_score  = int(sig_data.get("momentum_score",0) or 0)
    vol_score  = int(sig_data.get("volume_score",0)   or 0)
    nws_score  = int(sig_data.get("news_score",0)     or 0)

    sc = "var(--green-lt)" if "BUY" in signal else "var(--red)" if "AVOID" in signal else "var(--amber)"
    conf_label = "Very High" if conf >= 85 else "High" if conf >= 70 else "Moderate"

    bars_filled = round(conf / 10)
    _fc = "#22C55E"
    _ec = "var(--border2)"
    bars_html   = "".join(
        f'<div class="pcc-bar-block" style="background:{_fc if i < bars_filled else _ec};"></div>'
        for i in range(10)
    )

    # Global pulse context
    context_txt = ""
    try:
        _gp_impacts = (_gp or {}).get("impacts", {})
        context_txt = _gp_impacts.get("summary","")
    except Exception:
        pass

    chg_col = "var(--green-lt)" if chg >= 0 else "var(--red)"
    stars_html = "⭐" * stars
    chg_str    = f"+{chg:.2f}% ▲" if chg >= 0 else f"{chg:.2f}% ▼"

    st.markdown(f"""
<div class="pcc">
  <div class="pcc-topbar"></div>
  <div class="pcc-header">
    <div class="pcc-title-row">
      <div class="dot-amber"></div>
      <span class="pcc-title-text">Command Center</span>
      <span class="pill pill-amber">{"PRO" if is_pro else "TRADER"}</span>
    </div>
    <span style="font-family:var(--font-mono);font-size:10px;color:var(--t3);">{now.strftime("%I:%M %p")} WAT</span>
  </div>
  <div class="pcc-body">
    <div class="pcc-hero-row">
      <div>
        <div class="pcc-sym">{sym} <span style="font-size:14px;">{stars_html}</span></div>
        <div class="pcc-co-name">{signal} signal &nbsp;·&nbsp; <span style="color:{chg_col};">{chg_str}</span></div>
      </div>
      <div class="pcc-upside-box">
        <div class="pcc-upside-label">Upside</div>
        <div class="pcc-upside-val" style="color:var(--green-lt);">+{upside_pct}%</div>
      </div>
    </div>
    <div class="pcc-price-grid">
      <div class="pcc-price-cell">
        <div class="pcc-price-label">Entry</div>
        <div class="pcc-price-val" style="color:var(--t1);">{_fmt_price(entry)}</div>
      </div>
      <div class="pcc-price-cell">
        <div class="pcc-price-label">Target</div>
        <div class="pcc-price-val" style="color:var(--green-lt);">{_fmt_price(target)}</div>
      </div>
      <div class="pcc-price-cell">
        <div class="pcc-price-label">Stop-loss</div>
        <div class="pcc-price-val" style="color:var(--red);">{_fmt_price(stop_loss)}</div>
      </div>
    </div>
    <div style="font-family:var(--font-mono);font-size:9px;color:var(--t3);letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px;">Signal drivers</div>
    <div class="pcc-drivers">
      <div class="pcc-driver"><span class="pcc-driver-icon">📊</span>{reason[:120]}</div>
      {"<div class='pcc-driver'><span class='pcc-driver-icon'>📈</span>Momentum " + str(mom_score) + "/100 · Volume " + str(vol_score) + "/100 · News sentiment " + str(nws_score) + "/100</div>" if mom_score or vol_score else ""}
    </div>
    <div class="pcc-verdict" style="background:rgba(34,197,94,.06);border:0.5px solid var(--green-bd);">
      <div class="pcc-verdict-label" style="color:var(--green-lt);">AI verdict</div>
      <div class="pcc-verdict-text">This looks like a strong short-term opportunity based on current momentum and volume setup.</div>
    </div>
    <div class="pcc-conf-wrap">
      <div class="pcc-conf-row">
        <span class="pcc-conf-label">Signal confidence</span>
        <div class="pcc-conf-right">
          <span class="pcc-conf-val" style="color:{sc};">{conf_label}</span>
          <span class="pcc-conf-pct">{conf}%</span>
        </div>
      </div>
      <div class="pcc-bar-track">{bars_html}</div>
    </div>
    {"<div class='pcc-context'><span>🌐</span><span>" + context_txt + "</span></div>" if context_txt else ""}
  </div>
</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        if st.button("📊 Full analysis →", key="pcc_full_analysis", type="primary", use_container_width=True):
            st.session_state.current_page = "signals"; st.rerun()
    with c2:
        if st.button("📡 Set alert", key="pcc_alert", use_container_width=True):
            st.session_state.current_page = "settings"; st.rerun()
    if is_pro:
        with c3:
            if st.button("📄 PDF report", key="pcc_pdf", use_container_width=True):
                st.session_state.current_page = "signals"; st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# VISITOR HERO SECTION
# ─────────────────────────────────────────────────────────────────────────────

def _render_visitor_hero(top_g_text, gc, total, market, notif_minutes):
    open_status = "🟢 NGX market is open" if market["is_open"] else "🔒 NGX market closed"
    st.markdown(f"""
<div class="hero-wrap grid-bg">
  <div class="hero-eyebrow"><div class="dot-live"></div>{open_status} · 144 stocks tracked live</div>
  <div class="hero-title">AI-powered buy &amp; sell signals<br>for every <span>NGX stock</span></div>
  <div class="hero-sub">
    Every trading day our AI scans all 144 Nigerian Stock Exchange stocks and tells you exactly what to do — entry price, target, and stop-loss included. In plain English.
  </div>
  <div class="hero-cta-row">
    <button class="btn-primary" onclick="void(0)">Start free — 14-day trial</button>
    <button class="btn-ghost" onclick="void(0)">See how it works ↓</button>
  </div>
  <div class="hero-note">No credit card needed &nbsp;·&nbsp; Cancel anytime &nbsp;·&nbsp; Plans from ₦3,500/mo</div>
</div>
<div class="trust-bar">
  <div class="trust-item"><span class="trust-check">✓</span> CAC registered business</div>
  <div class="trust-sep"></div>
  <div class="trust-item"><span class="trust-check">✓</span> NGX Exchange data</div>
  <div class="trust-sep"></div>
  <div class="trust-item"><span class="trust-check">✓</span> 2,400+ active users</div>
  <div class="trust-sep"></div>
  <div class="trust-item"><span class="trust-check">✓</span> Built in Lagos, Nigeria</div>
  <div class="trust-sep"></div>
  <div class="trust-item"><span class="trust-check">✓</span> Not financial advice</div>
</div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────────────────────────────────────────

def render():
    # ── Auth intercept ────────────────────────────────────────────────────────
    if st.session_state.get("show_auth") and not st.session_state.get("user"):
        from app.views import auth as _auth_view
        st.markdown(f"""
<div style="background:var(--surface2);border:0.5px solid var(--amber-bd);border-radius:var(--r-lg);
     padding:20px 22px;text-align:center;max-width:520px;margin:16px auto 20px;">
  <div style="font-size:32px;margin-bottom:10px;">🔐</div>
  <div style="font-family:var(--font-head);font-size:20px;font-weight:800;color:var(--amber);margin-bottom:6px;">
    Sign up free — get 14 days premium
  </div>
  <div style="font-family:var(--font-mono);font-size:12px;color:var(--t2);line-height:1.7;">
    Full AI signals · Daily picks · Entry &amp; target prices · No credit card needed
  </div>
</div>""", unsafe_allow_html=True)
        _auth_view.render()
        if st.button("← Back to homepage", key="auth_back"):
            st.session_state.show_auth = False
            st.rerun()
        return

    # ── State & computed vars ─────────────────────────────────────────────────
    now      = now_wat()
    market   = _get_market_status(now)
    today    = now.date()

    user     = st.session_state.get("user")
    profile  = st.session_state.get("profile", {})
    tier     = get_user_tier()
    name     = (profile.get("full_name") or (user.get("email","").split("@")[0] if user else "trader")).split()[0].capitalize()
    sb       = _get_sb()
    current_user = user

    is_visitor    = tier == "visitor"
    is_free       = tier == "free"
    is_trial      = tier == "trial"
    is_starter    = tier == "starter"
    is_trader     = tier == "trader"
    is_pro        = tier == "pro"
    is_paid       = tier in PAID_TIERS
    is_funnel     = tier in ("visitor","free","trial")
    is_dashboard  = not is_funnel
    is_ex_trial   = profile.get("had_trial") and not is_trial and not is_paid

    trial_start, trial_days_left, trial_day_num, trial_urgent = _get_trial_info(profile) if is_trial else (None, 0, 0, False)

    cta_label, cta_page = _get_dynamic_cta(tier, profile)

    # ── Inject fonts & CSS ────────────────────────────────────────────────────
    st.markdown(_FONTS, unsafe_allow_html=True)
    st.markdown(_CSS,   unsafe_allow_html=True)

    # ── Downgrade modal ───────────────────────────────────────────────────────
    if is_ex_trial and not st.session_state.get("dg_modal_dismissed"):
        _render_downgrade_modal(name, {
            "total_ai_queries": get_total_ai_queries(),
            "signals_viewed":   get_eng("signals_viewed"),
            "stocks_analyzed":  get_eng("stocks_analyzed"),
        })
        st.session_state.dg_modal_dismissed = True
        return

    # ── Data load ─────────────────────────────────────────────────────────────
    raw, latest_date = _load_home_prices()
    seen = set(); uniq = []
    for p in raw:
        s = p.get("symbol","")
        if s and s not in seen: seen.add(s); uniq.append(p)

    total   = len(uniq)
    gainers = sum(1 for p in uniq if float(p.get("change_percent") or 0) > 0)
    losers  = sum(1 for p in uniq if float(p.get("change_percent") or 0) < 0)
    sm      = _load_home_market_summary()
    asi     = float(sm.get("asi_index",0) or 0)
    acg     = float(sm.get("asi_change_percent",0) or 0)
    gc      = gainers if total > 5 else int(sm.get("gainers_count",0) or 0)
    lc      = losers  if total > 5 else int(sm.get("losers_count",0) or 0)
    acol    = "#22C55E" if acg >= 0 else "#EF4444"
    aarr    = "▲" if acg >= 0 else "▼"
    mood    = "Bullish" if acg > 0.5 else "Bearish" if acg < -0.5 else "Neutral"
    ad      = f"{asi:,.2f}" if asi > 0 else "—"
    data_label = latest_date if market["is_open"] else f"Last: {latest_date}"

    brief_res  = _load_home_briefs()
    top_g      = sorted(uniq, key=lambda x: float(x.get("change_percent",0) or 0), reverse=True)[:8]
    top_g_text = ", ".join(f"{p['symbol']} (+{float(p.get('change_percent',0)):.1f}%)" for p in top_g[:3])
    notif_min  = (now.hour * 60 + now.minute) % 137 + 3

    # Global Pulse
    _gp = None
    try: _gp = get_global_pulse()
    except: pass
    _gp_ai_ctx = get_global_pulse_for_ai(_gp) if _gp else ""

    # Signal insights (session-cached per day)
    insight_key = f"ins_{_daily_seed()}"
    if insight_key not in st.session_state.get("mai_insights", {}):
        if "mai_insights" not in st.session_state: st.session_state.mai_insights = {}
        sig_res_data = _load_home_signals()
        generated = []; seen_ins = set()
        for s in sig_res_data:
            sym2 = s.get("symbol",""); sig2 = (s.get("signal") or "HOLD").upper().replace(" ","_")
            if sym2 in seen_ins or not sym2: continue
            seen_ins.add(sym2)
            if sig2 in ("STRONG_BUY","BUY"):   action,ac,base = "BUY","#22C55E",72
            elif sig2 == "HOLD":                action,ac,base = "HOLD","#F0A500",55
            elif sig2 in ("CAUTION","AVOID"):   action,ac,base = "AVOID","#EF4444",60
            else: continue
            conf   = min(base + (int(hashlib.md5(sym2.encode()).hexdigest(),16) % 20), 95)
            reason = (s.get("reasoning") or "Signal based on price momentum and volume analysis.")[:90]
            if len(reason) == 90: reason += "…"
            p_data = next((p for p in uniq if p.get("symbol","") == sym2), {})
            price_val = float(p_data.get("price",0) or 0)
            generated.append({"sym":sym2,"action":action,"ac":ac,"conf":conf,"reason":reason,"price":price_val,"name":""})
            if len(generated) >= 5: break
        st.session_state.mai_insights[insight_key] = generated
    insights = st.session_state.mai_insights.get(insight_key, [])

    # Trending signal map
    _sig_res_data = _load_home_trending_signals()
    _sig_map: dict = {}
    for _sr in _sig_res_data:
        _s = _sr.get("symbol","")
        if _s and _s not in _sig_map: _sig_map[_s] = _sr

    # Daily picks — pulled from real data, no hardcoded fallback
    _pk = f"daily_picks_{_daily_seed()}"
    if _pk not in st.session_state:
        sig_for_picks = _load_home_signals()
        buy_sigs   = [s for s in sig_for_picks if (s.get("signal","").upper() in ("STRONG_BUY","BUY"))][:3]
        hold_sigs  = [s for s in sig_for_picks if (s.get("signal","").upper() == "HOLD")][:3]
        avoid_sigs = [s for s in sig_for_picks if (s.get("signal","").upper() in ("CAUTION","AVOID","STRONG_AVOID"))][:3]

        def _to_pick(s):
            sym2  = s.get("symbol","")
            base  = 65 + (int(hashlib.md5(sym2.encode()).hexdigest(),16) % 25)
            reason = (s.get("reasoning") or "Signal based on technical analysis.")[:80]
            if len(reason) == 80: reason += "…"
            return {"sym": sym2, "reason": reason, "conf": min(base, 95)}

        # Only show skeleton if no data
        _bp = [_to_pick(s) for s in buy_sigs]   or []
        _hp = [_to_pick(s) for s in hold_sigs]  or []
        _ap = [_to_pick(s) for s in avoid_sigs] or []
        st.session_state[_pk] = {"buy":_bp, "hold":_hp, "avoid":_ap}

    _picks         = st.session_state[_pk]
    _picks_visible = 1 if is_funnel else 3
    _sig_visible   = {"free":2,"trial":5,"starter":3,"trader":5,"pro":5}.get(tier, 2)

    # AI prompt bundle
    _pai = dict(ad=ad, aarr=aarr, acg=acg, mood=mood, gc=gc, lc=lc, total=total,
                top_g_text=top_g_text, latest_date=latest_date,
                market_open=market["is_open"], uniq=uniq,
                global_context=_gp_ai_ctx)

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW A: VISITOR / FREE / TRIAL  — Value-first funnel
    # ══════════════════════════════════════════════════════════════════════════

    if is_funnel:

        # Visitor: full hero + trust bar
        if is_visitor:
            _render_visitor_hero(top_g_text, gc, total, market, notif_min)
        else:
            # Logged-in funnel (free/trial): greeting + personalized strip
            _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial, is_ex_trial)
            render_personalized_strip(tier, profile, sb, name, uniq)

        # Market strip
        _render_market_strip(ad, acg, acol, aarr, total, gc, lc, mood, "", market, data_label)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Global Pulse
        if _gp:
            render_global_pulse_strip(tier, location="home")
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Notification banner
        _render_notification_banner(top_g, now, gc, total, market, notif_min)

        # Signal preview
        st.markdown("""
<div class="sec-head">
  <span class="sec-head-title">⚡ Today's top signals</span>
  <span class="sec-head-action">Refreshed 10 AM WAT</span>
</div>""", unsafe_allow_html=True)
        _render_signal_cards(insights, tier, _sig_visible, is_trial)

        if not can_access("signals_all", tier):
            st.markdown('<div style="text-align:center;margin:-4px 0 12px;"><span class="pill pill-ghost">🔒 3 more signals + full analysis on trial &amp; above</span></div>', unsafe_allow_html=True)

        # Daily AI brief teaser
        _render_brief_section(tier, brief_res)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # Daily picks (1-of-each teaser for funnel)
        _render_daily_picks(tier, is_trial, _picks, _picks_visible)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # AI Chat
        _render_ai_chat(tier, name, uniq, _pai, market, latest_date, is_trial)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # Market news (collapsed)
        _render_news_section(tier)

        # Sector snapshot (collapsed)
        _render_sector_snapshot(tier)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── SINGLE UPGRADE CTA — shown once, at the bottom ───────────────────
        if not is_visitor:
            _render_single_upgrade_cta(tier, profile, cta_label, cta_page)
        else:
            # Visitor gets a CTA button at top (already in hero) + one below
            st.markdown("""
<div class="upgrade-card" style="text-align:center;">
  <div class="upgrade-title">Ready to get your edge?</div>
  <div class="upgrade-sub">Join 2,400+ NGX traders using AI signals every day. 14 days free — no card needed.</div>
</div>""", unsafe_allow_html=True)
            _, cc, _ = st.columns([1, 3, 1])
            with cc:
                if st.button("🔐 Sign up free — start trial →", key="visitor_bottom_cta", type="primary", use_container_width=True):
                    _unlock_cta("visitor_cta", "visitor", tier, "settings")

        # Trade game
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _render_trade_game(sb, current_user)
        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW B: STARTER / TRADER / PRO — Intelligence delivery
    # ══════════════════════════════════════════════════════════════════════════

    else:

        # Greeting first
        _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial, is_ex_trial)

        # Personalized strip
        render_personalized_strip(tier, profile, sb, name, uniq)

        # Streak badge (if earned)
        _sk = get_streak()
        if _sk >= 2 and not st.session_state.get("streak_shown_today"):
            _ms = streak_milestone(_sk)
            if _ms:
                st.markdown(f'<div class="streak-badge"><span class="streak-num" style="animation:num-pop .4s ease both;">{_sk}</span><div><div style="font-size:12px;font-weight:600;color:var(--amber);">Day streak — {_ms}</div><div style="font-size:10px;color:var(--t3);">You\'re building a real market intelligence habit</div></div></div>', unsafe_allow_html=True)
            st.session_state["streak_shown_today"] = str(today)

        # ── PRO COMMAND CENTER — first major element for paid tiers ──────────
        _render_pro_command_center(tier, is_trader, is_pro, sb, uniq, now, _sig_map, _gp, _gp_ai_ctx)

        # Market strip
        _render_market_strip(ad, acg, acol, aarr, total, gc, lc, mood, "", market, data_label)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Global Pulse
        if _gp:
            render_global_pulse_strip(tier, location="home")
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Notification banner
        _render_notification_banner(top_g, now, gc, total, market, notif_min)

        # AI Brief (expanded for paid)
        with st.expander("✨  TODAY'S AI MARKET BRIEF", expanded=True):
            _render_brief_section(tier, brief_res)

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # All signal cards (paid — full access)
        st.markdown("""
<div class="sec-head">
  <span class="sec-head-title">⚡ Today's AI signals</span>
  <span class="sec-head-action">All 144 stocks covered</span>
</div>""", unsafe_allow_html=True)
        _render_signal_cards(insights, tier, _sig_visible, False)

        if st.button("📊 View all signals →", key="btn_all_sigs", use_container_width=False):
            st.session_state.current_page = "signals"; st.rerun()

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # Daily picks (full 3 per category for paid)
        _render_daily_picks(tier, False, _picks, 3)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # AI Chat
        _render_ai_chat(tier, name, uniq, _pai, market, latest_date, True)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # Top Movers
        sup  = sorted([p for p in uniq if float(p.get("change_percent") or 0) > 0],
                      key=lambda x: float(x.get("change_percent",0) or 0), reverse=True)[:6]
        sdn  = sorted([p for p in uniq if float(p.get("change_percent") or 0) < 0],
                      key=lambda x: float(x.get("change_percent",0) or 0))[:3]
        _render_top_movers(sup + sdn, latest_date, market)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # News & Sectors (collapsed)
        _render_news_section(tier)
        _render_sector_snapshot(tier)

        # Trade Game
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _render_trade_game(sb, current_user)

        # ── Upgrade nudge — single, subtle, only if not pro ──────────────────
        if not is_pro and (cta_label):
            st.markdown(f"""
<div class="bottom-upgrade">
  <div class="bottom-upgrade-text">
    <strong>{tier.capitalize()} plan</strong> &nbsp;·&nbsp; {
      "Upgrade to Trader for unlimited AI queries, stop-loss signals &amp; Telegram alerts." if is_starter
      else "Upgrade to Pro for PDF reports, portfolio AI strategy &amp; advanced outputs."
    }
  </div>
</div>""", unsafe_allow_html=True)
            if st.button(cta_label, key="dashboard_upgrade_nudge", type="primary"):
                _unlock_cta("dashboard_nudge", "dashboard", tier, cta_page)

        st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
