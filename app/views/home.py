"""
NGX Signal \u2014 Home View
======================
Hybrid monetisation: Always show DATA, restrict INTELLIGENCE by tier.

Tiers (ordered lowest \u2192 highest):
  visitor  \u2192 unauthenticated, UI-only
  free     \u2192 authenticated, 2 AI queries/day
  trial    \u2192 14-day full access with countdown
  starter  \u2192 15 AI queries/day
  trader   \u2192 unlimited queries
  pro      \u2192 unlimited + advanced outputs (strategy, portfolio, recs)
"""
import streamlit as st
import re
import requests
import hashlib
from datetime import date, datetime, timedelta
from app.utils.supabase_client import get_supabase

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

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# TIER SYSTEM
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

TIER_ORDER   = ["visitor", "free", "trial", "starter", "trader", "pro"]
PAID_TIERS   = {"starter", "trader", "pro"}
TRIAL_TIERS  = {"trial"}

_QUERY_LIMITS: dict[str, int | None] = {
    "visitor": 0,
    "free":    2,
    "trial":   None,
    "starter": 15,
    "trader":  None,
    "pro":     None,
}

_FEATURE_MIN_TIER: dict[str, str] = {
    "ai_input":             "free",
    "ai_full_response":     "trial",
    "ai_advanced_outputs":  "pro",
    "signals_all":          "trial",
    "signals_confidence":   "starter",
    "daily_picks_all":      "trial",
    "daily_picks_entry":    "starter",
    "brief_full":           "trial",
    "brief_pidgin":         "trader",
    "sector_all":           "trial",
    "news_full":            "trial",
    "trending_opportunities":"trial",
    "follow_up_chips":      "free",
    "streak_system":        "free",
    "export_pdf":           "pro",
    "telegram_alerts":      "starter",
}

_LOCK_COPY: dict[str, dict] = {
    "ai_input": {
        "title": "Create a Free Account to Ask AI",
        "bullets": ["\u2705 Free: 2 AI queries per day", "\ud83d\udd12 Full analysis on Starter+",
                    "\ud83d\udd12 Unlimited on Trader & Pro"],
        "cta": "Create Free Account \u2192",
    },
    "ai_full_response": {
        "title": "\ud83d\udd12 Unlock Full AI Analysis",
        "bullets": ["\u2705 You're seeing a preview", "\ud83d\udd12 Complete stock breakdown",
                    "\ud83d\udd12 Entry price \u00b7 Target \u00b7 Stop-loss \u00b7 Risk rating",
                    "\ud83d\udd12 Unlimited daily queries"],
        "cta": "Start Free 14-Day Trial \u2192",
    },
    "ai_advanced_outputs": {
        "title": "\ud83d\udd12 Pro AI Outputs",
        "bullets": ["\ud83d\udd12 Portfolio-level strategy", "\ud83d\udd12 Personalised stock recommendations",
                    "\ud83d\udd12 Risk-adjusted position sizing", "\ud83d\udd12 Sector rotation signals"],
        "cta": "Upgrade to Pro \u2192",
    },
    "signals_all": {
        "title": "\ud83d\udd12 See All AI Signals",
        "bullets": ["\u2705 Showing 2 of 5 signals", "\ud83d\udd12 3 more signals with full reasoning",
                    "\ud83d\udd12 Entry price & target per signal", "\ud83d\udd12 Confidence scores"],
        "cta": "Start Free Trial \u2192",
    },
    "daily_picks_all": {
        "title": "\ud83d\udd12 Unlock All 9 Daily AI Picks",
        "bullets": ["\u2705 Showing 1 pick per category (3 total)",
                    "\ud83d\udd12 6 more picks with full reasoning",
                    "\ud83d\udd12 Real-time confidence scores",
                    "\ud83d\udd12 Entry price, target & stop-loss per pick",
                    "\ud83d\udd12 Daily refresh alerts via Telegram"],
        "cta": "Start Free Trial \u2192",
    },
    "trending_opportunities": {
        "title": "\ud83d\udd12 Today's Opportunities",
        "bullets": ["\ud83d\udd12 See which stocks are moving NOW",
                    "\ud83d\udd12 Signal trigger timestamps", "\ud83d\udd12 One-tap AI analysis per stock"],
        "cta": "Start Free Trial \u2192",
    },
}

