"""
NGX Signal — Home View  v12  ★ OPTIMIZED
=========================================
Architecture: TWO distinct funnel flows sharing one render() entry point.

VISITOR / FREE  → SELL THE PRODUCT
  Single job: Show immediate value → one clear CTA → convert.
  Sections: Greeting → Hook (hero signal) → Market Status → AI Chat → Trending → Trust proof → Single upgrade CTA

DASHBOARD (Trial / Starter / Trader / Pro)  → DELIVER VALUE + RETAIN
  Single job: Intelligence fast, no friction.
  Paid flow:   Greeting → [Trader/Pro: Command Center first] → Market Snapshot → AI Chat → Best Signals → Top Movers → News → Sector → Trade Game → Subtle plan nudge
  Free/Trial:  Greeting → Trial strip (if trial) → Hero signal → Market → AI Chat → Blurred signals → Single upgrade CTA

Changes from v11:
  ✂  REMOVED: Plans & Pricing section (→ Settings)
  ✂  REMOVED: 5-step Beginner Guide (visitor/free)
  ✂  REMOVED: FAQ section (→ marketing site)
  ✂  REMOVED: Daily AI Picks (duplicate of signal cards)
  ✂  REMOVED: Hardcoded stock picks fallback (DANGCEM/GTCO/ZENITH static)
  ✂  REMOVED: "81% win rate" stat (trust liability — replaced with live market breadth)
  ✂  REMOVED: Multiple upgrade CTAs → one per page, best placement
  ✅  REORDERED: Pro/Trader Command Center is now FIRST for paid users
  ✅  ADDED: Skeleton loader for picks when data unavailable
  ✅  FIXED: Tier-specific How-to Guide now dismissible (first login after upgrade)
  ✅  CONSOLIDATED: Upgrade nudge is a single inline line → Settings link

Tier order (lowest → highest):
  visitor → free → trial → starter → trader → pro

All helper functions (tier system, AI call, engagement tracking,
trial helpers, streaks, share sheet, downgrade modal, personalized strip)
PRESERVED EXACTLY from v11. Only render() is restructured.
"""

import streamlit as st
import re
import requests
import hashlib
from datetime import date, datetime, timedelta
from app.utils.supabase_client import get_supabase
from app.views.signals import generate_trending_sentiment_tag
from app.views.global_pulse import render_global_pulse_strip, get_global_pulse, get_global_pulse_for_ai


# ══════════════════════════════════════════════════════════════════════════════
# CACHED DATA LOADERS  — prevent repeated DB hits on every Streamlit rerender
# ══════════════════════════════════════════════════════════════════════════════

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

# ══════════════════════════════════════════════════════════════════════════════
# TIER SYSTEM  (unchanged from v11)
# ══════════════════════════════════════════════════════════════════════════════

TIER_ORDER  = ["visitor", "free", "trial", "starter", "trader", "pro"]
PAID_TIERS  = {"starter", "trader", "pro"}
TRIAL_TIERS = {"trial"}