def get_user_tier() -> str:
    user    = st.session_state.get("user")
    profile = st.session_state.get("profile", {})
    if not user:
        return "visitor"
    plan = (profile.get("plan") or "free").lower().strip()
    if plan in ("starter","trader","pro","trial","free"):
        return plan
    return "free"

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

def render_locked_content(feature: str, key: str, upgrade_page: str = "settings") -> None:
    copy   = _LOCK_COPY.get(feature, {"title":"\ud83d\udd12 Upgrade Required",
                                       "bullets":["This feature requires a higher plan."],
                                       "cta":"Upgrade \u2192"})
    tier   = get_user_tier()
    req    = _FEATURE_MIN_TIER.get(feature, "starter")
    items_html = "".join(f'<li style="margin-bottom:5px;">{b}</li>' for b in copy["bullets"])
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0C0C00,#100A00);border:1px solid rgba(240,165,0,.3);
            border-radius:12px;padding:20px 22px;margin:12px 0;text-align:center;">
  <div style="font-size:22px;margin-bottom:8px;">\ud83d\udd12</div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;
              color:#F0A500;margin-bottom:10px;">{copy['title']}</div>
  <ul style="font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;text-align:left;
             display:inline-block;margin-bottom:14px;list-style:none;padding:0;">{items_html}</ul>
  <div style="font-family:'DM Mono',monospace;font-size:10px;color:#404040;margin-top:2px;">
    Your plan: <strong style="color:#808080;">{tier.upper()}</strong>
    &nbsp;\u00b7&nbsp; Required: <strong style="color:#F0A500;">{req.upper()}+</strong>
  </div>
</div>""", unsafe_allow_html=True)
    _,col,_ = st.columns([1,2,1])
    with col:
        if st.button(copy["cta"], key=key, type="primary", use_container_width=True):
            st.session_state.current_page = upgrade_page; st.rerun()

def _upgrade_inline(msg: str, key: str, cta: str = "\ud83d\ude80 Upgrade \u2192", page: str = "settings"):
    st.markdown(f"""
<div style="background:rgba(240,165,0,.05);border:1px solid rgba(240,165,0,.18);
            border-left:3px solid #F0A500;border-radius:8px;
            padding:10px 14px;margin:8px 0;font-family:'DM Mono',monospace;
            font-size:12px;color:#B0B0B0;">\ud83d\udd12 {msg}</div>""", unsafe_allow_html=True)
    if st.button(cta, key=key, type="primary"):
        st.session_state.current_page = page; st.rerun()

def _tier_badge_html(tier: str) -> str:
    colors = {"visitor":"#606060","free":"#808080","trial":"#22C55E",
              "starter":"#3B82F6","trader":"#A78BFA","pro":"#F0A500"}
    c = colors.get(tier, "#606060")
    return (f'<span style="background:{c}1A;border:1px solid {c}55;border-radius:4px;'
            f'padding:2px 7px;font-family:DM Mono,monospace;font-size:9px;font-weight:700;'
            f'color:{c};text-transform:uppercase;letter-spacing:.08em;">{tier}</span>')

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# ENGAGEMENT TRACKING
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

def _eng_key(k):           return f"eng_{k}"
def get_eng(k, default=0): return st.session_state.get(_eng_key(k), default)
def inc_eng(k, by=1):      st.session_state[_eng_key(k)] = get_eng(k) + by
def set_eng(k, v):         st.session_state[_eng_key(k)] = v

def track_signal_view():   inc_eng("signals_viewed")
def track_stock_analyzed(sym: str):
    seen = get_eng("stocks_analyzed_set", set())
    if sym not in seen:
        seen.add(sym); set_eng("stocks_analyzed_set", seen)
        set_eng("stocks_analyzed", len(seen))

def get_total_ai_queries():  return get_eng("total_ai_queries", 0)
def inc_total_ai_queries():  inc_eng("total_ai_queries")

def get_ai_query_count():    return st.session_state.get(f"ai_q_{date.today()}", 0)
def increment_ai_query_count():
    k = f"ai_q_{date.today()}"
    st.session_state[k] = st.session_state.get(k, 0) + 1
    inc_total_ai_queries()

def _queries_remaining(tier: str) -> tuple[int | None, bool]:
    limit = get_usage_limit("ai_queries", tier)
    if limit is None:  return None, False
    if limit == 0:     return 0, True
    used  = get_ai_query_count()
    rem   = max(0, limit - used)
    return rem, rem == 0

# \u2550\u2550\u2550 Streak \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

def get_streak() -> int:
    return st.session_state.get("ai_streak", 0)

def update_streak():
    today_str   = str(date.today())
    last_active = st.session_state.get("streak_last_date", "")
    streak      = st.session_state.get("ai_streak", 0)
    if last_active == today_str: return
    yesterday = str(date.today() - timedelta(days=1))
    streak    = streak + 1 if last_active == yesterday else 1
    st.session_state.ai_streak        = streak
    st.session_state.streak_last_date = today_str
    st.session_state.streak_shown     = False

def streak_milestone(streak: int) -> str | None:
    return {3:"3 days in a row \ud83d\udd25",5:"5-day streak! \ud83d\ude80",
            7:"Full week streak \ud83c\udfc6",14:"14-day champion \ud83e\udd47"}.get(streak)

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# TRIAL HELPERS
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

def get_trial_days_left(profile: dict) -> int:
    ts_raw = profile.get("trial_start_date") or profile.get("created_at","")
    if not ts_raw: return 14
    try:
        ts = datetime.fromisoformat(str(ts_raw)[:10])
        return max(0, 14 - (datetime.utcnow() - ts).days)
    except: return 14

def get_trial_day_number(profile: dict) -> int:
    ts_raw = profile.get("trial_start_date") or profile.get("created_at","")
    if not ts_raw: return 1
    try:
        ts = datetime.fromisoformat(str(ts_raw)[:10])
        return min(14, max(1, (datetime.utcnow() - ts).days + 1))
    except: return 1

def was_trial_user(profile: dict) -> bool:
    return (profile.get("was_trial", False) or profile.get("previous_plan") == "trial")

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# MARKET / AI HELPERS
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

def get_market_status():
    now=now_wat(); dow=now.weekday(); ds=now.strftime("%Y-%m-%d")
    hhmm=now.hour*60+now.minute; OPEN,CLOSE=10*60,15*60
    if dow>=5:      return {"is_open":False,"label":"Closed \u2014 Weekend","note":"NGX is closed on weekends. Showing last closing prices.","color":"#EF4444"}
    if ds in NG_HOLIDAYS_2026: return {"is_open":False,"label":"Closed \u2014 Public Holiday","note":"NGX is closed today. Showing last closing prices.","color":"#EF4444"}
    if hhmm<OPEN:
        m=OPEN-hhmm; return {"is_open":False,"label":f"Pre-Market \u2014 Opens in {m//60}h {m%60}m","note":"NGX opens 10AM WAT. Showing last closing prices.","color":"#D97706"}
    if hhmm>=CLOSE: return {"is_open":False,"label":"Closed \u2014 After Hours","note":"NGX closed 3PM WAT. Showing today's final prices.","color":"#A78BFA"}
    m=CLOSE-hhmm;   return {"is_open":True,"label":f"Live \u2014 Closes in {m//60}h {m%60}m","note":"Market is live now.","color":"#22C55E"}

def get_greeting(name):
    h=now_wat().hour
    if 5<=h<12:   return f"Good morning, {name} \ud83d\udc4b"
    elif 12<=h<17: return f"Good afternoon, {name} \u2600\ufe0f"
    elif 17<=h<21: return f"Good evening, {name} \ud83c\udf06"
    else:          return f"Hello, {name} \ud83c\udf19"

def _classify_query(question: str) -> str:
    q = question.lower()
    decision_triggers = [
        "should i", "is it good", "buy or not", "invest in", "worth buying",
        "is this a buy", "is this good", "should i buy", "should i sell",
        "should i hold", "good investment", "worth it", "is it worth",
        "good buy", "bad buy", "can i buy", "right time to buy",
    ]
    explain_triggers = [
        "analyze", "analyse", "why", "explain", "tell me about",
        "what is", "how does", "breakdown", "deep dive", "more detail",
        "give me analysis", "technical",
    ]
    for t in decision_triggers:
        if t in q: return "decision"
    for t in explain_triggers:
        if t in q: return "explain"
    return "decision"