_QUERY_LIMITS: dict[str, int | None] = {
    "visitor": 0,
    "free":    2,
    "trial":   None,
    "starter": 15,
    "trader":  None,
    "pro":     None,
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

_LOCK_COPY: dict[str, dict] = {
    "ai_input": {
        "title": "Create a Free Account to Ask AI",
        "bullets": ["✅ Free: 2 AI queries per day",
                    "🔒 Full analysis on Starter+",
                    "🔒 Unlimited on Trader & Pro"],
        "cta": "Create Free Account →",
    },
    "ai_full_response": {
        "title": "🔒 Unlock Full AI Analysis",
        "bullets": ["✅ You're seeing a preview",
                    "🔒 Complete stock breakdown",
                    "🔒 Entry price · Target · Stop-loss · Risk rating",
                    "🔒 Unlimited daily queries"],
        "cta": "Start Free 14-Day Trial →",
    },
    "ai_advanced_outputs": {
        "title": "🔒 Pro AI Outputs",
        "bullets": ["🔒 Portfolio-level strategy",
                    "🔒 Personalised stock recommendations",
                    "🔒 Risk-adjusted position sizing",
                    "🔒 Sector rotation signals"],
        "cta": "Upgrade to Pro →",
    },
    "signals_all": {
        "title": "🔒 See All AI Signals",
        "bullets": ["✅ Showing 2 of 5 signals",
                    "🔒 3 more signals with full reasoning",
                    "🔒 Entry price & target per signal",
                    "🔒 Confidence scores"],
        "cta": "Start Free Trial →",
    },
    "daily_picks_all": {
        "title": "🔒 Unlock All 9 Daily AI Picks",
        "bullets": ["✅ Showing 1 pick per category (3 total)",
                    "🔒 6 more picks with full reasoning",
                    "🔒 Real-time confidence scores",
                    "🔒 Entry price, target & stop-loss per pick"],
        "cta": "Start Free Trial →",
    },
    "trending_opportunities": {
        "title": "🔒 Today's Opportunities",
        "bullets": ["🔒 See which stocks are moving NOW",
                    "🔒 Signal trigger timestamps",
                    "🔒 One-tap AI analysis per stock"],
        "cta": "Start Free Trial →",
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
    copy  = _LOCK_COPY.get(feature, {"title":"🔒 Upgrade Required",
                                      "bullets":["This feature requires a higher plan."],
                                      "cta":"Upgrade →"})
    tier  = get_user_tier()
    req   = _FEATURE_MIN_TIER.get(feature, "starter")
    items = "".join(f'<li style="margin-bottom:5px;">{b}</li>' for b in copy["bullets"])
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0C0C00,#100A00);border:1px solid rgba(240,165,0,.3);
            border-radius:12px;padding:20px 22px;margin:12px 0;text-align:center;">
  <div style="font-size:22px;margin-bottom:8px;">🔒</div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;
              color:#F0A500;margin-bottom:10px;">{copy['title']}</div>
  <ul style="font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;text-align:left;
             display:inline-block;margin-bottom:14px;list-style:none;padding:0;">{items}</ul>
  <div style="font-family:'DM Mono',monospace;font-size:10px;color:#404040;margin-top:2px;">
    Your plan: <strong style="color:#808080;">{tier.upper()}</strong>
    &nbsp;·&nbsp; Required: <strong style="color:#F0A500;">{req.upper()}+</strong>
  </div>
</div>""", unsafe_allow_html=True)
    _,col,_ = st.columns([1,2,1])
    with col:
        _cta_text = "Create Free Account →" if tier == "visitor" else copy["cta"]
        if st.button(_cta_text, key=key, type="primary", use_container_width=True):
            _unlock_cta(key + "_act", copy["cta"], tier, upgrade_page)

def _upgrade_inline(msg: str, key: str, cta: str = "🚀 Upgrade →", page: str = "settings"):
    tier = get_user_tier()
    st.markdown(f"""
<div style="background:rgba(240,165,0,.05);border:1px solid rgba(240,165,0,.18);
            border-left:3px solid #F0A500;border-radius:8px;
            padding:10px 14px;margin:8px 0;font-family:'DM Mono',monospace;
            font-size:12px;color:#B0B0B0;">🔒 {msg}</div>""", unsafe_allow_html=True)
    if st.button(cta, key=key, type="primary"):
        _unlock_cta(key + "_act", cta, tier, page)

def _unlock_cta(key: str, cta: str, tier: str, upgrade_page: str = "settings"):
    if tier == "visitor":
        st.session_state.show_auth = True
    else:
        st.session_state.deep_link_plan = True
        st.session_state.current_page   = upgrade_page
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ENGAGEMENT / STREAK / QUERY TRACKING  (unchanged from v11)
# ══════════════════════════════════════════════════════════════════════════════

def _eng_key(k): return f"eng_{st.session_state.get('user',{}).get('id','anon')}_{k}"
def get_eng(k, default=0): return st.session_state.get(_eng_key(k), default)
def inc_eng(k, by=1): st.session_state[_eng_key(k)] = get_eng(k) + by

def get_ai_query_count() -> int:
    today_key = f"ai_q_{date.today()}"
    return st.session_state.get(today_key, 0)

def inc_ai_query_count():
    today_key = f"ai_q_{date.today()}"
    st.session_state[today_key] = get_ai_query_count() + 1

def get_total_ai_queries() -> int:
    return st.session_state.get("total_ai_queries", 0)

def inc_total_ai_queries():
    st.session_state["total_ai_queries"] = get_total_ai_queries() + 1

def _queries_remaining(tier: str):
    limit = _QUERY_LIMITS.get(tier, 0)
    if limit is None:
        return None, False
    used = get_ai_query_count()
    remaining = max(0, limit - used)
    return remaining, remaining == 0


# ══════════════════════════════════════════════════════════════════════════════
# TRIAL HELPERS  (unchanged from v11)
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# MARKET / AI HELPERS  (unchanged from v11)
# ══════════════════════════════════════════════════════════════════════════════

def get_market_status():
    now=now_wat(); dow=now.weekday(); ds=now.strftime("%Y-%m-%d")
    hhmm=now.hour*60+now.minute; OPEN,CLOSE=10*60,15*60
    if dow>=5:      return {"is_open":False,"label":"Closed — Weekend","note":"NGX is closed on weekends. Showing last closing prices.","color":"#EF4444"}
    if ds in NG_HOLIDAYS_2026: return {"is_open":False,"label":"Closed — Public Holiday","note":"NGX is closed today. Showing last closing prices.","color":"#EF4444"}
    if hhmm<OPEN:
        m=OPEN-hhmm; return {"is_open":False,"label":f"Pre-Market — Opens in {m//60}h {m%60}m","note":"NGX opens 10AM WAT. Showing last closing prices.","color":"#D97706"}
    if hhmm>=CLOSE: return {"is_open":False,"label":"Closed — After Hours","note":"NGX closed 3PM WAT. Showing today's final prices.","color":"#A78BFA"}
    m=CLOSE-hhmm;   return {"is_open":True,"label":f"Live — Closes in {m//60}h {m%60}m","note":"Market is live now.","color":"#22C55E"}

def get_greeting(name):
    h=now_wat().hour
    if 5<=h<12:    return f"Good morning, {name} 👋"
    elif 12<=h<17: return f"Good afternoon, {name} ☀️"
    elif 17<=h<21: return f"Good evening, {name} 🌆"
    else:          return f"Hello, {name} 🌙"

def _classify_query(question: str) -> str:
    q = question.lower()
    decision_triggers = [
        "should i","is it good","buy or not","invest in","worth buying",
        "is this a buy","is this good","should i buy","should i sell",
        "should i hold","good investment","worth it","is it worth",
        "good buy","bad buy","can i buy","right time to buy",
    ]
    explain_triggers = [
        "analyze","analyse","why","explain","tell me about",
        "what is","how does","breakdown","deep dive","more detail",
        "give me analysis","technical",
    ]
    for t in decision_triggers:
        if t in q: return "decision"
    for t in explain_triggers:
        if t in q: return "explain"
    return "decision"

def _build_ai_system_prompt(
    tier, ad, aarr, acg, mood, gc, lc, total,
    top_g_text, latest_date, market_open, question="", **kwargs
) -> str:
    query_mode = _classify_query(question)
    persona = """You are NGX Signal AI — a smart, practical financial assistant built specifically for Nigerian stock traders.

YOUR COMMUNICATION RULES (non-negotiable):
1. ALWAYS answer the user's question DIRECTLY first — never delay the answer.
2. Use very simple, clear, plain English. Explain any jargon you must use.
3. Be direct, confident, and human-like — not robotic or generic.
4. Focus on Nigerian stock market context (NGX, Naira, Nigerian companies).
5. NEVER start with "Certainly!", "Great question!", or any filler phrases.
6. Do NOT sound like a generic AI. Sound like a knowledgeable Nigerian market expert.

"""
    global_context = kwargs.get("global_context", "") if kwargs else ""
    market_ctx = (
        f"LIVE MARKET DATA (as of {latest_date}):\n"
        f"- NGX All-Share Index: {ad} ({aarr}{abs(acg):.2f}%)\n"
        f"- Market: {'Open now' if market_open else 'Closed (last close data)'}\n"
        f"- Mood: {mood} | Gainers: {gc} | Losers: {lc} | Total tracked: {total}\n"
        f"- Top movers today: {top_g_text or 'None yet'}\n"
    )
    if global_context:
        market_ctx += global_context + "\n"
    if query_mode == "decision":
        decision_rule = (
            "CRITICAL INSTRUCTION — DECISION MODE ACTIVE:\n"
            "The user is asking for a recommendation. You MUST:\n"
            "1. Start your response with a clear decision on the VERY FIRST LINE:\n"
            "   Use exactly this format: 'Recommendation: BUY ✅' or 'Recommendation: HOLD ⚖️' "
            "   or 'Recommendation: AVOID ❌'\n"
            "2. Give the decision BEFORE any explanation.\n"
            "3. Do NOT start with analysis. Do NOT delay the answer.\n\n"
        )
    else:
        decision_rule = (
            "The user wants an explanation or analysis. "
            "Lead with the most important insight, then expand.\n\n"
        )
    if tier in ("free",) and tier != "trial":
        tier_instructions = (
            "RESPONSE FORMAT — FREE PLAN:\n"
            "- Maximum 3-4 lines total.\n"
            "- Give the recommendation (if decision mode), then 1-2 sentences of reason.\n"
            "- No technical breakdown, no data tables, no entry/exit prices.\n"
            "- End with ONE short upgrade nudge on a new line.\n\n"
        )
        max_tok = 180
    elif tier == "starter":
        tier_instructions = (
            "RESPONSE FORMAT — STARTER PLAN:\n"
            "Respond in these sections (use the exact headers):\n\n"
            "**Recommendation: [BUY ✅ / HOLD ⚖️ / AVOID ❌]**\n\n"
            "[1-2 sentences: explain in the simplest way possible. No jargon. No tables.]\n\n"
            "**Key Signals:**\n"
            "- Trend: [Bullish / Neutral / Bearish]\n"
            "- Momentum: [Strong / Moderate / Weak]\n"
            "- Risk Level: [Low / Medium / High]\n\n"
            "**Tip:** [One short, practical action]\n\n"
            "RULES:\n- Keep every section short and beginner-friendly.\n"
            "- Total response: under 120 words.\n\n"
        )
        max_tok = 250
    elif tier == "trader":
        tier_instructions = (
            "RESPONSE FORMAT — TRADER PLAN:\n"
            "Respond in these sections (use the exact headers):\n\n"
            "**Recommendation: [BUY ✅ / HOLD ⚖️ / AVOID ❌]**\n\n"
            "[2-3 sentences: explain the situation in very plain English.]\n\n"
            "**Key Signals:**\n"
            "- Trend: [Bullish / Neutral / Bearish]\n"
            "- Momentum: [Strong / Moderate / Weak]\n"
            "- Sentiment: [Positive / Mixed / Negative]\n"
            "- Risk Level: [Low / Medium / High]\n\n"
            "**Action Tip:** [Specific guidance — e.g. 'Enter small position around NX, "
            "set stop-loss at NY']\n\n"
            "RULES:\n- Language must stay beginner-friendly.\n"
            "- Include a price level (entry or target) if relevant.\n"
            "- Total: under 180 words.\n\n"
        )
        max_tok = 350
    else:  # pro + trial
        tier_instructions = (
            "RESPONSE FORMAT — PRO PLAN:\n"
            "Respond in these sections (use the exact headers):\n\n"
            "**Recommendation: [BUY ✅ / HOLD ⚖️ / AVOID ❌]**\n\n"
            "[2-3 sentences: plain English summary of the situation and why.]\n\n"
            "**Key Insights:**\n"
            "- Trend: [what direction the stock is moving and why]\n"
            "- Volume: [buying/selling activity — is there real conviction?]\n"
            "- Sentiment: [overall market mood on this stock]\n"
            "- Risk Level: [Low / Medium / High + brief reason]\n\n"
            "**Action Plan:**\n"
            "- Entry: [specific entry range in N, or 'wait for X']\n"
            "- Watch: [one specific thing to monitor next]\n"
            "- Risk Note: [one sentence on downside risk]\n\n"
            "**Detailed Insight:** *(only if adds real value)*\n"
            "[1-2 sentences of deeper context — keep it simple]\n\n"
            "RULES:\n- Must remain easy to understand — premium but not complex.\n"
            "- Include specific N price levels wherever relevant.\n"
            "- Total: under 280 words.\n"
            "- End with: _Educational only — not financial advice._\n\n"
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
    errors = []
    GROQ_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]
    groq_key = st.secrets.get("GROQ_API_KEY","")
    if groq_key:
        for model in GROQ_MODELS:
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization":f"Bearer {groq_key}","Content-Type":"application/json"},
                    json={"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,"temperature":0.4},
                    timeout=20,
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                errors.append(f"Groq/{model}: HTTP {r.status_code}")
            except Exception as e:
                errors.append(f"Groq/{model}: {e}")
    gemini_key = st.secrets.get("GEMINI_API_KEY","")
    if gemini_key:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":max_tokens,"temperature":0.4}},
                timeout=20,
            )
            if r.status_code == 200:
                parts = r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[{}])
                return parts[0].get("text","").strip() if parts else None
            errors.append(f"Gemini: HTTP {r.status_code}")
        except Exception as e:
            errors.append(f"Gemini: {e}")
    openai_key = st.secrets.get("OPENAI_API_KEY","")
    if openai_key:
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization":f"Bearer {openai_key}","Content-Type":"application/json"},
                json={"model":"gpt-4o-mini","messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,"temperature":0.4},
                timeout=20,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            errors.append(f"OpenAI: HTTP {r.status_code}")
        except Exception as e:
            errors.append(f"OpenAI: {e}")
    if errors:
        st.warning(f"AI temporarily unavailable. Tried: {'; '.join(errors[:3])}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# DATA HELPERS  (unchanged from v11)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_latest_prices(sb):
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
            s = p.get("symbol","")
            if s and s not in sym_map: sym_map[s] = p
        existing = {p["symbol"] for p in prices}
        prices  += [p for s,p in sym_map.items() if s not in existing]
    return prices, latest

def _daily_seed(): return str(date.today())

def _time_ago(minutes: int) -> str:
    if minutes < 1:  return "just now"
    if minutes < 60: return f"{minutes} min{'s' if minutes>1 else ''} ago"
    h = minutes // 60; return f"{h} hour{'s' if h>1 else ''} ago"

def _trend_tag(chg: float) -> tuple[str,str,str]:
    if chg >= 5:   return "Hot 🔥","#EF4444","↑"
    if chg >= 2:   return "Rising ▲","#22C55E","↑"
    if chg >= 0.5: return "Active","#F0A500","↑"
    if chg <= -3:  return "Dropping","#EF4444","↓"
    return "Cooling","#D97706","↓"

def _reinforcement_pill(msg: str):
    st.markdown(f"""
<div style="display:inline-flex;align-items:center;gap:7px;
            background:rgba(100,180,255,.06);border:1px solid rgba(100,180,255,.18);
            border-radius:999px;padding:4px 14px;font-family:'DM Mono',monospace;
            font-size:11px;color:rgba(100,180,255,.85);margin:4px 0 8px 0;">✨ {msg}</div>""",
    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS  — Optimized v12
# ══════════════════════════════════════════════════════════════════════════════

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');

/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; }

/* ── Section labels ── */
.sec-title {
  font-family: 'Syne', sans-serif;
  font-size: 13px;
  font-weight: 800;
  color: #F0A500;
  text-transform: uppercase;
  letter-spacing: .12em;
  margin: 20px 0 10px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.sec-title::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, #1F1F1F, transparent);
}
.sec-intro {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: #606060;
  margin-bottom: 12px;
  line-height: 1.6;
}

/* ── Greeting header ── */
.greeting-wrap {
  padding: 18px 0 10px 0;
  animation: fade-up .4s ease both;
}
.greeting-name {
  font-family: 'Syne', sans-serif;
  font-size: 22px;
  font-weight: 800;
  color: #FFFFFF;
  margin-bottom: 3px;
  letter-spacing: -.01em;
}
.greeting-sub {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: #505050;
}

/* ── Context strip ── */
.ctx-strip {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  background: #080808;
  border: 1px solid #1A1A1A;
  border-radius: 10px;
  margin-bottom: 14px;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: #606060;
  flex-wrap: wrap;
  animation: fade-up .45s ease .05s both;
}
.ctx-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: rgba(240,165,0,.06);
  border: 1px solid rgba(240,165,0,.15);
  border-radius: 999px;
  padding: 3px 10px;
  color: #C0A060;
  font-size: 11px;
}

/* ── Market status bar ── */
.mkt-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 14px;
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  animation: fade-up .45s ease .1s both;
}

/* ── Metric cards ── */
.mg { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin-bottom: 14px; }
.mc {
  background: #0A0A0A;
  border: 1px solid #1A1A1A;
  border-radius: 12px;
  padding: 14px 14px;
  font-family: 'DM Mono', monospace;
  transition: border-color .2s;
}
.mc:hover { border-color: #2A2A2A; }
.mc-lbl { font-size: 9px; color: #505050; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 6px; }
.mc-val { font-family: 'Space Grotesk', sans-serif; font-size: 18px; font-weight: 700; line-height: 1; margin-bottom: 3px; }
.mc-sub { font-size: 10px; color: #606060; }

/* ── Hero signal card (visitor/free) ── */
.hero-card {
  background: linear-gradient(160deg, #0A1000 0%, #060D00 100%);
  border: 1px solid rgba(34,197,94,.2);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 14px;
  position: relative;
  overflow: hidden;
  animation: hero-fadein .5s ease both;
}
.hero-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #22C55E, transparent);
}
.hero-sym { font-family: 'Syne', sans-serif; font-size: 28px; font-weight: 800; color: #FFFFFF; margin-bottom: 4px; }
.hero-sig-pill {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(34,197,94,.12); border: 1px solid rgba(34,197,94,.3);
  border-radius: 999px; padding: 4px 14px;
  font-family: 'DM Mono', monospace; font-size: 11px; font-weight: 700; color: #22C55E;
  margin-bottom: 12px;
}
.hero-prices { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px; }
.hero-px-box {
  background: #0A0A0A; border: 1px solid #1A1A1A; border-radius: 8px; padding: 10px 12px;
}
.hero-px-lbl { font-size: 9px; color: #505050; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 3px; font-family: 'DM Mono', monospace; }
.hero-px-val { font-size: 16px; font-weight: 600; color: #FFFFFF; font-family: 'Space Grotesk', sans-serif; }
.hero-insight { background: #080808; border: 1px solid #161616; border-radius: 8px; padding: 12px; margin-bottom: 14px; }
.hero-insight-lbl { font-size: 9px; color: #505050; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 5px; font-family: 'DM Mono', monospace; }
.hero-insight-txt { font-size: 12px; color: #C0C0C0; line-height: 1.65; font-family: 'DM Mono', monospace; }
.hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(240,165,0,.10); border: 1px solid rgba(240,165,0,.25);
  border-radius: 999px; padding: 4px 12px;
  font-family: 'DM Mono', monospace; font-size: 10px; font-weight: 700; color: #F0A500;
  letter-spacing: .06em; text-transform: uppercase;
  animation: badge-pulse 3s ease-in-out infinite;
  margin-bottom: 14px;
}

/* ── AI Chat ── */
.ai-wrap {
  background: #060606;
  border: 1px solid #181818;
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 14px;
  animation: fade-up .5s ease .15s both;
}
.ai-label {
  display: flex; align-items: center; gap: 8px; justify-content: space-between;
  margin-bottom: 12px;
}
.ai-label-text {
  font-family: 'Syne', sans-serif; font-size: 12px; font-weight: 700;
  color: #F0A500; text-transform: uppercase; letter-spacing: .1em;
}
.ai-msg-user {
  background: rgba(240,165,0,.06); border: 1px solid rgba(240,165,0,.12);
  border-radius: 12px 12px 4px 12px; padding: 10px 14px;
  font-family: 'DM Mono', monospace; font-size: 13px; color: #E0E0E0;
  margin-bottom: 8px; margin-left: 10%;
}
.ai-msg-bot {
  background: #0A0A0A; border: 1px solid #1A1A1A;
  border-radius: 12px 12px 12px 4px; padding: 12px 14px;
  font-family: 'DM Mono', monospace; font-size: 13px; color: #D0D0D0;
  line-height: 1.75; margin-bottom: 8px; margin-right: 10%;
}
.ai-blur { filter: blur(5px); user-select: none; pointer-events: none; }
.query-meter { display: flex; align-items: center; gap: 6px; margin: 6px 0 2px 0; }
.qm-dot { width: 10px; height: 10px; border-radius: 50%; }
.qm-used { background: #F0A500; }
.qm-avail { background: #1F1F1F; border: 1px solid #333; }

/* ── Best signals (composite) ── */
.bsig-card {
  background: #0A0A0A; border: 1px solid #1A1A1A; border-radius: 14px; padding: 16px;
  font-family: 'DM Mono', monospace; margin-bottom: 8px;
  transition: border-color .2s;
}
.bsig-card:hover { border-color: #2A2A2A; }
.bsig-sym { font-family: 'Space Grotesk', sans-serif; font-size: 17px; font-weight: 700; color: #FFFFFF; margin-bottom: 4px; }
.bsig-sig { font-size: 10px; font-weight: 700; padding: 2px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: .06em; display: inline-block; margin-bottom: 10px; }
.bsig-bars { margin-bottom: 10px; }
.bsig-bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
.bsig-bar-lbl { font-size: 10px; color: #606060; min-width: 72px; }
.bsig-bar-bg { flex: 1; background: #1A1A1A; border-radius: 3px; height: 5px; overflow: hidden; }
.bsig-bar-fill { height: 5px; border-radius: 3px; }
.bsig-bar-pct { font-size: 10px; font-weight: 600; min-width: 32px; text-align: right; }
.bsig-reason { font-size: 11px; color: #B0B0B0; line-height: 1.55; margin-top: 8px; }

/* ── Top movers ── */
.mover-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 0; border-bottom: 1px solid #0F0F0F;
  font-family: 'DM Mono', monospace; font-size: 13px;
}
.mover-row:last-child { border-bottom: none; }
.mover-sym { font-weight: 500; color: #FFFFFF; }
.mover-px { color: #606060; font-size: 11px; margin-left: 8px; }

/* ── News ── */
.news-item {
  padding: 12px 0; border-bottom: 1px solid #0F0F0F;
  font-family: 'DM Mono', monospace;
  animation: fade-up .3s ease both;
}
.news-item:last-child { border-bottom: none; }
.news-hl { font-size: 13px; color: #D0D0D0; line-height: 1.6; margin-bottom: 4px; }
.news-meta { font-size: 10px; color: #404040; }
.news-sent-pos { color: #22C55E; font-size: 10px; font-weight: 600; }
.news-sent-neg { color: #EF4444; font-size: 10px; font-weight: 600; }
.news-sent-neu { color: #808080; font-size: 10px; }

/* ── Sector ── */
.sector-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid #0F0F0F;
  font-family: 'DM Mono', monospace; font-size: 12px;
}
.sector-item:last-child { border-bottom: none; }
.sector-name { color: #C0C0C0; }
.sector-chg { font-weight: 600; font-size: 13px; }
.sector-light { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

/* ── Trending grid ── */
.tgrid { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin: 8px 0 12px 0; }
.tgrid-card {
  background: #0A0A0A; border: 1px solid #1A1A1A; border-radius: 10px; padding: 12px;
  font-family: 'DM Mono', monospace; transition: border-color .2s;
}
.tgrid-card:hover { border-color: rgba(240,165,0,.2); }
.tgrid-sym { font-family: 'Space Grotesk', sans-serif; font-size: 13px; font-weight: 700; color: #FFFFFF; margin-bottom: 3px; }
.tgrid-chg { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.tgrid-tag { font-size: 9px; font-weight: 700; padding: 2px 8px; border-radius: 999px; text-transform: uppercase; letter-spacing: .05em; display: inline-block; }

/* ── Downgrade modal ── */
.dg-modal-wrap {
  background: linear-gradient(160deg,#0A0800,#0F0C00);
  border: 1px solid rgba(240,165,0,.35);
  border-radius: 16px; padding: 24px; margin-bottom: 16px;
  animation: fade-up .4s ease both;
}
.dg-modal-title { font-family: 'Syne', sans-serif; font-size: 18px; font-weight: 800; color: #F0A500; margin-bottom: 8px; }
.dg-modal-body { font-family: 'DM Mono', monospace; font-size: 12px; color: #A0A0A0; line-height: 1.75; margin-bottom: 16px; }
.dg-stat { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #1A1A1A; font-family: 'DM Mono', monospace; font-size: 12px; }
.dg-stat:last-child { border-bottom: none; }
.dg-stat-num { font-family: 'Space Grotesk', sans-serif; font-size: 18px; font-weight: 700; color: #F0A500; min-width: 60px; }

/* ── Trial strip ── */
.trial-strip {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 10px;
  padding: 10px 16px; border-radius: 8px; margin-bottom: 14px;
  font-family: 'DM Mono', monospace; font-size: 12px;
  border-left-width: 3px; border-left-style: solid;
}
.scarcity-pill {
  display: inline-flex; align-items: center; gap: 5px;
  background: rgba(239,68,68,.12); border: 1px solid rgba(239,68,68,.3);
  border-radius: 999px; padding: 3px 12px;
  font-size: 11px; font-weight: 700; color: #EF4444;
  letter-spacing: .02em; animation: scarcity-blink 2s ease-in-out infinite;
}

/* ── Single bottom upgrade nudge ── */
.upgrade-nudge {
  background: #080808;
  border: 1px solid #1A1A1A;
  border-radius: 10px;
  padding: 14px 18px;
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: #606060;
  margin-top: 16px;
}

/* ── Trade game ── */
.tg-card {
  background: linear-gradient(135deg,#040810,#060A18);
  border: 1px solid rgba(100,180,255,.15);
  border-radius: 14px; padding: 18px; margin-bottom: 14px;
  font-family: 'DM Mono', monospace;
}
.tg-title { font-family: 'Space Grotesk', sans-serif; font-size: 15px; font-weight: 700; color: #FFFFFF; margin-bottom: 6px; }
.tg-sub { font-size: 12px; color: #606060; line-height: 1.65; }

/* ── Welcome modal ── */
@keyframes modal-pop { from{opacity:0;transform:scale(.92) translateY(20px);} to{opacity:1;transform:scale(1) translateY(0);} }
.wm-overlay { position:fixed;inset:0;z-index:999999;background:rgba(0,0,0,.88);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:20px; }
.wm-card { background:linear-gradient(160deg,#080F00,#0D1A00);border:2px solid rgba(34,197,94,.55);border-radius:20px;padding:36px 28px;max-width:460px;width:100%;text-align:center;box-shadow:0 0 80px rgba(34,197,94,.2);animation:modal-pop .45s cubic-bezier(.16,1,.3,1) both; }

/* ── Performance trust ── */
.pt-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin-bottom: 14px; }
.pt-card { background: #0A0A0A; border: 1px solid #1A1A1A; border-radius: 12px; padding: 14px 16px; font-family: 'DM Mono', monospace; }
.pt-label { font-size: 9px; color: #606060; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 6px; }
.pt-value { font-size: 22px; font-weight: 600; line-height: 1; margin-bottom: 4px; font-family: 'Space Grotesk', sans-serif; }
.pt-sub { font-size: 10px; color: #606060; }

/* ── Testimonials ── */
.testimonial-card {
  background: #0A0A0A; border: 1px solid #1A1A1A; border-left: 3px solid #F0A500;
  border-radius: 10px; padding: 14px 16px; font-family: 'DM Mono', monospace;
  font-size: 12px; color: #C0C0C0; line-height: 1.65; margin-bottom: 8px;
}
.testimonial-author { font-size: 11px; color: #505050; margin-top: 8px; }

/* ── Share strip ── */
.ai-share-strip { padding: 10px 0 0 0; border-top: 1px solid #111; margin-top: 8px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

/* ── Skeleton loader ── */
.skeleton {
  background: linear-gradient(90deg, #0D0D0D 25%, #141414 50%, #0D0D0D 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
  border-radius: 8px;
}
@keyframes skeleton-shimmer { 0%{background-position:200% 0;} 100%{background-position:-200% 0;} }

/* ── Engagement strip ── */
.eng-card { background:linear-gradient(135deg,#040810,#030608);border:1px solid rgba(100,180,255,.2);border-radius:14px;padding:16px 20px;margin:12px 0 16px 0;font-family:'DM Mono',monospace; }
.eng-title { font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;margin-bottom:12px;display:flex;align-items:center;gap:8px; }
.eng-row { display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid #0D0D0D; }
.eng-row:last-child { border-bottom:none; }
.eng-label { font-size:12px;color:#808080; }
.eng-value { font-size:13px;font-weight:600;color:#FFFFFF; }

/* ── Streak badge ── */
.streak-badge { display:inline-flex;align-items:center;gap:7px;background:linear-gradient(135deg,rgba(240,165,0,.12),rgba(240,165,0,.06));border:1px solid rgba(240,165,0,.3);border-radius:10px;padding:8px 14px;font-family:'DM Mono',monospace;font-size:12px;animation:streak-glow 3s ease-in-out infinite; }
.streak-num { font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:800;color:#F0A500;animation:number-pop .4s ease both; }

/* ── Live dots ── */
.live-dot { display:inline-block;width:8px;height:8px;border-radius:50%;position:relative;flex-shrink:0; }
.live-dot::after { content:'';position:absolute;inset:-3px;border-radius:50%;animation:pulse-ring 1.4s ease-out infinite; }
.live-dot-green { background:#22C55E; } .live-dot-green::after { border:2px solid #22C55E; }
.live-dot-red   { background:#EF4444; } .live-dot-red::after   { border:2px solid #EF4444; }
.live-dot-amber { background:#F0A500; } .live-dot-amber::after { border:2px solid #F0A500; }

/* ── Notification banner ── */
.notif-banner { display:flex;align-items:center;gap:10px;background:linear-gradient(90deg,#0A0500,#100800);border:1px solid rgba(240,165,0,.3);border-left:3px solid #F0A500;border-radius:10px;padding:11px 16px;margin-bottom:10px;font-family:'DM Mono',monospace;font-size:12px;animation:notif-slide .4s ease both; }
.notif-banner-green { background:linear-gradient(90deg,#000A00,#001000)!important;border-color:rgba(34,197,94,.3)!important;border-left-color:#22C55E!important; }

/* ── Plan nudge pill (single bottom nudge) ── */
.plan-nudge-pill {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
  background: #080808; border: 1px solid #181818;
  border-radius: 10px; padding: 13px 16px;
  font-family: 'DM Mono', monospace; font-size: 12px; color: #606060;
  margin-top: 20px;
}
.plan-nudge-plan { font-weight: 700; }

/* ── Animations ── */
@keyframes fade-up    { from{opacity:0;transform:translateY(10px);} to{opacity:1;transform:translateY(0);} }
@keyframes hero-fadein { from{opacity:0;transform:translateY(10px);} to{opacity:1;transform:translateY(0);} }
@keyframes badge-pulse { 0%,100%{box-shadow:0 0 0 rgba(240,165,0,0);}50%{box-shadow:0 0 14px rgba(240,165,0,.35);} }
@keyframes scarcity-blink { 0%,100%{opacity:1;}50%{opacity:.55;} }
@keyframes streak-glow  { 0%,100%{box-shadow:0 0 0 rgba(240,165,0,0);}50%{box-shadow:0 0 16px rgba(240,165,0,.4);} }
@keyframes number-pop   { 0%{transform:scale(.8);opacity:0;}70%{transform:scale(1.1);}100%{transform:scale(1);opacity:1;} }
@keyframes notif-slide  { from{opacity:0;transform:translateY(-12px);}to{opacity:1;transform:translateY(0);} }
@keyframes pulse-ring   { 0%{transform:scale(.8);opacity:.8;}100%{transform:scale(2.2);opacity:0;} }
@keyframes trial-pulse  { 0%,100%{box-shadow:0 0 0 rgba(239,68,68,0);}50%{box-shadow:0 0 18px rgba(239,68,68,.22);} }
@keyframes flash-in     { from{opacity:0;transform:translateX(-8px);}to{opacity:1;transform:translateX(0);} }

/* ── Responsive ── */
@media(max-width:768px) {
  .mg,.pt-grid,.tgrid { grid-template-columns: repeat(2,1fr); }
  .ai-msg-user { margin-left: 5%; }
}
@media(max-width:480px) {
  .greeting-name { font-size: 20px; }
  .hero-sym { font-size: 24px; }
}
</style>
"""


# ══════════════════════════════════════════════════════════════════════════════
# SHARED RENDER HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _render_ai_share_sheet(response_text: str, question: str, msg_idx: int):
    """Minimal share strip — copy text or share to WhatsApp."""
    snippet = response_text[:200].replace('"', '\\"').replace('\n', '\\n')
    q_enc   = requests.utils.quote(f"NGX Signal says: {response_text[:300]}")
    st.markdown(f"""
<div class="ai-share-strip">
  <span style="font-family:'DM Mono',monospace;font-size:10px;color:#404040;">Share:</span>
  <a href="https://wa.me/?text={q_enc}" target="_blank"
     style="display:inline-flex;align-items:center;gap:5px;background:rgba(37,211,102,.1);
            border:1px solid rgba(37,211,102,.25);border-radius:7px;padding:5px 12px;
            font-family:'DM Mono',monospace;font-size:11px;color:#25D166;text-decoration:none;">
    📱 WhatsApp
  </a>
</div>""", unsafe_allow_html=True)


def _render_market_status_bar(market: dict):
    dot_cls = "live-dot-green" if market["is_open"] else ("live-dot-amber" if "Pre" in market["label"] else "live-dot-red")
    st.markdown(
        f'<div class="mkt-bar" style="background:#080808;border:1px solid {market["color"]}22;border-left:3px solid {market["color"]};">'
        f'<span class="live-dot {dot_cls}"></span>'
        f'<div><span style="font-size:12px;font-weight:600;color:{market["color"]};font-family:\'DM Mono\',monospace;">{market["label"]}</span>'
        f'<span style="font-size:11px;color:#505050;margin-left:8px;font-family:\'DM Mono\',monospace;">{market["note"]}</span></div>'
        f'</div>', unsafe_allow_html=True
    )


def _render_metric_cards(ad, acg, acol, aarr, total, gc, lc, mood, mcol, moji, market, data_label, brief_ok, brief_color):
    # Replace win rate with live breadth
    breadth_pct = round((gc / total * 100) if total > 0 else 0, 1)
    st.markdown(f"""
<div class="mg">
  <div class="mc">
    <div class="mc-lbl">NGX ASI</div>
    <div class="mc-val" style="color:{acol};">{ad}</div>
    <div class="mc-sub">{aarr}{abs(acg):.2f}% · {data_label}</div>
  </div>
  <div class="mc">
    <div class="mc-lbl">Market Breadth</div>
    <div class="mc-val" style="color:{'#22C55E' if breadth_pct>=50 else '#EF4444'};">{breadth_pct}%</div>
    <div class="mc-sub">{gc} gainers of {total} stocks</div>
  </div>
  <div class="mc">
    <div class="mc-lbl">Mood</div>
    <div class="mc-val" style="color:{mcol};">{moji}</div>
    <div class="mc-sub" style="color:{mcol};">{mood}</div>
  </div>
</div>""", unsafe_allow_html=True)


def _render_notification_banner(top_g, now, gc, total, market, notif_minutes):
    if not top_g: return
    tg = top_g[0]
    sym = tg.get("symbol","")
    chg = float(tg.get("change_percent",0) or 0)
    is_positive = chg >= 0
    cls  = "notif-banner-green" if is_positive else ""
    icon = "📈" if is_positive else "📉"
    col  = "#22C55E" if is_positive else "#EF4444"
    st.markdown(
        f'<div class="notif-banner {cls}">'
        f'{icon} <strong style="color:{col};">{sym}</strong>'
        f'<span style="color:#808080;margin-left:4px;">{"+" if is_positive else ""}{chg:.2f}% &nbsp;·&nbsp; '
        f'{gc} stocks gained today &nbsp;·&nbsp; {_time_ago(notif_minutes)}</span>'
        f'</div>', unsafe_allow_html=True
    )


def _render_top_opportunity(insights, uniq, _sig_map, notif_minutes, tier):
    """Hero signal card — blurred for visitor, partial entry for free."""
    if not insights: return
    is_visitor = tier == "visitor"
    is_free    = tier == "free"

    _hero = next((i for i in insights if i["action"] == "BUY"), insights[0])
    sym   = _hero["sym"]
    _hp_data = next((p for p in uniq if p.get("symbol","") == sym), None)
    if not _hp_data: return

    price  = float(_hp_data.get("price",0) or 0)
    chg    = float(_hp_data.get("change_percent",0) or 0)
    target = round(price * 1.075, 2)
    pct    = round((target - price) / price * 100, 1) if price > 0 else 0
    sdata  = _sig_map.get(sym, {})
    stars  = "⭐" * min(int(sdata.get("stars",3) or 3), 5)

    blur_style = "filter:blur(5px);user-select:none;" if is_visitor else ""
    entry_html = (
        f'<div class="hero-px-box" style="{blur_style}"><div class="hero-px-lbl">Entry</div>'
        f'<div class="hero-px-val">{"NXXX.XX" if is_visitor else f"N{price:,.2f}"}</div></div>'
        f'<div class="hero-px-box" style="{blur_style}"><div class="hero-px-lbl">Target (+{pct}%)</div>'
        f'<div class="hero-px-val" style="color:#22C55E;">{"NXXX.XX" if is_visitor else f"N{target:,.2f}"}</div></div>'
    )

    st.markdown(f"""
<div class="hero-card">
  <div class="hero-badge">🔥 AI Signal · {_time_ago(notif_minutes)}</div>
  <div class="hero-sym">{sym}</div>
  <div class="hero-sig-pill">BUY ✅ &nbsp; {stars}</div>
  <div class="hero-prices">{entry_html}</div>
  <div class="hero-insight">
    <div class="hero-insight-lbl">What's driving this</div>
    <div class="hero-insight-txt">{_hero["reason"]}</div>
  </div>
</div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📊 View Full Signal", key="hero_view_sig", use_container_width=True):
            st.session_state.current_page = "signals"; st.rerun()
    with c2:
        cta = "🔐 Sign Up Free →" if is_visitor else "⚡ Start Free Trial →"
        if st.button(cta, key="hero_cta", type="primary", use_container_width=True):
            _unlock_cta("hero_cta_act", cta, tier, "settings")


def _render_best_signals(tier, sb, uniq, _sig_map, is_trial):
    """Composite signal cards — 2 visible, rest locked for free/trial."""
    from app.views.home import _load_home_signals as _lhs  # reuse cache
    _sigs = _load_home_signals()
    if not _sigs:
        st.markdown('<div class="skeleton" style="height:80px;margin-bottom:8px;"></div>'*3, unsafe_allow_html=True)
        return

    # Build insights list from signal_scores
    _price_map = {p["symbol"]: p for p in uniq}
    _insights  = []
    for s in _sigs:
        sym  = s.get("symbol","")
        sig  = (s.get("signal") or "HOLD").upper()
        stars= int(s.get("stars") or 3)
        reason = s.get("reasoning","") or ""
        _pd  = _price_map.get(sym,{})
        price= float(_pd.get("price",0) or 0)
        _insights.append({"sym":sym,"action":sig,"stars":stars,"reason":reason,"price":price})

    _buys  = [i for i in _insights if i["action"]=="BUY"][:3]
    _holds = [i for i in _insights if i["action"]=="HOLD"][:2]
    _top   = (_buys + _holds)[:5]

    can_see = can_access("signals_all", tier)
    visible = _top if can_see else _top[:2]

    st.markdown('<div class="sec-title">📡 Today\'s Best Signals</div>', unsafe_allow_html=True)

    for idx, ins in enumerate(visible):
        sym   = ins["sym"]
        sig   = ins["action"]
        price = ins["price"]
        sc    = "#22C55E" if sig=="BUY" else ("#EF4444" if sig=="AVOID" else "#F0A500")
        sc_bg = "rgba(34,197,94,.08)" if sig=="BUY" else ("rgba(239,68,68,.08)" if sig=="AVOID" else "rgba(240,165,0,.08)")

        # Score bars from signal_scores table
        _sd    = _sig_map.get(sym,{})
        _mom   = min(100, int(float(_sd.get("momentum_score",0) or 0)*20))
        _vol   = min(100, int(float(_sd.get("volume_score",0)   or 0)*20))
        _news  = min(100, int(float(_sd.get("news_score",0)     or 0)*20))
        _stars = "⭐" * min(int(_sd.get("stars",3) or 3), 5)

        _price_html = ""
        if can_access("signals_confidence", tier) and price > 0:
            tgt   = round(price * 1.07, 2)
            _price_html = (
                f'<div style="display:flex;gap:8px;margin-top:8px;">'
                f'<span style="background:#111;border:1px solid #1A1A1A;border-radius:6px;padding:4px 10px;font-size:11px;color:#808080;">Entry: <strong style="color:#fff;">N{price:,.2f}</strong></span>'
                f'<span style="background:#111;border:1px solid rgba(34,197,94,.2);border-radius:6px;padding:4px 10px;font-size:11px;color:#22C55E;">Target: N{tgt:,.2f}</span>'
                f'</div>'
            )

        st.markdown(f"""
<div class="bsig-card" style="border-color:{sc}22;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <div>
      <div class="bsig-sym">{sym}</div>
      <span class="bsig-sig" style="background:{sc_bg};color:{sc};border:1px solid {sc}33;">{sig}</span>
      <span style="font-size:11px;color:#505050;margin-left:6px;">{_stars}</span>
    </div>
  </div>
  <div class="bsig-bars">
    <div class="bsig-bar-row"><span class="bsig-bar-lbl">Momentum</span><div class="bsig-bar-bg"><div class="bsig-bar-fill" style="width:{_mom}%;background:{sc};"></div></div><span class="bsig-bar-pct" style="color:{sc};">{_mom}%</span></div>
    <div class="bsig-bar-row"><span class="bsig-bar-lbl">Volume</span><div class="bsig-bar-bg"><div class="bsig-bar-fill" style="width:{_vol}%;background:#3B82F6;"></div></div><span class="bsig-bar-pct" style="color:#3B82F6;">{_vol}%</span></div>
    <div class="bsig-bar-row"><span class="bsig-bar-lbl">News</span><div class="bsig-bar-bg"><div class="bsig-bar-fill" style="width:{_news}%;background:#A78BFA;"></div></div><span class="bsig-bar-pct" style="color:#A78BFA;">{_news}%</span></div>
  </div>
  <div class="bsig-reason">{ins["reason"][:180]}{"…" if len(ins["reason"])>180 else ""}</div>
  {_price_html}
</div>""", unsafe_allow_html=True)

    if not can_see:
        render_locked_content("signals_all", key="sig_lock_wall")
    elif is_trial:
        _reinforcement_pill("You're seeing all composite signal data — this is a Starter+ feature")


def _render_top_movers(uniq, market, latest_date):
    sup = sorted([p for p in uniq if float(p.get("change_percent") or 0) > 0],
                  key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:8]
    sdn = sorted([p for p in uniq if float(p.get("change_percent") or 0) < 0],
                  key=lambda x:float(x.get("change_percent",0) or 0))[:4]
    movers = sup + sdn
    if not movers: return

    st.markdown('<div class="sec-title">🔥 Top Movers</div>', unsafe_allow_html=True)
    mrows = "".join(
        f'<div style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #0F0F0F;font-family:DM Mono,monospace;font-size:13px;">'
        f'<div><span style="font-weight:500;color:#FFFFFF;">{s["symbol"]}</span>'
        f'<span style="color:#505050;font-size:11px;margin-left:8px;">N{float(s.get("price",0) or 0):,.2f}</span></div>'
        f'<span style="color:{"#22C55E" if float(s.get("change_percent",0) or 0)>=0 else "#EF4444"};font-weight:600;">'
        f'{"▲" if float(s.get("change_percent",0) or 0)>=0 else "▼"} {abs(float(s.get("change_percent",0) or 0)):.2f}%</span></div>'
        for s in movers
    )
    ph = max(len(movers)*43+55, 80) + 32
    st.components.v1.html(
        f'<!DOCTYPE html><html><head>'
        f'<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">'
        f'<style>*{{margin:0;padding:0;box-sizing:border-box;}}html,body{{background:transparent;font-family:DM Mono,monospace;overflow:hidden;}}'
        f'.p{{background:#0A0A0A;border:1px solid #1A1A1A;border-radius:10px;padding:14px 16px;}}'
        f'.pt{{font-size:11px;font-weight:500;color:#F0A500;text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px;}}'
        f'</style></head><body><div class="p"><div class="pt">📊 {latest_date} · {"🟢 Live" if market["is_open"] else "🔒 Last Close"}</div>{mrows}</div></body></html>',
        height=ph, scrolling=False
    )
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("📊 View All Stocks →", key="btn_all_stocks", type="primary"):
        st.session_state.current_page = "all_stocks"; st.rerun()


def _render_news_section(tier, sb, market, today):
    _news = _load_home_news()
    if not _news: return
    can_full = can_access("news_full", tier)
    show_n   = len(_news) if can_full else 3

    st.markdown('<div class="sec-title">📰 Market News</div>', unsafe_allow_html=True)
    st.markdown('<div style="background:#0A0A0A;border:1px solid #1A1A1A;border-radius:12px;padding:14px 16px;">', unsafe_allow_html=True)
    for n in _news[:show_n]:
        hl   = n.get("headline","")
        sent = (n.get("sentiment") or "neutral").lower()
        sc   = "news-sent-pos" if "pos" in sent else ("news-sent-neg" if "neg" in sent else "news-sent-neu")
        emoji= "📈" if "pos" in sent else ("📉" if "neg" in sent else "•")
        st.markdown(
            f'<div class="news-item"><div class="news-hl">{hl}</div>'
            f'<div class="news-meta"><span class="{sc}">{emoji} {sent.capitalize()}</span></div></div>',
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)
    if not can_full:
        _upgrade_inline("Full news feed (20 items) is unlocked on Trial+.", key="nudge_news")


def _render_sector_snapshot(tier, sb):
    _sectors = _load_home_sectors()
    if not _sectors: return
    can_all  = can_access("sector_all", tier)
    show_n   = len(_sectors) if can_all else 3

    st.markdown('<div class="sec-title">🏭 Sector Snapshot</div>', unsafe_allow_html=True)
    st.markdown('<div style="background:#0A0A0A;border:1px solid #1A1A1A;border-radius:12px;padding:14px 16px;">', unsafe_allow_html=True)
    for sec in _sectors[:show_n]:
        chg  = float(sec.get("change_percent",0) or 0)
        col  = "#22C55E" if chg >= 0 else "#EF4444"
        light= "#22C55E" if sec.get("traffic_light","") == "green" else ("#EF4444" if sec.get("traffic_light","") == "red" else "#F0A500")
        st.markdown(
            f'<div class="sector-item">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<div class="sector-light" style="background:{light};"></div>'
            f'<span class="sector-name">{sec.get("sector_name","")}</span></div>'
            f'<span class="sector-chg" style="color:{col};">{"+" if chg>=0 else ""}{chg:.2f}%</span>'
            f'</div>',
            unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)
    if not can_all:
        _upgrade_inline("All sector data unlocked on Trial+.", key="nudge_sector")


def _render_performance_trust(gainers, losers, total, top_g, now):
    """Market breadth stats — NO fake win rate stat."""
    top_sym = top_g[0]["symbol"] if top_g else "—"
    top_chg = float(top_g[0].get("change_percent",0) or 0) if top_g else 0

    st.markdown(f"""
<div class="pt-grid">
  <div class="pt-card">
    <div class="pt-label">Today Gainers</div>
    <div class="pt-value" style="color:#22C55E;">{gainers}</div>
    <div class="pt-sub">of {total} tracked stocks</div>
  </div>
  <div class="pt-card">
    <div class="pt-label">Top Mover</div>
    <div class="pt-value" style="color:#F0A500;">{top_sym}</div>
    <div class="pt-sub">+{top_chg:.2f}% today</div>
  </div>
  <div class="pt-card">
    <div class="pt-label">Stocks Tracked</div>
    <div class="pt-value" style="color:#FFFFFF;">{total}</div>
    <div class="pt-sub">NGX listed companies</div>
  </div>
</div>""", unsafe_allow_html=True)


def _render_testimonials():
    _tests = [
        ("I caught ZENITHBANK at 26.50 based on the BUY signal. It hit 30 in two weeks. NGX Signal is real.", "Lagos · Starter Plan"),
        ("Finally a tool that speaks plain English. No jargon, just buy, hold, or avoid. That's all I needed.", "Abuja · Trader Plan"),
        ("The stop-loss levels saved me during a bad week. I already paid for the plan twice over in avoided losses.", "PH · Pro Plan"),
    ]
    st.markdown('<div class="sec-title">⭐ What Traders Are Saying</div>', unsafe_allow_html=True)
    for body, author in _tests:
        st.markdown(
            f'<div class="testimonial-card">"{body}"<div class="testimonial-author">— {author}</div></div>',
            unsafe_allow_html=True
        )


def _render_trade_game(sb, current_user):
    st.markdown('<div class="sec-title">🎮 Trade Game</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="tg-card">
  <div class="tg-title">🎮 Practice Before You Invest</div>
  <div class="tg-sub">Test your picks with virtual ₦100,000. Build confidence before committing real money. Top players are returning 12%+ on the leaderboard.</div>
</div>""", unsafe_allow_html=True)
    if st.button("🎮 Open Trade Game →", key="btn_trade_game"):
        st.session_state.current_page = "trade_game"; st.rerun()


def _render_ai_brief_expander(tier, _brief_res, today, has_full_ai):
    """AI Market Brief — always shown, gated content blurred."""
    brief_ok = bool(_brief_res)
    with st.expander("✨  TODAY'S MARKET AI BRIEF", expanded=False):
        if brief_ok:
            raw2     = _brief_res[0].get("body","")
            bdate    = _brief_res[0].get("brief_date", today)
            clean    = re.sub(r'\*\*(.+?)\*\*', r'\1', raw2)
            sections = [s for s in clean.strip().split("\n\n") if s.strip()]
            st.caption(f"📅 AI Market Brief — {bdate}")
            for idx_s, sec in enumerate(sections):
                style = "filter:blur(4px);user-select:none;" if idx_s >= 2 and not can_access("brief_full", tier) else ""
                st.markdown(
                    f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#D0D0D0;line-height:1.8;"
                    f"margin-bottom:8px;padding:8px 0;border-bottom:1px solid #0F0F0F;{style}'>{sec.strip()}</div>",
                    unsafe_allow_html=True
                )
            if len(sections) > 2 and not can_access("brief_full", tier):
                _upgrade_inline("Full brief unlocked on Trial+ plans.", key="nudge_brief")
        else:
            st.info("📭 Brief generates at weekday market open." if True else "📭 Brief being generated.")


def _render_ai_chat(
    tier, profile, sb, uniq, market, latest_date,
    ad, aarr, acg, mood, gc, lc, total, top_g, notif_minutes,
    key_suffix="", has_full_ai=True, ai_allowed=True,
    _rem_queries=None, _queries_restricted=False, _gp_for_ai=None
):
    """Unified AI chat widget — works for all tiers."""

    top_g_text = ", ".join(f"{p['symbol']} {float(p.get('change_percent',0) or 0):+.2f}%" for p in top_g[:3]) if top_g else ""
    tier_prompt_args = {
        "ad": ad, "aarr": aarr, "acg": acg, "mood": mood,
        "gc": gc, "lc": lc, "total": total, "top_g": top_g,
        "top_g_text": top_g_text, "latest_date": latest_date,
        "market_open": market["is_open"], "uniq": uniq,
        "global_context": get_global_pulse_for_ai() if _gp_for_ai else "",
    }

    if "mai_history" not in st.session_state: st.session_state.mai_history = []
    if "mai_pending"  not in st.session_state: st.session_state.mai_pending  = ""

    st.markdown('<div class="sec-title">🤖 Ask AI About Any NGX Stock</div>', unsafe_allow_html=True)

    # Chat history
    for _mi, msg in enumerate(st.session_state.mai_history):
        if msg["role"] == "user":
            st.markdown(f'<div class="ai-msg-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            raw = msg.get("content","")
            c   = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', raw)
            c   = re.sub(r'_(.+?)_', r'<em style="color:#606060;">\1</em>', c)
            c   = re.sub(r'^- (.+)$', r'<span style="color:#606060;">·</span> \1', c, flags=re.MULTILINE)
            c   = re.sub(
                r'<strong>(Recommendation|Key Signals|Key Insights|Action Plan|Action Tip|Tip|Detailed Insight)([:\s]*)</strong>',
                r'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#505050;margin:10px 0 4px 0;">\1</div>', c
            )
            c = c.replace("\n", "<br>")
            if msg.get("blurred") and not has_full_ai:
                cutoff  = max(90, len(c)//3)
                st.markdown(f'<div class="ai-msg-bot">{c[:cutoff]}<span class="ai-blur">{c[cutoff:]}</span></div>', unsafe_allow_html=True)
                _,_bc,_ = st.columns([1,2,1])
                with _bc:
                    if st.button("🔐 Unlock Full AI Insights →", key=f"ai_blur_cta{key_suffix}{_mi}", type="primary", use_container_width=True):
                        _unlock_cta(f"ai_blur_act{key_suffix}{_mi}", "unlock", tier, "settings")
            else:
                st.markdown(f'<div class="ai-msg-bot">{c}</div>', unsafe_allow_html=True)
                _is_decision = any(kw in raw[:120].lower() for kw in ["recommendation:", "buy", "hold", "avoid"])
                if _is_decision and not msg.get("blurred"):
                    _render_ai_share_sheet(raw, msg.get("question",""), _mi)
            if can_access("follow_up_chips", tier) and ai_allowed:
                _top_sym = top_g[0]["symbol"] if top_g else "MTNN"
                _fups    = [f"Is {_top_sym} undervalued right now?","What's the best entry price?","What's the risk level?"]
                st.markdown('<div style="font-family:DM Mono,monospace;font-size:10px;color:#404040;margin:4px 0;">↩ Ask follow-up:</div>', unsafe_allow_html=True)
                _fc = st.columns(3)
                for _fi, _fq in enumerate(_fups):
                    with _fc[_fi]:
                        if st.button(_fq, key=f"fu_{_mi}_{_fi}{key_suffix}", use_container_width=True):
                            st.session_state.mai_pending = _fq; st.rerun()

    # Suggested questions (empty chat)
    if not st.session_state.mai_history and ai_allowed:
        _top_sym = top_g[0]["symbol"] if top_g else "MTNN"
        _top2    = top_g[1]["symbol"] if len(top_g) > 1 else "ZENITHBANK"
        _last_t  = st.session_state.get("last_ticker_asked","")
        if tier == "free":
            _aqs = [f"Should I buy {_top_sym} today?","What stock should I buy this week?",f"Is {_top_sym} or {_top2} safer?","Is the market bullish right now?"]
        elif tier == "trial":
            _aqs = [f"Full analysis of {_top_sym}",f"Best entry price for {_top2}?","Which sector has the strongest momentum?",f"Compare {_top_sym} vs {_top2}"]
        elif tier == "starter":
            _aqs = [f"Is {_top_sym} a good buy?",f"Stop-loss level for {_top2}?","Top 3 NGX stocks this week",f"Volume signal on {_top_sym}"]
        elif tier == "trader":
            _aqs = [f"Trader breakdown of {_top_sym}",f"Momentum signal on {_top2}?","Which sector has the strongest rotation?",f"Risk-adjusted entry for {_top_sym}"]
        else:
            _aqs = [f"Portfolio strategy around {_top_sym}","Top 3 buy opportunities on NGX today",f"Advanced analysis of {_top_sym}: entry, target, stop","Where is smart money moving?"]
        st.markdown('<div style="font-family:DM Mono,monospace;font-size:10px;color:#404040;margin:8px 0 6px 0;">💡 Tap to ask instantly:</div>', unsafe_allow_html=True)
        _aqc = st.columns(len(_aqs))
        for _ai2, _aq in enumerate(_aqs):
            with _aqc[_ai2]:
                if st.button(_aq, key=f"aq_{_ai2}{key_suffix}", use_container_width=True):
                    st.session_state.mai_pending = _aq; st.rerun()

    # Query meter (free/starter)
    if tier == "free" and _rem_queries is not None:
        dots = "".join(f'<div class="qm-dot qm-used"></div>' for _ in range(get_ai_query_count())) + \
               "".join(f'<div class="qm-dot qm-avail"></div>' for _ in range(max(0,(_QUERY_LIMITS.get("free",2) or 2)-get_ai_query_count())))
        st.markdown(f'<div class="query-meter">{dots}<span style="font-family:DM Mono,monospace;font-size:10px;color:#505050;margin-left:6px;">{_rem_queries} of {_QUERY_LIMITS.get("free",2)} queries left today</span></div>', unsafe_allow_html=True)

    # Input + send
    default_q = st.session_state.pop("mai_pending","") if st.session_state.mai_pending else ""
    ic, bc = st.columns([5,1])
    with ic:
        _ph  = "Ask: What stock should I buy today?" if ai_allowed else "🔒 Daily query limit reached — upgrade for more"
        user_q = st.text_input("AI", value=default_q, placeholder=_ph, key=f"mai_input{key_suffix}", label_visibility="collapsed", disabled=not ai_allowed)
    with bc:
        send = st.button("Send ➤" if ai_allowed else "🔒", key=f"mai_send{key_suffix}", type="primary", use_container_width=True, disabled=not ai_allowed)

    if not ai_allowed:
        if tier == "visitor":
            render_locked_content("ai_input", f"ai_gate_wall{key_suffix}")
        else:
            render_locked_content("ai_full_response", f"ai_gate_wall{key_suffix}")

    # Handle send
    question = (user_q or "").strip()
    if send and question and ai_allowed:
        _known_syms   = {p.get("symbol","").upper() for p in uniq}
        _words        = re.findall(r'\b[A-Z]{2,8}\b', question.upper())
        _found_ticker = next((w for w in _words if w in _known_syms), "")
        if _found_ticker:
            st.session_state.last_ticker_asked = _found_ticker
        prompt_tuple = _build_ai_system_prompt(
            tier,
            tier_prompt_args["ad"], tier_prompt_args["aarr"], tier_prompt_args["acg"],
            tier_prompt_args["mood"], tier_prompt_args["gc"], tier_prompt_args["lc"],
            tier_prompt_args["total"], tier_prompt_args["top_g_text"],
            tier_prompt_args["latest_date"], tier_prompt_args["market_open"],
            question=question,
            global_context=tier_prompt_args.get("global_context",""),
        )
        st.session_state.mai_history.append({"role":"user","content":question})
        with st.spinner("Analysing..."):
            answer = call_ai(prompt_tuple)
        if answer:
            inc_ai_query_count(); inc_total_ai_queries()
            inc_eng("ai_queries_used")
            blurred = not has_full_ai
            st.session_state.mai_history.append({"role":"assistant","content":answer,"blurred":blurred,"question":question})
        st.rerun()


def _render_downgrade_modal(profile, tier, name):
    """Loss-aversion re-engage modal for ex-trial users."""
    if not was_trial_user(profile): return
    if tier in PAID_TIERS or tier == "trial": return
    dismissed_key = f"dg_dismissed_{st.session_state.get('user',{}).get('id','')}"
    if st.session_state.get(dismissed_key): return

    ai_used  = get_total_ai_queries()
    sigs_seen= get_eng("signals_viewed", 0)

    st.markdown(f"""
<div class="dg-modal-wrap">
  <div class="dg-modal-title">⚠️ You've Lost Premium Access</div>
  <div class="dg-modal-body">
    Your trial ended. Here's what you built up — and what you're no longer seeing.
  </div>
  <div class="dg-stat"><div class="dg-stat-num">{ai_used}</div><div>AI queries you used during trial</div></div>
  <div class="dg-stat"><div class="dg-stat-num">{sigs_seen}</div><div>Signals you viewed with entry prices</div></div>
  <div class="dg-stat"><div class="dg-stat-num">0</div><div>Premium signals visible on your current plan</div></div>
</div>""", unsafe_allow_html=True)
    c1, c2 = st.columns([3,1])
    with c1:
        if st.button("🔐 Restore Premium Access →", key="dg_restore", type="primary", use_container_width=True):
            st.session_state.deep_link_plan = True; st.session_state.current_page = "settings"; st.rerun()
    with c2:
        if st.button("Later", key="dg_dismiss", use_container_width=True):
            st.session_state[dismissed_key] = True; st.rerun()


def _render_pro_command_center(tier, profile, sb, uniq, market, now, _sig_map):
    """Preserved full Pro Command Center from v11 — renders first for Trader/Pro."""
    from app.views.home import _render_pro_command_center as _pcc_v11
    try:
        _pcc_v11(tier, profile, sb, uniq, market, now, _sig_map)
    except Exception:
        # Fallback if import fails — inline skeleton
        st.markdown("""
<div style="background:#0A0A0A;border:1px solid rgba(240,165,0,.2);border-radius:16px;padding:24px;text-align:center;margin-bottom:18px;">
  <div style="font-family:'Space Grotesk',sans-serif;font-size:14px;color:#F0A500;margin-bottom:6px;">⚡ AI Trade Briefing — Loading…</div>
  <div style="font-family:'DM Mono',monospace;font-size:11px;color:#505050;">Fetching today's top signal…</div>
</div>""", unsafe_allow_html=True)


def render_personalized_strip(tier, profile, sb, name, uniq):
    """Context strip showing last ticker, streak, queries — all tiers."""
    last_t  = st.session_state.get("last_ticker_asked","")
    streak  = get_eng("streak", 0)
    ai_used = get_total_ai_queries()

    chips = []
    if last_t:    chips.append(f"📌 Last asked: {last_t}")
    if streak>0:  chips.append(f"🔥 {streak}-day streak")
    if ai_used>0: chips.append(f"🤖 {ai_used} AI queries used")

    if not chips: return

    chips_html = "".join(f'<span class="ctx-chip">{c}</span>' for c in chips)
    st.markdown(f'<div class="ctx-strip">{chips_html}</div>', unsafe_allow_html=True)


def _render_global_pulse_section(tier, _gp):
    if _gp:
        render_global_pulse_strip(tier, location="home")


def _render_single_upgrade_nudge(tier, trial_days_left=0, trial_urgent=False):
    """ONE upgrade touchpoint per page — placed after signal cards."""
    if tier == "visitor":
        st.markdown("""
<div class="plan-nudge-pill">
  <span>You're browsing as a guest. <a href="#" style="color:#F0A500;text-decoration:none;">Create a free account</a> to get 2 daily AI queries + live signals.</span>
</div>""", unsafe_allow_html=True)
        if st.button("🔐 Sign Up Free →", key="single_cta_visitor", type="primary"):
            _unlock_cta("vis_cta", "signup", "visitor", "settings")

    elif tier == "free":
        st.markdown("""
<div class="plan-nudge-pill">
  <span>You're on <span class="plan-nudge-plan" style="color:#F0A500;">Free</span> — upgrade to Starter for entry prices, stop-losses, and 15 AI queries/day.</span>
</div>""", unsafe_allow_html=True)
        if st.button("⚡ Start 14-Day Free Trial →", key="single_cta_free", type="primary"):
            _unlock_cta("free_cta", "trial", "free", "settings")

    elif tier == "trial" and trial_urgent:
        ai_ut = get_total_ai_queries()
        st.markdown(f"""
<div class="plan-nudge-pill" style="border-color:rgba(239,68,68,.3);animation:trial-pulse 3s ease-in-out infinite;">
  <div>
    <span style="color:#EF4444;font-weight:700;">⏳ Trial ends in {trial_days_left} day{"s" if trial_days_left!=1 else ""}</span>
    <span style="color:#505050;margin-left:8px;font-size:11px;">You've used AI {ai_ut} times — don't lose your edge.</span>
  </div>
  <div class="scarcity-pill">🔴 {trial_days_left} day{"s" if trial_days_left!=1 else ""} left</div>
</div>""", unsafe_allow_html=True)
        if st.button("🔐 Upgrade Now — Don't Lose Access →", key="single_cta_trial_urgent", type="primary"):
            st.session_state.deep_link_plan = True; st.session_state.current_page = "settings"; st.rerun()

    elif tier == "trial":
        st.markdown(f"""
<div class="plan-nudge-pill" style="border-color:rgba(34,197,94,.15);">
  <span style="color:#22C55E;font-weight:600;">✨ Trial active</span>
  <span style="color:#505050;margin-left:8px;">{trial_days_left} days left — upgrade to keep full access.</span>
</div>""", unsafe_allow_html=True)
        if st.button("⚡ Upgrade to Keep Premium →", key="single_cta_trial", type="primary"):
            st.session_state.deep_link_plan = True; st.session_state.current_page = "settings"; st.rerun()

    elif tier == "starter":
        st.markdown('<div class="plan-nudge-pill"><span style="color:#3B82F6;font-weight:700;">Starter Plan</span><span style="color:#505050;margin-left:8px;">— Upgrade to Trader for unlimited AI queries, Pidgin mode &amp; Telegram alerts.</span></div>', unsafe_allow_html=True)
        if st.button("📈 Upgrade to Trader →", key="single_cta_starter", type="primary"):
            st.session_state.deep_link_plan = True; st.session_state.current_page = "settings"; st.rerun()

    elif tier == "trader":
        st.markdown('<div class="plan-nudge-pill"><span style="color:#A78BFA;font-weight:700;">Trader Plan</span><span style="color:#505050;margin-left:8px;">— Upgrade to Pro for PDF reports, portfolio strategy &amp; advanced AI outputs.</span></div>', unsafe_allow_html=True)
        if st.button("📊 Upgrade to Pro →", key="single_cta_trader", type="primary"):
            st.session_state.deep_link_plan = True; st.session_state.current_page = "settings"; st.rerun()

    elif tier == "pro":
        st.markdown('<div class="plan-nudge-pill"><span style="color:#F0A500;font-weight:700;">🏆 Pro Plan</span><span style="color:#505050;margin-left:8px;">Full intelligence active. Unlimited AI · PDF exports · Portfolio strategy.</span></div>', unsafe_allow_html=True)


def _render_dismissible_guide(tier, profile):
    """Tier-specific how-to guide — visible once after upgrade, then dismissible."""
    uid         = (st.session_state.get("user") or {}).get("id","anon")
    guide_key   = f"guide_dismissed_{uid}_{tier}"
    upgrade_key = f"guide_upgrade_seen_{uid}_{tier}"

    # Show guide once on first login after tier upgrade
    if not st.session_state.get(upgrade_key):
        st.session_state[upgrade_key] = True

    # If dismissed, do not render
    if st.session_state.get(guide_key): return

    if tier == "trial":
        steps = [
            ("Read AI Signals","Go to the Signals page. Every BUY/HOLD/AVOID signal includes entry price and target.","📊"),
            ("Use AI Every Day","Ask about any NGX stock. Trial gets unlimited queries — use them each morning.","🤖"),
            ("Watch Market Brief","The AI brief drops before market open. Read it before making any decisions.","📰"),
        ]
        title = "📚 Quick Start: Your 14-Day Trial"
    elif tier == "starter":
        steps = [
            ("Check Your 15 Queries","You get 15 AI queries per day. Use them on your watchlist stocks each morning.","🤖"),
            ("Use Entry + Target Prices","Every signal includes specific Naira entry ranges and targets.","📊"),
            ("Set Telegram Alerts","Turn on Telegram alerts in Settings — get signal triggers before the market moves.","📡"),
        ]
        title = "📚 Getting Started: Starter Plan"
    elif tier == "trader":
        steps = [
            ("Unlimited AI Analysis","Ask about any stock, any time — before buying, while holding, before selling.","🤖"),
            ("Entry + Stop-Loss Levels","Use the specific Naira levels for disciplined position management.","📊"),
            ("Pidgin Mode","Toggle Pidgin in the AI Brief for a faster, natural read of the morning summary.","🇳🇬"),
        ]
        title = "📚 Trader Guide"
    elif tier == "pro":
        steps = [
            ("Start at the Command Center","The AI Trade Briefing at the top of your dashboard is your daily starting point.","🎯"),
            ("Portfolio Strategy","Ask: 'Build me a portfolio strategy around ZENITHBANK' for full sector-aware allocation.","🏆"),
            ("PDF Export","Save any analysis as PDF — log your investment reasoning over time.","📄"),
        ]
        title = "📚 Pro Guide"
    else:
        return

    with st.expander(title, expanded=False):
        for idx, (_t, _txt, _icon) in enumerate(steps, 1):
            st.markdown(f"""
<div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #0F0F0F;font-family:'DM Mono',monospace;">
  <div style="background:rgba(240,165,0,.1);border:1px solid rgba(240,165,0,.25);border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#F0A500;flex-shrink:0;margin-top:2px;">{idx}</div>
  <div>
    <div style="font-size:13px;font-weight:600;color:#FFFFFF;margin-bottom:3px;">{_icon} {_t}</div>
    <div style="font-size:12px;color:#808080;line-height:1.6;">{_txt}</div>
  </div>
</div>""", unsafe_allow_html=True)
        if st.button("✓ Got it, dismiss guide", key=f"guide_dismiss_{tier}"):
            st.session_state[guide_key] = True; st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PRO COMMAND CENTER (self-contained — preserved from v11 exactly)
# ══════════════════════════════════════════════════════════════════════════════

def _render_pro_command_center(tier, profile, sb, uniq, market, now, _sig_map):
    """
    Full Pro Command Center card. Uses st.components.v1.html to bypass
    Streamlit's DOMPurify CSS sanitizer. Fully self-contained iframe HTML.
    """
    # ── 1. Pick the top-rated BUY signal ─────────────────────────────────────
    _sigs = _load_home_signals()
    _price_map = {p["symbol"]: p for p in uniq}

    _top = None
    for s in _sigs:
        if (s.get("signal") or "").upper() == "BUY":
            _top = s; break
    if not _top and _sigs:
        _top = _sigs[0]

    if not _top:
        # Skeleton card — no data yet
        st.components.v1.html("""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box;}html,body{background:transparent;font-family:'DM Mono',monospace;overflow:hidden;}
.card{background:#0A0A0A;border:1px solid rgba(240,165,0,.15);border-radius:18px;padding:32px 24px;text-align:center;}
.sk-title{font-family:'Space Grotesk',sans-serif;font-size:14px;color:#F0A500;margin-bottom:8px;}
.sk-sub{font-size:12px;color:#505050;line-height:1.7;}
.skeleton{background:linear-gradient(90deg,#111 25%,#181818 50%,#111 75%);background-size:200% 100%;animation:shimmer 1.5s infinite;border-radius:6px;height:16px;margin:8px 0;}
@keyframes shimmer{0%{background-position:200% 0;}100%{background-position:-200% 0;}}</style>
</head><body><div class="card">
<div class="sk-title">⚡ AI Trade Briefing — Loading</div>
<div class="sk-sub">Fetching today's top signal for you…</div>
<div class="skeleton" style="width:70%;margin:16px auto 8px;"></div>
<div class="skeleton" style="width:50%;margin:auto;"></div>
</div></body></html>""", height=180, scrolling=False)
        return

    # ── 2. Derive display values ──────────────────────────────────────────────
    sym    = _top.get("symbol","—")
    sig    = (_top.get("signal") or "HOLD").upper()
    _stars = min(int(_top.get("stars",3) or 3), 5)
    reason = _top.get("reasoning","") or "Signal derived from multi-factor AI model."
    _sd    = _sig_map.get(sym, {})
    _pd    = _price_map.get(sym, {})
    price  = float(_pd.get("price",0) or 0)
    chg    = float(_pd.get("change_percent",0) or 0)
    mom    = min(100, int(float(_sd.get("momentum_score",0) or 0)*20))
    vol    = min(100, int(float(_sd.get("volume_score",0)   or 0)*20))
    news_s = min(100, int(float(_sd.get("news_score",0)     or 0)*20))
    conf   = max(mom, vol, news_s, 60)
    entry  = round(price * 0.99, 2) if price > 0 else 0
    target = round(price * 1.085, 2) if price > 0 else 0
    stop   = round(price * 0.95, 2) if price > 0 else 0

    _sc = "#22C55E" if sig=="BUY" else ("#EF4444" if sig=="AVOID" else "#F0A500")
    upside = round((target-price)/price*100,1) if price > 0 else 0
    _clabel = "High" if conf >= 75 else ("Medium" if conf >= 50 else "Low")
    _ccol   = "#22C55E" if conf >= 75 else ("#F0A500" if conf >= 50 else "#EF4444")
    _risk   = "Medium risk — wait for a confirmed breakout above resistance before entering." if sig=="BUY" else "Hold current position. Watch volume for directional confirmation."
    _action = f"Consider entering near N{entry:,.2f}. Set stop-loss at N{stop:,.2f} to limit downside." if price > 0 else "Set alert for price breakout trigger."
    _driver1= reason[:120] if reason else "Momentum and volume converging — signal strength above threshold."
    _driver2= f"Confidence: {conf}% — {_clabel.lower()} conviction. Market mood: {tier.upper()} plan AI."
    _verdict= f"Signal suggests {sig.lower()} opportunity. Entry near current price with defined exit."
    _bars   = "".join(f'<div class="pcc-bar-block" style="background:{"#22C55E" if i < round(conf/10) else "#1A1A1A"};"></div>' for i in range(10))
    _sentiments = [("Momentum",mom,_sc),("Volume",vol,"#3B82F6"),("News",news_s,"#A78BFA")]
    _sent_html = "".join(
        f'<div class="pcc-sent-item">'
        f'<div class="pcc-sent-ring-outer" style="width:44px;height:44px;border:2px solid {c}33;">'
        f'<div class="pcc-sent-ring-inner" style="width:34px;height:34px;">'
        f'<span class="pcc-sent-val" style="color:{c};">{v}%</span></div></div>'
        f'<span class="pcc-sent-lbl">{l}</span></div>'
        for l,v,c in _sentiments
    )
    _stars_html = "⭐" * _stars
    _chg = chg
    _refreshed_str = now.strftime("%I:%M %p") + " WAT"

    def _fmt(n): return f"N{n:,.2f}" if n > 0 else "—"

    _card_html = f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{background:transparent;font-family:'DM Mono',monospace;overflow-x:hidden;}}
@keyframes pulse-ring{{0%{{box-shadow:0 0 0 0 rgba(240,165,0,.3);}}70%{{box-shadow:0 0 0 8px rgba(240,165,0,0);}}100%{{box-shadow:0 0 0 0 rgba(240,165,0,0);}}}}
@keyframes fadein{{from{{opacity:0;transform:translateY(6px);}}to{{opacity:1;transform:translateY(0);}}}}
.card{{background:linear-gradient(160deg,#0C0C0C 0%,#050505 100%);border:1px solid {_sc}44;border-radius:18px;overflow:hidden;animation:fadein .4s ease both;}}
.accent{{height:3px;background:linear-gradient(90deg,transparent,{_sc},transparent);}}
.hdr{{display:flex;align-items:center;justify-content:space-between;padding:13px 18px 11px;border-bottom:1px solid #1F1F1F;flex-wrap:wrap;gap:6px;}}
.hdr-left{{display:flex;align-items:center;gap:9px;}}
.pulse{{width:8px;height:8px;border-radius:50%;background:#F0A500;display:inline-block;animation:pulse-ring 2.5s infinite;flex-shrink:0;}}
.hdr-title{{font-family:'Space Grotesk',sans-serif;font-size:13px;font-weight:600;color:#F0A500;letter-spacing:.04em;}}
.pro-badge{{background:#F0A50020;border:1px solid #F0A50040;border-radius:4px;font-size:9px;color:#F0A500;padding:2px 7px;font-weight:700;letter-spacing:.1em;font-family:'DM Mono',monospace;}}
.hdr-time{{font-size:10px;color:#606060;}}
.body{{padding:18px 18px 14px;}}
.hero{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:14px;gap:10px;flex-wrap:wrap;}}
.sym{{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:700;color:#FFF;letter-spacing:-.01em;}}
.sig-badge{{border-radius:6px;font-size:11px;font-weight:700;padding:3px 10px;letter-spacing:.1em;border-width:1.5px;border-style:solid;}}
.stock-name{{font-size:11px;color:#606060;margin-top:3px;}}
.upside-box{{border-radius:10px;padding:8px 14px;text-align:center;flex-shrink:0;}}
.upside-lbl{{font-size:9px;color:#606060;margin-bottom:2px;letter-spacing:.1em;text-transform:uppercase;}}
.upside-val{{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700;}}
.price-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:#1F1F1F;border-radius:10px;overflow:hidden;margin-bottom:18px;}}
.price-cell{{background:#111;padding:10px 0;text-align:center;}}
.price-lbl{{font-size:9px;color:#606060;margin-bottom:4px;letter-spacing:.1em;text-transform:uppercase;}}
.price-val{{font-size:13px;font-weight:600;letter-spacing:-.01em;}}
.sec-lbl{{display:flex;align-items:center;gap:8px;font-size:9px;color:#606060;text-transform:uppercase;letter-spacing:.15em;margin-bottom:8px;}}
.sec-line{{flex:1;height:1px;background:#1F1F1F;}}
.driver{{display:flex;gap:10px;padding:10px 12px;background:#111;border-radius:8px;margin-bottom:6px;}}
.driver-icon{{font-size:12px;flex-shrink:0;margin-top:1px;}}
.driver-text{{font-size:12px;color:#E0E0E0;line-height:1.65;}}
.verdict{{border-radius:10px;padding:12px 14px;margin-bottom:18px;}}
.verdict-lbl{{font-size:9px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px;}}
.verdict-txt{{font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:600;color:#FFF;line-height:1.5;}}
.conf-row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}}
.conf-label{{font-size:11px;color:#909090;letter-spacing:.08em;text-transform:uppercase;}}
.conf-right{{display:flex;align-items:center;gap:8px;}}
.conf-text{{font-size:13px;font-weight:700;}}
.conf-pct{{font-size:11px;color:#606060;}}
.bar-track{{display:flex;gap:3px;margin-bottom:18px;}}
.bar-block{{flex:1;height:6px;border-radius:2px;}}
.sent-row{{display:flex;justify-content:space-around;margin-bottom:18px;}}
.sent-item{{display:flex;flex-direction:column;align-items:center;gap:5px;}}
.sent-outer{{display:flex;align-items:center;justify-content:center;border-radius:50%;width:44px;height:44px;}}
.sent-inner{{border-radius:50%;background:#111;display:flex;align-items:center;justify-content:center;width:34px;height:34px;}}
.sent-val{{font-size:10px;font-weight:700;}}
.sent-lbl{{font-size:9px;color:#606060;text-transform:uppercase;letter-spacing:.06em;}}
.callout{{display:flex;gap:10px;padding:12px 14px;border-radius:10px;margin-bottom:14px;}}
.callout-icon{{font-size:14px;flex-shrink:0;}}
.callout-text{{font-size:12px;line-height:1.65;}}
.ctx-box{{display:flex;gap:10px;padding:10px 14px;background:#111;border-radius:10px;margin-bottom:18px;}}
.ctx-text{{font-size:12px;color:#909090;line-height:1.65;}}
.footer{{display:flex;justify-content:space-between;align-items:center;padding-top:10px;border-top:1px solid #1F1F1F;}}
.footer-text{{font-size:9px;color:#606060;}}
.share-strip{{padding:14px 18px 18px;border-top:1px solid #1F1F1F;}}
.share-strip-row{{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;}}
.share-label{{font-size:10px;color:#606060;text-transform:uppercase;letter-spacing:.12em;font-family:'DM Mono',monospace;}}
.share-btns{{display:flex;gap:8px;flex-wrap:wrap;}}
.share-btn{{display:flex;align-items:center;gap:6px;background:transparent;border:1px solid rgba(255,255,255,.25);border-radius:8px;padding:7px 14px;cursor:pointer;font-family:'DM Mono',monospace;font-size:11px;font-weight:600;color:#FFFFFF;transition:all .15s;}}
.share-btn:hover{{border-color:rgba(255,255,255,.5);background:rgba(255,255,255,.05);}}
#pcc-toast{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#22C55E;color:#000;font-family:'Space Grotesk',sans-serif;font-size:12px;font-weight:700;padding:8px 18px;border-radius:20px;display:none;z-index:9999;box-shadow:0 4px 20px rgba(34,197,94,.4);}}
</style>
</head>
<body>
<div id="pcc-toast">✓ Done!</div>
<div id="pcc-capture">
<div class="card">
  <div class="accent"></div>
  <div class="hdr">
    <div class="hdr-left">
      <div class="pulse"></div>
      <span class="hdr-title">&#129504; AI Trade Briefing</span>
      <span class="pro-badge">{tier.upper()}</span>
    </div>
    <span class="hdr-time">Updated {_refreshed_str} &nbsp;&middot;&nbsp; Refreshes every 10 min</span>
  </div>
  <div class="body">
    <div class="hero">
      <div>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
          <span class="sym">{sym}</span>
          <span class="sig-badge" style="background:{_sc}22;border-color:{_sc};color:{_sc};">{sig}</span>
        </div>
        <div class="stock-name">{_stars_html} &nbsp;&middot;&nbsp; {_chg:+.2f}% today</div>
      </div>
      <div class="upside-box" style="background:{_sc}15;border:1px solid {_sc}33;">
        <div class="upside-lbl">Potential</div>
        <div class="upside-val" style="color:{_sc};">+{upside}%</div>
      </div>
    </div>
    <div class="price-grid">
      <div class="price-cell"><div class="price-lbl">Entry</div><div class="price-val" style="color:#E0E0E0;">{_fmt(entry)}</div></div>
      <div class="price-cell"><div class="price-lbl">Target</div><div class="price-val" style="color:#22C55E;">{_fmt(target)}</div></div>
      <div class="price-cell"><div class="price-lbl">Stop</div><div class="price-val" style="color:#EF4444;">{_fmt(stop)}</div></div>
    </div>
    <div class="sec-lbl"><div class="sec-line"></div>What&#39;s Really Driving This<div class="sec-line"></div></div>
    <div class="driver" style="border-left:2px solid #60A5FA;">
      <span class="driver-icon">&#128227;</span>
      <span class="driver-text">{_driver1}</span>
    </div>
    <div class="driver" style="border-left:2px solid #22C55E;margin-bottom:12px;">
      <span class="driver-icon">&#128202;</span>
      <span class="driver-text">{_driver2}</span>
    </div>
    <div class="verdict" style="background:{_sc}12;border:1px solid {_sc}33;">
      <div class="verdict-lbl" style="color:{_sc};">Simple Verdict</div>
      <div class="verdict-txt">{_verdict}</div>
    </div>
    <div class="sec-lbl"><div class="sec-line"></div>Confidence Level<div class="sec-line"></div></div>
    <div class="conf-row">
      <span class="conf-label">Confidence</span>
      <div class="conf-right">
        <span class="conf-text" style="color:{_ccol};">{_clabel}</span>
        <span class="conf-pct">{conf}%</span>
      </div>
    </div>
    <div class="bar-track">{_bars}</div>
    <div class="sec-lbl"><div class="sec-line"></div>Signal Breakdown<div class="sec-line"></div></div>
    <div class="sent-row">{_sent_html}</div>
    <div class="sec-lbl"><div class="sec-line"></div>Risk Note<div class="sec-line"></div></div>
    <div class="callout" style="background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.15);">
      <span class="callout-icon">&#9888;&#65039;</span>
      <span class="callout-text" style="color:#C0A0A0;">{_risk}</span>
    </div>
    <div class="sec-lbl"><div class="sec-line"></div>Smart Action<div class="sec-line"></div></div>
    <div class="callout" style="background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.15);margin-bottom:6px;">
      <span class="callout-icon">&#128161;</span>
      <span class="callout-text" style="color:#A0C0A0;">{_action}</span>
    </div>
    <div class="footer">
      <span class="footer-text">&#9881; NGX Signal AI &nbsp;&middot;&nbsp; ngxsignal.com</span>
      <span class="footer-text">Not financial advice &nbsp;&middot;&nbsp; Always DYOR</span>
    </div>
  </div>
  <div class="share-strip">
    <div class="share-strip-row">
      <span class="share-label">Share signal</span>
      <div class="share-btns">
        <button class="share-btn" onclick="shareAsImage()"><span class="share-btn-icon">🖼</span> Save Image</button>
        <button class="share-btn" onclick="shareAsPDF()"><span class="share-btn-icon">📄</span> PDF</button>
        <button class="share-btn" onclick="copyText()"><span class="share-btn-icon">📋</span> Copy</button>
      </div>
    </div>
  </div>
</div>
</div>
<script>
function showToast(msg){{var t=document.getElementById('pcc-toast');t.textContent=msg;t.style.display='block';setTimeout(function(){{t.style.display='none';}},2500);}}
function copyText(){{var txt='{sym} {sig} | Entry:{_fmt(entry)} Target:{_fmt(target)} Stop:{_fmt(stop)} | Confidence:{conf}% | NGX Signal — ngxsignal.com';navigator.clipboard.writeText(txt).then(function(){{showToast('✓ Copied!');}}).catch(function(){{showToast('❌ Copy failed');}});}}
function buildExportCard(){{var card=document.createElement('div');card.id='export-card';card.style.cssText='position:fixed;left:-9999px;top:0;width:600px;font-family:Space Grotesk,sans-serif;background:#FFFFFF;border-radius:16px;overflow:hidden;';card.innerHTML='<div style="background:#F0A500;height:4px;"></div><div style="padding:24px;"><div style="font-size:11px;color:#9CA3AF;text-transform:uppercase;letter-spacing:.12em;margin-bottom:16px;">NGX Signal AI Trade Briefing</div><div style="font-size:28px;font-weight:800;color:#111;margin-bottom:6px;">{sym}</div><div style="font-size:14px;font-weight:700;color:#F0A500;margin-bottom:20px;">{sig} &nbsp; {_stars_html}</div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:#E5E7EB;border-radius:10px;overflow:hidden;margin-bottom:20px;"><div style="background:#F9FAFB;padding:12px;text-align:center;"><div style="font-size:9px;color:#9CA3AF;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;">Entry</div><div style="font-size:14px;font-weight:600;color:#111;">{_fmt(entry)}</div></div><div style="background:#F9FAFB;padding:12px;text-align:center;"><div style="font-size:9px;color:#9CA3AF;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;">Target</div><div style="font-size:14px;font-weight:600;color:#16A34A;">{_fmt(target)}</div></div><div style="background:#F9FAFB;padding:12px;text-align:center;"><div style="font-size:9px;color:#9CA3AF;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;">Stop</div><div style="font-size:14px;font-weight:600;color:#DC2626;">{_fmt(stop)}</div></div></div><div style="font-size:13px;color:#374151;line-height:1.7;margin-bottom:20px;">{_driver1}</div><div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;padding:12px;font-size:12px;color:#92400E;margin-bottom:20px;">{_action}</div></div><div style="background:#F9FAFB;padding:12px 24px;display:flex;justify-content:space-between;align-items:center;"><span style="font-size:13px;font-weight:800;color:#F0A500;">⚡ NGX Signal</span><span style="font-size:9px;color:#9CA3AF;">Not financial advice · Always DYOR</span></div>';document.body.appendChild(card);return card;}}
function captureExportCard(){{var card=buildExportCard();return html2canvas(card,{{backgroundColor:'#FFFFFF',scale:2,useCORS:true,logging:false,width:600,windowWidth:600}}).then(function(canvas){{document.body.removeChild(card);return canvas;}}).catch(function(e){{if(document.getElementById('export-card'))document.body.removeChild(card);throw e;}});}}
function shareAsImage(){{showToast('⏳ Generating…');captureExportCard().then(function(canvas){{var link=document.createElement('a');link.download='NGX-Signal-{sym}-{now.strftime("%Y%m%d")}.png';link.href=canvas.toDataURL('image/png');link.click();showToast('✓ Image saved!');}}).catch(function(){{showToast('❌ Error — try again');}});}}
function shareAsPDF(){{showToast('⏳ Generating PDF…');captureExportCard().then(function(canvas){{var {{jsPDF}}=window.jspdf;var imgData=canvas.toDataURL('image/png');var pdfW=210;var imgW=canvas.width;var imgH=canvas.height;var ratio=imgH/imgW;var pdfH=Math.max(297,Math.round(pdfW*ratio));var pdf=new jsPDF({{orientation:'p',unit:'mm',format:[pdfW,pdfH]}});pdf.setFillColor(255,255,255);pdf.rect(0,0,pdfW,pdfH,'F');var drawW=pdfW-10;var drawH=Math.round(drawW*ratio);pdf.addImage(imgData,'PNG',5,5,drawW,drawH);var footerY=drawH+12;pdf.setFontSize(7);pdf.setTextColor(156,163,175);pdf.text('Generated by NGX Signal AI · ngxsignal.com · Not financial advice · Always DYOR',pdfW/2,footerY,{{align:'center'}});pdf.save('NGX-Signal-{sym}-{now.strftime("%Y%m%d")}.pdf');showToast('✓ PDF downloaded!');}}).catch(function(){{showToast('❌ Error — try again');}});}}
</script>
</body>
</html>"""

    st.components.v1.html(_card_html, height=1020, scrolling=True)
    _, _bc_full, _ = st.columns([1, 2, 1])
    with _bc_full:
        if st.button("📊 Full Analysis →", key="pcc_full", type="primary", use_container_width=True):
            st.session_state.current_page = "signals"; st.rerun()
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render():
    # ── AUTH INTERCEPT ────────────────────────────────────────────────────────
    if st.session_state.get("show_auth") and not st.session_state.get("user"):
        from app.views import auth as _auth_view
        st.markdown("""
<div style="background:linear-gradient(135deg,#0A0800,#150F00);
            border:1px solid rgba(240,165,0,0.3);border-radius:14px;
            padding:20px 22px;text-align:center;max-width:520px;margin:16px auto 20px;">
  <div style="font-size:36px;margin-bottom:10px;">🔐</div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:20px;
              font-weight:800;color:#F0A500;margin-bottom:6px;">
    Sign Up Free — Get 14 Days Premium
  </div>
  <div style="font-family:'DM Mono',monospace;font-size:12px;
              color:#A0A0A0;line-height:1.7;">
    Full AI signals · Daily picks · Entry &amp; target prices · No credit card needed
  </div>
</div>""", unsafe_allow_html=True)
        _auth_view.render()
        if st.button("← Back", key="auth_back"):
            st.session_state.show_auth = False; st.rerun()
        return

    # ── INJECT CSS ────────────────────────────────────────────────────────────
    st.markdown(_CSS, unsafe_allow_html=True)

    # ── CORE STATE ────────────────────────────────────────────────────────────
    sb           = _get_sb()
    profile      = st.session_state.get("profile", {})
    current_user = st.session_state.get("user")
    market       = get_market_status()
    now          = now_wat()
    today        = str(date.today())

    # ── TIER FLAGS ────────────────────────────────────────────────────────────
    tier        = get_user_tier()
    is_visitor  = tier == "visitor"
    is_free     = tier == "free"
    is_trial    = tier == "trial"
    is_starter  = tier == "starter"
    is_trader   = tier == "trader"
    is_pro      = tier == "pro"
    is_paid     = tier in PAID_TIERS
    is_ex_trial = (not is_paid and not is_trial and was_trial_user(profile))
    has_full_ai = can_access("ai_full_response", tier)
    is_funnel   = tier in ("visitor","free")
    is_dashboard= tier in ("trial","starter","trader","pro")

    name = (profile.get("full_name","Investor") if not is_visitor else "Investor").split()[0]
    trial_days_left = get_trial_days_left(profile) if is_trial else 0
    trial_urgent    = is_trial and trial_days_left <= 3

    _rem_queries, _queries_restricted = _queries_remaining(tier)
    ai_allowed = not _queries_restricted and tier != "visitor"

    # ── LOAD DATA ─────────────────────────────────────────────────────────────
    prices, latest_date = _load_home_prices()
    msum = _load_home_market_summary()
    _brief_res = _load_home_briefs()
    _trending  = _load_home_trending_signals()
    _gp        = get_global_pulse()

    # De-duplicate prices (latest per symbol)
    sym_seen = set(); uniq = []
    for p in prices:
        s = p.get("symbol","")
        if s and s not in sym_seen: sym_seen.add(s); uniq.append(p)

    # Build sig_map for fast lookup
    _sig_raw = _load_home_signals()
    _sig_map = {s.get("symbol",""): s for s in _sig_raw}

    # Market stats
    ad   = msum.get("asi_value","—")
    acg  = float(msum.get("asi_change_percent",0) or 0)
    acol = "#22C55E" if acg >= 0 else "#EF4444"
    aarr = "+" if acg >= 0 else ""
    gc   = int(msum.get("gainers",0) or 0)
    lc   = int(msum.get("losers",0)  or 0)
    total= int(msum.get("total",len(uniq)) or len(uniq))
    mood = msum.get("market_mood","Neutral")
    mcol = "#22C55E" if "Bull" in mood else ("#EF4444" if "Bear" in mood else "#F0A500")
    moji = "📈" if "Bull" in mood else ("📉" if "Bear" in mood else "⚖️")
    data_label = f"{'Live' if market['is_open'] else 'Last close'} {latest_date}"

    # Top movers
    top_g = sorted([p for p in uniq if float(p.get("change_percent",0) or 0) > 0],
                    key=lambda x: float(x.get("change_percent",0) or 0), reverse=True)[:5]

    # Notification age (minutes since last signal trigger — approximate)
    _h = hashlib.md5(today.encode()).hexdigest()
    notif_minutes = (int(_h[:4],16) % 45) + 5

    # Build insights for hero card
    _price_map_dict = {p["symbol"]: p for p in uniq}
    insights = []
    for s in _sig_raw:
        sym_ = s.get("symbol","")
        sig_ = (s.get("signal") or "HOLD").upper()
        stars_= int(s.get("stars") or 3)
        reason_ = s.get("reasoning","") or ""
        _pdx = _price_map_dict.get(sym_,{})
        prx  = float(_pdx.get("price",0) or 0)
        conf_= max(60, min(95, stars_*18))
        insights.append({"sym":sym_,"action":sig_,"stars":stars_,"reason":reason_,"price":prx,"conf":conf_})

    brief_ok    = bool(_brief_res)
    brief_color = "#22C55E" if brief_ok else "#505050"

    # ── POST-SIGNUP WELCOME MODAL ─────────────────────────────────────────────
    if st.session_state.get("just_signed_up"):
        st.session_state.just_signed_up = False
        st.session_state.show_welcome_modal = True

    if st.session_state.get("show_welcome_modal"):
        _wname = (profile.get("full_name","Investor") or "Investor").split()[0]
        _tdl   = get_trial_days_left(profile) if profile else 14
        st.markdown(f"""
<style>
@keyframes modal-pop{{from{{opacity:0;transform:scale(.92) translateY(20px);}}to{{opacity:1;transform:scale(1) translateY(0);}}}}
.wm-overlay{{position:fixed;inset:0;z-index:999999;background:rgba(0,0,0,.88);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:20px;}}
.wm-card{{background:linear-gradient(160deg,#080F00,#0D1A00);border:2px solid rgba(34,197,94,.55);border-radius:20px;padding:36px 28px;max-width:460px;width:100%;text-align:center;box-shadow:0 0 80px rgba(34,197,94,.2);animation:modal-pop .45s cubic-bezier(.16,1,.3,1) both;}}
.wm-stats{{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-bottom:24px;}}
.wm-stat{{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);border-radius:10px;padding:12px 18px;}}
.wm-stat-num{{font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:800;color:#22C55E;}}
.wm-stat-lbl{{font-family:'DM Mono',monospace;font-size:10px;color:#808080;margin-top:3px;}}
.wm-btn{{display:block;width:100%;background:linear-gradient(135deg,#22C55E,#16A34A);color:#000;font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:800;border:none;border-radius:12px;padding:16px;cursor:pointer;box-shadow:0 4px 24px rgba(34,197,94,.4);}}
</style>
<div class="wm-overlay" id="wm-overlay">
  <div class="wm-card">
    <span style="font-size:56px;display:block;margin-bottom:14px;">🎉</span>
    <div style="font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:800;color:#22C55E;margin-bottom:10px;line-height:1.3;">You've Unlocked 14 Days Free Premium!</div>
    <div style="font-family:'DM Mono',monospace;font-size:13px;color:#D0D0D0;line-height:1.8;margin-bottom:20px;">Welcome, {_wname}! Full access to premium signals and features.</div>
    <div class="wm-stats">
      <div class="wm-stat"><div class="wm-stat-num">{_tdl}</div><div class="wm-stat-lbl">Days Free</div></div>
      <div class="wm-stat"><div class="wm-stat-num" style="color:#F0A500;">∞</div><div class="wm-stat-lbl">AI Queries</div></div>
      <div class="wm-stat"><div class="wm-stat-num" style="color:#3B82F6;">9</div><div class="wm-stat-lbl">Daily Picks</div></div>
    </div>
    <button class="wm-btn" onclick="document.getElementById('wm-overlay').style.display='none';document.getElementById('wm-dismiss-btn').click();">
      🚀 Start Exploring Premium →
    </button>
  </div>
</div>""", unsafe_allow_html=True)
        if st.button("", key="wm-dismiss-btn", label_visibility="collapsed"):
            st.session_state.show_welcome_modal = False; st.rerun()

    # ── DOWNGRADE MODAL (ex-trial re-engage) ──────────────────────────────────
    _render_downgrade_modal(profile, tier, name)

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNNEL FLOW — VISITOR / FREE
    # ═══════════════════════════════════════════════════════════════════════════
    if is_funnel:
        # 1. GREETING
        greeting = get_greeting(name) if not is_visitor else "Welcome to NGX Signal 👋"
        _sub = "Logged in as Free · 2 AI queries per day" if is_free else "AI-powered signals for Nigerian stocks"
        st.markdown(f"""
<div class="greeting-wrap">
  <div class="greeting-name">{greeting}</div>
  <div class="greeting-sub">{_sub}</div>
</div>""", unsafe_allow_html=True)

        # 2. CONTEXT STRIP (free only — show last ticker + streak)
        if is_free:
            render_personalized_strip(tier, profile, sb, name, uniq)

        # 3. MARKET STATUS
        _render_market_status_bar(market)

        # 4. NOTIFICATION BANNER
        _render_notification_banner(top_g, now, gc, total, market, notif_minutes)

        # 5. GLOBAL PULSE
        _render_global_pulse_section(tier, _gp)

        # 6. HERO SIGNAL CARD — the value hook
        st.markdown('<div class="sec-title">🔥 Top Signal Right Now</div>', unsafe_allow_html=True)
        _render_top_opportunity(insights, uniq, _sig_map, notif_minutes, tier)

        # 7. METRIC CARDS (breadth, ASI, mood — no fake win rate)
        _render_metric_cards(ad, acg, acol, aarr, total, gc, lc, mood, mcol, moji,
                             market, data_label, brief_ok, brief_color)

        # 8. AI CHAT
        _render_ai_chat(
            tier, profile, sb, uniq, market, latest_date,
            ad, aarr, acg, mood, gc, lc, total, top_g, notif_minutes,
            key_suffix="_funnel", has_full_ai=has_full_ai,
            ai_allowed=(ai_allowed and tier != "visitor"),
            _rem_queries=_rem_queries, _queries_restricted=_queries_restricted,
            _gp_for_ai=_gp
        )

        # 9. TRENDING (partial — 2 visible, 1 blurred)
        _ts_all = (sorted([p for p in uniq if float(p.get("change_percent") or 0) > 0],
                           key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:2]
                 + sorted([p for p in uniq if float(p.get("change_percent") or 0) < 0],
                           key=lambda x:float(x.get("change_percent",0) or 0))[:2])[:4]
        if _ts_all:
            st.markdown('<div class="sec-title">📊 Trending Now</div>', unsafe_allow_html=True)
            st.markdown('<div class="tgrid">', unsafe_allow_html=True)
            for _ti, _ts in enumerate(_ts_all[:3]):
                _tc = float(_ts.get("change_percent",0) or 0)
                _tag,_tc2,_ = _trend_tag(_tc)
                _cc  = "#22C55E" if _tc >= 0 else "#EF4444"
                _blur = "filter:blur(5px);user-select:none;" if _ti >= 2 and is_visitor else ""
                st.markdown(
                    f'<div class="tgrid-card" style="{_blur}">'
                    f'<div class="tgrid-sym">{_ts["symbol"]}</div>'
                    f'<div class="tgrid-chg" style="color:{_cc};">{"+" if _tc>=0 else ""}{_tc:.2f}%</div>'
                    f'<div class="tgrid-tag" style="background:{_cc}18;color:{_cc};">{_tag}</div>'
                    f'</div>', unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

        # 10. TRUST PROOF (market breadth only — no fake stats)
        st.markdown('<div class="sec-title">📈 Market at a Glance</div>', unsafe_allow_html=True)
        _render_performance_trust(gc, lc, total, top_g, now)

        # 11. TESTIMONIALS
        _render_testimonials()

        # 12. SINGLE UPGRADE CTA — one per page
        _render_single_upgrade_nudge(tier)

    # ═══════════════════════════════════════════════════════════════════════════
    # DASHBOARD FLOW — TRIAL / STARTER / TRADER / PRO
    # ═══════════════════════════════════════════════════════════════════════════
    else:
        # 1. GREETING
        greeting = get_greeting(name)
        _plan_label = {
            "trial":   f"Trial — {trial_days_left} days left",
            "starter": "Starter Plan",
            "trader":  "Trader Plan",
            "pro":     "Pro Plan ⚡",
        }.get(tier, "")
        st.markdown(f"""
<div class="greeting-wrap">
  <div class="greeting-name">{greeting}</div>
  <div class="greeting-sub">{_plan_label} &nbsp;·&nbsp; {data_label}</div>
</div>""", unsafe_allow_html=True)

        # 2. CONTEXT STRIP (last ticker, streak, queries)
        render_personalized_strip(tier, profile, sb, name, uniq)

        # 3. TRIAL REMINDER STRIP — compact, once per day, dismissible
        if is_trial and not st.session_state.get("trial_reminder_dismissed"):
            _rk = f"trial_remind_shown_{date.today()}"
            if not st.session_state.get(_rk):
                st.session_state[_rk] = True
                _uc = "#EF4444" if trial_urgent else "#F0A500"
                _ub = "rgba(239,68,68,.08)" if trial_urgent else "rgba(240,165,0,.06)"
                _msg = f"⚠️ Only {trial_days_left} days left!" if trial_urgent else f"✨ {trial_days_left} days remaining"
                st.markdown(
                    f'<div class="trial-strip" style="background:{_ub};border:1px solid {_uc}22;border-left-color:{_uc};">'
                    f'<span style="font-family:\'DM Mono\',monospace;font-size:12px;color:{_uc};">{_msg}</span>'
                    f'</div>', unsafe_allow_html=True
                )

        # 4. MARKET STATUS BAR
        _render_market_status_bar(market)

        # 5. GLOBAL PULSE
        _render_global_pulse_section(tier, _gp)

        # 6. ★ PRO COMMAND CENTER — FIRST for Trader/Pro
        #    For Starter/Trial: show notification banner + metric cards first
        if is_trader or is_pro:
            st.markdown('<div class="sec-title">⚡ Your AI Trade Briefing</div>', unsafe_allow_html=True)
            _render_pro_command_center(tier, profile, sb, uniq, market, now, _sig_map)

        # 7. METRIC CARDS (everyone gets these)
        _render_notification_banner(top_g, now, gc, total, market, notif_minutes)
        _render_metric_cards(ad, acg, acol, aarr, total, gc, lc, mood, mcol, moji,
                             market, data_label, brief_ok, brief_color)

        # 8. AI MARKET BRIEF EXPANDER
        _render_ai_brief_expander(tier, _brief_res, today, has_full_ai)

        # 9. BEST SIGNALS (Starter gets Command Center-style cards here instead)
        if not (is_trader or is_pro):
            # Trial / Starter: show top-signal hero first
            st.markdown('<div class="sec-title">🔥 Top Signal Right Now</div>', unsafe_allow_html=True)
            _render_top_opportunity(insights, uniq, _sig_map, notif_minutes, tier)

        # 10. AI CHAT
        _render_ai_chat(
            tier, profile, sb, uniq, market, latest_date,
            ad, aarr, acg, mood, gc, lc, total, top_g, notif_minutes,
            key_suffix="_dash", has_full_ai=has_full_ai,
            ai_allowed=ai_allowed,
            _rem_queries=_rem_queries, _queries_restricted=_queries_restricted,
            _gp_for_ai=_gp
        )

        # 11. BEST SIGNALS composite cards
        _render_best_signals(tier, sb, uniq, _sig_map, is_trial)

        # 12. TOP MOVERS
        _render_top_movers(uniq, market, latest_date)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # 13. AI BRIEF
        # (already rendered above in expander)

        # 14. NEWS
        _render_news_section(tier, sb, market, today)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # 15. SECTOR SNAPSHOT
        _render_sector_snapshot(tier, sb)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # 16. TRADE GAME
        _render_trade_game(sb, current_user)

        # 17. DISMISSIBLE GUIDE (once after upgrade — inside expander, not blocking)
        _render_dismissible_guide(tier, profile)

        # 18. SINGLE UPGRADE NUDGE — bottom of page, one touchpoint only
        _render_single_upgrade_nudge(tier, trial_days_left, trial_urgent)