def _build_ai_system_prompt(
    tier:        str,
    ad:          str,
    aarr:        str,
    acg:         float,
    mood:        str,
    gc:          int,
    lc:          int,
    total:       int,
    top_g_text:  str,
    latest_date: str,
    market_open: bool,
    question:    str = "",
) -> str:
    query_mode = _classify_query(question)

    persona = """You are NGX Signal AI \u2014 a smart, practical financial assistant built specifically for Nigerian stock traders.

YOUR COMMUNICATION RULES (non-negotiable):
1. ALWAYS answer the user's question DIRECTLY first \u2014 never delay the answer.
2. Use very simple, clear, plain English. Explain any jargon you must use.
3. Be direct, confident, and human-like \u2014 not robotic or generic.
4. Focus on Nigerian stock market context (NGX, Naira, Nigerian companies).
5. NEVER start with "Certainly!", "Great question!", or any filler phrases.
6. Do NOT sound like a generic AI. Sound like a knowledgeable Nigerian market expert.

"""

    market_ctx = (
        f"LIVE MARKET DATA (as of {latest_date}):\n"
        f"- NGX All-Share Index: {ad} ({aarr}{abs(acg):.2f}%)\n"
        f"- Market: {'Open now' if market_open else 'Closed (last close data)'}\n"
        f"- Mood: {mood} | Gainers: {gc} | Losers: {lc} | Total tracked: {total}\n"
        f"- Top movers today: {top_g_text or 'None yet'}\n\n"
    )

    if query_mode == "decision":
        decision_rule = (
            "CRITICAL INSTRUCTION \u2014 DECISION MODE ACTIVE:\n"
            "The user is asking for a recommendation. You MUST:\n"
            "1. Start your response with a clear decision on the VERY FIRST LINE:\n"
            "   Use exactly this format: 'Recommendation: BUY \u2705' or 'Recommendation: HOLD \u2696\ufe0f' "
            "   or 'Recommendation: AVOID \u274c'\n"
            "2. Give the decision BEFORE any explanation.\n"
            "3. Do NOT start with analysis. Do NOT delay the answer.\n\n"
        )
    else:
        decision_rule = (
            "The user wants an explanation or analysis. "
            "Lead with the most important insight, then expand.\n\n"
        )

    if tier in ("free", "trial") and tier != "starter":
        tier_instructions = (
            "RESPONSE FORMAT \u2014 FREE PLAN:\n"
            "- Maximum 3-4 lines total.\n"
            "- Give the recommendation (if decision mode), then 1-2 sentences of reason.\n"
            "- No technical breakdown, no data tables, no entry/exit prices.\n"
            "- End with ONE short upgrade nudge on a new line.\n\n"
            "EXAMPLE:\n"
            "Recommendation: HOLD \u2696\ufe0f\n\n"
            "Jaiz Bank isn't showing strong movement right now. "
            "It's safer to wait for a clearer signal.\n\n"
            "_Upgrade to see full analysis and entry strategy._\n\n"
        )
        max_tok = 180

    elif tier == "starter":
        tier_instructions = (
            "RESPONSE FORMAT \u2014 STARTER PLAN:\n"
            "Respond in these sections (use the exact headers):\n\n"
            "**Recommendation: [BUY \u2705 / HOLD \u2696\ufe0f / AVOID \u274c]**\n\n"
            "[1-2 sentences: explain in the simplest way possible. "
            "No jargon. No tables. No entry prices.]\n\n"
            "**Key Signals:**\n"
            "- Trend: [Bullish / Neutral / Bearish]\n"
            "- Momentum: [Strong / Moderate / Weak]\n"
            "- Risk Level: [Low / Medium / High]\n\n"
            "**Tip:** [One short, practical action \u2014 e.g. 'Wait for breakout above \u20a6X before buying']\n\n"
            "RULES:\n"
            "- Keep every section short and beginner-friendly.\n"
            "- No overwhelming detail. No complex financial terms.\n"
            "- Total response: under 120 words.\n\n"
        )
        max_tok = 250

    elif tier == "trader":
        tier_instructions = (
            "RESPONSE FORMAT \u2014 TRADER PLAN:\n"
            "Respond in these sections (use the exact headers):\n\n"
            "**Recommendation: [BUY \u2705 / HOLD \u2696\ufe0f / AVOID \u274c]**\n\n"
            "[2-3 sentences: explain the situation in very plain English. "
            "What's happening with the stock, what the trend shows.]\n\n"
            "**Key Signals:**\n"
            "- Trend: [Bullish / Neutral / Bearish]\n"
            "- Momentum: [Strong / Moderate / Weak]\n"
            "- Sentiment: [Positive / Mixed / Negative]\n"
            "- Risk Level: [Low / Medium / High]\n\n"
            "**Action Tip:** [Specific guidance \u2014 e.g. 'Enter small position around \u20a6X, "
            "set stop-loss at \u20a6Y']\n\n"
            "RULES:\n"
            "- Language must stay beginner-friendly.\n"
            "- Include a price level (entry or target) if relevant.\n"
            "- No long reports. No complex jargon.\n"
            "- Total: under 180 words.\n\n"
        )
        max_tok = 350

    else:  # pro + trial
        tier_instructions = (
            "RESPONSE FORMAT \u2014 PRO PLAN:\n"
            "Respond in these sections (use the exact headers):\n\n"
            "**Recommendation: [BUY \u2705 / HOLD \u2696\ufe0f / AVOID \u274c]**\n\n"
            "[2-3 sentences: plain English summary of the situation and why.]\n\n"
            "**Key Insights:**\n"
            "- Trend: [what direction the stock is moving and why]\n"
            "- Volume: [buying/selling activity \u2014 is there real conviction?]\n"
            "- Sentiment: [overall market mood on this stock]\n"
            "- Risk Level: [Low / Medium / High + brief reason]\n\n"
            "**Action Plan:**\n"
            "- Entry: [specific entry range in \u20a6, or 'wait for X']\n"
            "- Watch: [one specific thing to monitor next]\n"
            "- Risk Note: [one sentence on downside risk]\n\n"
            "**Detailed Insight:** *(only if adds real value)*\n"
            "[1-2 sentences of deeper context \u2014 keep it simple]\n\n"
            "RULES:\n"
            "- Must remain easy to understand \u2014 premium but not complex.\n"
            "- Include specific \u20a6 price levels wherever relevant.\n"
            "- Break everything into the sections above.\n"
            "- Total: under 280 words.\n"
            "- End with: _Educational only \u2014 not financial advice._\n\n"
        )
        max_tok = 500

    full_prompt = persona + market_ctx + decision_rule + tier_instructions
    full_prompt += f"USER QUESTION: {question}\n"
    return full_prompt, max_tok


def call_ai(prompt_or_tuple, max_tokens: int = 500):
    if isinstance(prompt_or_tuple, tuple):
        prompt, max_tokens = prompt_or_tuple
    else:
        prompt = prompt_or_tuple

    for key_name, make_req in [
        ("GROQ_API_KEY", lambda k: (
            "https://api.groq.com/openai/v1/chat/completions",
            {
                "model":       "llama-3.1-8b-instant",
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  max_tokens,
                "temperature": 0.55,
            },
            {"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
            lambda d: d["choices"][0]["message"]["content"],
        )),
        ("GEMINI_API_KEY", lambda k: (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash-latest:generateContent?key={k}",
            {
                "contents":        [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.55},
            },
            {},
            lambda d: d["candidates"][0]["content"]["parts"][0]["text"],
        )),
    ]:
        key = st.secrets.get(key_name, "")
        if not key:
            continue
        try:
            url, payload, headers, extract = make_req(key)
            r = requests.post(url, json=payload, headers=headers, timeout=25)
            if r.status_code == 200:
                return extract(r.json())
        except Exception:
            continue
    return "AI temporarily unavailable. Please try again shortly."

def get_all_latest_prices(sb):
    date_res=sb.table("stock_prices").select("trading_date").order("trading_date",desc=True).limit(1).execute()
    if not date_res.data: return [],str(date.today())
    latest=date_res.data[0]["trading_date"]
    today_res=sb.table("stock_prices").select("symbol,price,change_percent,volume").eq("trading_date",latest).limit(500).execute()
    prices=today_res.data or []
    if len(prices)<50:
        broad=sb.table("stock_prices").select("symbol,price,change_percent,volume,trading_date").order("trading_date",desc=True).limit(5000).execute()
        sym_map={}
        for p in (broad.data or []):
            s=p.get("symbol","")
            if s and s not in sym_map: sym_map[s]=p
        existing={p["symbol"] for p in prices}
        prices+=[p for s,p in sym_map.items() if s not in existing]
    return prices,latest

def _daily_seed(): return str(date.today())

def _time_ago(minutes: int) -> str:
    if minutes < 1:  return "just now"
    if minutes < 60: return f"{minutes} min{'s' if minutes>1 else ''} ago"
    h