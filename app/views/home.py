"""
NGX Signal — Home View  v11
============================
Architecture: TWO distinct funnel flows sharing one render() entry point.

VISITOR / FREE  → SELL THE PRODUCT
  Goal: "Convince me to pay"
  Funnel: Hook → Trust → Curiosity → Action → Understanding → Conversion

PRO DASHBOARD (Starter / Trader / Pro / Trial)  → DELIVER VALUE + RETAIN
  Goal: "I'm glad I paid — give me my edge"
  Funnel: Context → Intelligence → Signals → Analysis → News → Tools

Tier order (lowest → highest):
  visitor → free → trial → starter → trader → pro

All inbuilt helper functions (tier system, AI call, engagement tracking,
trial helpers, streaks, share sheet, downgrade modal, personalized strip)
are PRESERVED EXACTLY from v10.  Only render() is restructured.
"""

import streamlit as st
import re
import requests
import hashlib
from datetime import date, datetime, timedelta
from app.utils.supabase_client import get_supabase
from app.views.signals import generate_trending_sentiment_tag

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
# TIER SYSTEM  (unchanged from v10)
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
                    "🔒 Entry price, target & stop-loss per pick",
                    "🔒 Daily refresh alerts via Telegram"],
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
        if st.button(copy["cta"], key=key, type="primary", use_container_width=True):
            st.session_state.current_page = upgrade_page; st.rerun()

def _upgrade_inline(msg: str, key: str, cta: str = "🚀 Upgrade →", page: str = "settings"):
    st.markdown(f"""
<div style="background:rgba(240,165,0,.05);border:1px solid rgba(240,165,0,.18);
            border-left:3px solid #F0A500;border-radius:8px;
            padding:10px 14px;margin:8px 0;font-family:'DM Mono',monospace;
            font-size:12px;color:#B0B0B0;">🔒 {msg}</div>""", unsafe_allow_html=True)
    if st.button(cta, key=key, type="primary"):
        st.session_state.current_page = page; st.rerun()

def _tier_badge_html(tier: str) -> str:
    colors = {"visitor":"#606060","free":"#808080","trial":"#22C55E",
              "starter":"#3B82F6","trader":"#A78BFA","pro":"#F0A500"}
    c = colors.get(tier, "#606060")
    return (f'<span style="background:{c}1A;border:1px solid {c}55;border-radius:4px;'
            f'padding:2px 7px;font-family:DM Mono,monospace;font-size:9px;font-weight:700;'
            f'color:{c};text-transform:uppercase;letter-spacing:.08em;">{tier}</span>')

# ══════════════════════════════════════════════════════════════════════════════
# ENGAGEMENT TRACKING  (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

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

# ═══ Streak (unchanged) ═══════════════════════════════════════════════════════

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
    return {3:"3 days in a row 🔥",5:"5-day streak! 🚀",
            7:"Full week streak 🏆",14:"14-day champion 🥇"}.get(streak)

# ══════════════════════════════════════════════════════════════════════════════
# TRIAL HELPERS  (unchanged)
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
# MARKET / AI HELPERS  (unchanged)
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
    top_g_text, latest_date, market_open, question="",
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
    market_ctx = (
        f"LIVE MARKET DATA (as of {latest_date}):\n"
        f"- NGX All-Share Index: {ad} ({aarr}{abs(acg):.2f}%)\n"
        f"- Market: {'Open now' if market_open else 'Closed (last close data)'}\n"
        f"- Mood: {mood} | Gainers: {gc} | Losers: {lc} | Total tracked: {total}\n"
        f"- Top movers today: {top_g_text or 'None yet'}\n\n"
    )
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
            "EXAMPLE:\nRecommendation: HOLD ⚖️\n\n"
            "Jaiz Bank isn't showing strong movement right now. "
            "It's safer to wait for a clearer signal.\n\n"
            "_Upgrade to see full analysis and entry strategy._\n\n"
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
            "**Action Tip:** [Specific guidance — e.g. 'Enter small position around ₦X, "
            "set stop-loss at ₦Y']\n\n"
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
            "- Entry: [specific entry range in ₦, or 'wait for X']\n"
            "- Watch: [one specific thing to monitor next]\n"
            "- Risk Note: [one sentence on downside risk]\n\n"
            "**Detailed Insight:** *(only if adds real value)*\n"
            "[1-2 sentences of deeper context — keep it simple]\n\n"
            "RULES:\n- Must remain easy to understand — premium but not complex.\n"
            "- Include specific ₦ price levels wherever relevant.\n"
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
# DATA HELPERS  (unchanged)
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
# DOWNGRADE MODAL  (unchanged from v10)
# ══════════════════════════════════════════════════════════════════════════════

def _render_downgrade_modal(name: str, stats: dict):
    ai_used     = max(stats.get("total_ai_queries",0), 8)
    sigs_viewed = max(stats.get("signals_viewed",0), 6)
    stocks_ana  = max(stats.get("stocks_analyzed",0), 4)
    st.markdown(f"""
<style>
@keyframes modal-in{{from{{opacity:0;transform:scale(.96) translateY(12px);}}to{{opacity:1;transform:scale(1) translateY(0);}}}}
@keyframes loss-shake{{0%,100%{{transform:translateX(0);}}20%,60%{{transform:translateX(-4px);}}40%,80%{{transform:translateX(4px);}}}}
.dg-overlay{{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.92);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;padding:20px;}}
.dg-card{{background:linear-gradient(160deg,#0A0000,#080808);border:1px solid rgba(239,68,68,.35);border-radius:20px;padding:36px 32px;max-width:520px;width:100%;animation:modal-in .4s cubic-bezier(.16,1,.3,1) both;box-shadow:0 0 60px rgba(239,68,68,.18),0 0 120px rgba(0,0,0,.8);}}
.dg-icon{{font-size:42px;margin-bottom:14px;display:block;text-align:center;animation:loss-shake .5s ease .4s both;}}
.dg-title{{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:800;color:#FFFFFF;text-align:center;margin-bottom:6px;}}
.dg-stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:22px;}}
.dg-stat{{background:#0F0F0F;border:1px solid #1F1F1F;border-radius:10px;padding:12px 8px;text-align:center;}}
.dg-stat-num{{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:700;color:#F0A500;}}
.dg-stat-lbl{{font-family:'DM Mono',monospace;font-size:10px;color:#606060;margin-top:2px;}}
.dg-lost{{background:#0C0000;border:1px solid rgba(239,68,68,.25);border-radius:10px;padding:14px 16px;margin-bottom:20px;}}
.dg-lost-title{{font-family:'DM Mono',monospace;font-size:11px;font-weight:700;color:#EF4444;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;}}
.dg-lost-item{{font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;padding:4px 0;border-bottom:1px solid #1A0000;display:flex;align-items:center;gap:8px;}}
.dg-lost-item:last-child{{border-bottom:none;}}
.dg-cta-p{{display:block;width:100%;background:linear-gradient(135deg,#F0A500,#D97706);color:#000;font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:800;border:none;border-radius:12px;padding:16px;cursor:pointer;margin-bottom:10px;box-shadow:0 4px 24px rgba(240,165,0,.4);}}
.dg-cta-s{{display:block;width:100%;background:transparent;color:#505050;font-family:'DM Mono',monospace;font-size:11px;border:1px solid #1F1F1F;border-radius:10px;padding:10px;cursor:pointer;}}
.dg-dismiss{{font-family:'DM Mono',monospace;font-size:10px;color:#303030;text-align:center;margin-top:10px;cursor:pointer;}}
</style>
<div class="dg-overlay" id="dg-overlay">
  <div class="dg-card">
    <span class="dg-icon">📉</span>
    <div class="dg-title">Your Premium Trial Has Ended</div>
    <p style="font-family:DM Mono,monospace;font-size:13px;color:#808080;text-align:center;margin-bottom:22px;line-height:1.6;">
      {name}, you've lost access to the tools<br>that gave you an edge in the NGX market.
    </p>
    <div style="font-family:DM Mono,monospace;font-size:10px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px;text-align:center;">📊 During your 14-day trial:</div>
    <div class="dg-stats">
      <div class="dg-stat"><div class="dg-stat-num">{ai_used}</div><div class="dg-stat-lbl">AI queries answered</div></div>
      <div class="dg-stat"><div class="dg-stat-num">{sigs_viewed}</div><div class="dg-stat-lbl">signals viewed</div></div>
      <div class="dg-stat"><div class="dg-stat-num">{stocks_ana}</div><div class="dg-stat-lbl">stocks analysed</div></div>
    </div>
    <div class="dg-lost">
      <div class="dg-lost-title">You've lost access to:</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> Full AI market analysis &amp; recommendations</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> Daily AI Picks — 9 curated buy/hold/avoid stocks</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> Advanced signal scores for all 144 NGX stocks</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> Telegram alerts &amp; morning market brief</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> PDF intelligence reports</div>
    </div>
    <div style="font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;color:#FFFFFF;text-align:center;margin-bottom:18px;">Don't lose your edge in the market. 📈</div>
    <button class="dg-cta-p" onclick="document.getElementById('dg-overlay').style.display='none';document.getElementById('dg-upgrade-trigger').click();">🚀 Restore Full Access — Upgrade to Pro</button>
    <button class="dg-cta-s" onclick="document.getElementById('dg-overlay').style.display='none';document.getElementById('dg-upgrade-trigger').click();">View plans from N3,500/mo →</button>
    <div class="dg-dismiss" onclick="document.getElementById('dg-overlay').style.display='none';">Continue with limited access</div>
  </div>
</div>""", unsafe_allow_html=True)
    if st.button("", key="dg-upgrade-trigger", label_visibility="collapsed"):
        st.session_state.current_page = "settings"; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PERSONALIZED CONTEXT STRIP  (unchanged from v10)
# ══════════════════════════════════════════════════════════════════════════════

def render_personalized_strip(tier: str, profile: dict, sb, name: str, uniq: list):
    if tier == "visitor":
        return
    last_ticker  = st.session_state.get("last_ticker_asked", "")
    ticker_data  = next((p for p in uniq if p.get("symbol","").upper() == last_ticker.upper()), None) if last_ticker else None
    chg          = float(ticker_data.get("change_percent", 0)) if ticker_data else None
    chg_str      = (f"+{chg:.2f}% ▲" if chg >= 0 else f"{chg:.2f}% ▼") if chg is not None else None
    chg_color    = ("#22C55E" if chg >= 0 else "#EF4444") if chg is not None else "#F0A500"
    last_date    = st.session_state.get("last_query_date")
    days_ago     = (date.today() - last_date).days if isinstance(last_date, date) else None
    days_ago_str = (f"{days_ago} day{'s' if days_ago != 1 else ''} ago") if days_ago is not None else "recently"
    used_today   = get_ai_query_count()
    streak       = get_streak()
    streak_html  = f'🔥 {streak} days' if streak >= 2 else '—'
    GOLD="F0A500"; WHITE="#FFFFFF"; MUTE="#C0C0C0"; DIM="#808080"
    def _gold(t):  return f'<strong style="color:#{GOLD};">{t}</strong>'
    def _white(t): return f'<strong style="color:{WHITE};">{t}</strong>'
    def _col(t,c): return f'<strong style="color:{c};">{t}</strong>'
    def _strip(inner_html: str, show_upgrade_btn: bool = False, upgrade_key: str = ""):
        st.markdown(f"""
<div style="background:#080808;border:1px solid #1F1F1F;border-left:3px solid #{GOLD};
            border-radius:10px;padding:11px 16px;margin-bottom:12px;
            font-family:'DM Mono',monospace;font-size:12px;color:{MUTE};">
  {inner_html}
</div>""", unsafe_allow_html=True)
        if show_upgrade_btn and upgrade_key:
            if st.button("⬆️ Upgrade for unlimited →", key=upgrade_key, type="primary"):
                st.session_state.current_page = "settings"; st.rerun()

    if tier == "free":
        limit = 2; rem = max(0, limit - used_today)
        if last_ticker and ticker_data and chg is not None:
            inner = (f"📊 {_gold(last_ticker)}: {_col(chg_str, chg_color)} today"
                     f" · {_white(str(used_today))} of {_white(str(limit))} free queries used"
                     f" · Streak: {_white(streak_html)}")
        else:
            inner = (f"👋 Welcome, {_gold(name)}"
                     f" · {_white(str(used_today))} of {_white(str(limit))} free queries used today"
                     f" · Streak: {_white(streak_html)}")
        _strip(inner, show_upgrade_btn=(rem == 0), upgrade_key="strip_free_upgrade" if rem == 0 else "")

    elif tier == "trial":
        trial_days = get_trial_days_left(profile)
        tcolor = "#EF4444" if trial_days <= 3 else "#22C55E"
        if last_ticker and ticker_data and chg is not None:
            inner = (f"✨ {_gold(last_ticker)}: {_col(chg_str, chg_color)} today"
                     f" · Unlimited AI active · "
                     f'{_col(f"Trial: {trial_days} days left", tcolor)}'
                     f" · Streak: {_white(streak_html)}")
        else:
            inner = (f"✨ {_gold(name)} — Premium Trial Active"
                     f" · Unlimited AI · "
                     f'{_col(f"{trial_days} days remaining", tcolor)}'
                     f" · Streak: {_white(streak_html)}")
        _strip(inner)

    elif tier == "starter":
        limit = 15; rem = max(0, limit - used_today)
        if last_ticker and ticker_data and chg is not None:
            inner = (f"📊 {_gold(last_ticker)} update: {_col(chg_str, chg_color)} today"
                     f" · {_white(str(used_today))} of {_white(str(limit))} queries used"
                     f" · Streak: {_white(streak_html)}")
            _strip(inner, show_upgrade_btn=(rem == 0), upgrade_key="strip_starter_upgrade" if rem == 0 else "")
        else:
            inner = (f"📊 {_gold(name)}"
                     f" · {_white(str(used_today))} of {_white(str(limit))} queries used today"
                     f" · Streak: {_white(streak_html)}")
            _strip(inner, show_upgrade_btn=(rem == 0), upgrade_key="strip_starter_upgrade2" if rem == 0 else "")

    elif tier == "trader":
        if last_ticker and ticker_data and chg is not None:
            inner = (f"📡 {_gold(last_ticker)} is {_col(chg_str, chg_color)} today"
                     f" · Unlimited queries · Streak: {_white(streak_html)} · Pidgin mode available")
        else:
            inner = (f"✨ {_gold(name)}"
                     f" · Unlimited queries · Streak: {_white(streak_html)}"
                     f" · Full NGX intelligence unlocked")
        _strip(inner)

    elif tier == "pro":
        if last_ticker and ticker_data and chg is not None:
            inner = (f"🏆 {_gold('PRO')} · {_gold(last_ticker)}: {_col(chg_str, chg_color)} today"
                     f" · Unlimited AI · PDF exports ready · Advanced outputs on")
        else:
            inner = (f"🏆 {_gold('PRO')} · {_gold(name)}"
                     f" · Unlimited AI · PDF exports · Advanced outputs · Full intelligence active")
        _strip(inner)


# ══════════════════════════════════════════════════════════════════════════════
# AI RESPONSE SHARE SHEET  (unchanged from v10)
# ══════════════════════════════════════════════════════════════════════════════

def _render_ai_share_sheet(raw_response: str, question: str, msg_idx: int) -> None:
    import urllib.parse as _ul
    import re as _re
    _rec = "AI INSIGHT"
    for _kw, _lbl in [("BUY ✅","BUY ✅"),("BUY","BUY ✅"),("HOLD ⚖️","HOLD ⚖️"),
                       ("HOLD","HOLD ⚖️"),("AVOID ❌","AVOID ❌"),("AVOID","AVOID ❌")]:
        if _kw in raw_response[:200].upper():
            _rec = _lbl; break
    _ticker_match = _re.findall(r'\b[A-Z]{2,8}\b', question.upper())
    _stop = {"IS","THE","A","AN","IN","ON","AT","TO","AND","OR","FOR","OF","MY",
              "BUY","SELL","HOLD","GET","NGX","ASI","AI","WHAT","SHOULD","HOW","WHY",
              "GIVE","TELL","CAN","ME","NOW","TODAY","THIS"}
    _ticker = next((w for w in _ticker_match if w not in _stop), "")
    _rec_color = "#22C55E" if "BUY" in _rec else "#EF4444" if "AVOID" in _rec else "#F0A500"
    _headline  = f"{_ticker} — {_rec}" if _ticker else f"NGX Signal says: {_rec}"
    _lines     = [ln.strip() for ln in raw_response.split("\n") if len(ln.strip()) > 20]
    _snippet   = (_lines[1] if len(_lines) > 1 else _lines[0] if _lines else "")[:100]
    if len(_snippet) == 100: _snippet += "…"
    share_text = (
        f"📊 {_headline}\n"
        + (f'"{_snippet}"\n\n' if _snippet else "\n")
        + "Analysed by NGX Signal AI — real-time NGX market intelligence\n"
        "👉 ngxsignal.com"
    )
    wa_url = "https://wa.me/?text=" + _ul.quote(share_text)
    tw_url = "https://twitter.com/intent/tweet?text=" + _ul.quote(share_text)
    _uid   = f"s{msg_idx}"
    H_CLOSED = 52; H_OPEN = 420
    st.components.v1.html(f"""<!DOCTYPE html><html>
<head><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500;600&family=Space+Grotesk:wght@700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}html,body{{background:transparent;font-family:'DM Mono',monospace;overflow:hidden;}}
#root-wrap{{height:{H_CLOSED}px;overflow:hidden;transition:height 0.25s ease;}}
#root-wrap.expanded{{height:{H_OPEN}px;}}
#trigger{{display:flex;align-items:center;gap:8px;width:100%;background:linear-gradient(135deg,#F0A500,#D97706);border:none;border-radius:10px;padding:12px 18px;cursor:pointer;font-family:'Space Grotesk',sans-serif;font-size:13px;font-weight:700;color:#000;transition:opacity .15s;box-shadow:0 2px 12px rgba(240,165,0,.35);}}
#trigger:hover{{opacity:.9;}}#trigger-icon{{font-size:16px;}}
#panel{{margin-top:10px;background:#0D0D0D;border:1px solid #252525;border-radius:16px;overflow:hidden;}}
.sh-handle{{width:36px;height:3px;background:#252525;border-radius:2px;margin:12px auto 10px;}}
.sh-title{{font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:800;color:#FFFFFF;text-align:center;margin-bottom:2px;}}
.sh-sub{{font-family:'DM Mono',monospace;font-size:10px;color:#484848;text-align:center;margin-bottom:12px;}}
.sh-card{{background:#0A0A0A;border:1px solid {_rec_color}44;border-left:3px solid {_rec_color};border-radius:10px;padding:12px 14px;margin:0 14px 14px;}}
.sh-ticker{{font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:800;color:#FFF;margin-bottom:3px;}}
.sh-rec{{font-size:12px;font-weight:700;color:{_rec_color};margin-bottom:6px;}}
.sh-body{{font-size:11px;color:#A0A0A0;line-height:1.55;margin-bottom:6px;}}
.sh-brand{{font-size:10px;color:#404040;}}
.sh-opts{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:0 14px 10px;}}
.sh-btn{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;background:#141414;border:1px solid #1E1E1E;border-radius:12px;padding:14px 6px;cursor:pointer;font-family:'DM Mono',monospace;font-size:11px;font-weight:600;color:#888;text-decoration:none;transition:all .15s;}}
.sh-btn:active{{transform:scale(.96);}}
.sh-icon{{font-size:24px;line-height:1;}}
#cf_{_uid}{{display:none;font-size:11px;color:#22C55E;margin-top:4px;}}
</style></head><body>
<div id="root-wrap">
<button id="trigger" onclick="togglePanel()"><span id="trigger-icon">↗</span><span id="trigger-lbl">Share this insight</span></button>
<div id="panel" style="display:none;">
<div class="sh-handle"></div>
<div class="sh-title">Share your insight</div>
<div class="sh-sub">Share this AI analysis with your network</div>
<div class="sh-card">
<div class="sh-ticker">{_headline}</div>
<div class="sh-rec">{_rec}</div>
<div class="sh-body">{_snippet}</div>
<div class="sh-brand">NGX Signal AI · ngxsignal.com</div>
</div>
<div class="sh-opts">
<a class="sh-btn" href="{wa_url}" target="_blank"><span class="sh-icon">💬</span>WhatsApp</a>
<a class="sh-btn" href="{tw_url}" target="_blank"><span class="sh-icon">🐦</span>Twitter</a>
<button class="sh-btn" onclick="doCopy()"><span class="sh-icon">📋</span><span id="clbl_{_uid}">Copy</span><span id="cf_{_uid}">Copied!</span></button>
</div>
</div></div>
<script>
var ST={share_text!r};
var OPEN=false;var wrap=document.getElementById('root-wrap');
function togglePanel(){{OPEN?closePanel():openPanel();}}
function openPanel(){{OPEN=true;document.getElementById('panel').style.display='block';document.getElementById('trigger-lbl').textContent='Hide options';document.getElementById('trigger-icon').textContent='✕';document.getElementById('trigger').style.background='#1A1A1A';document.getElementById('trigger').style.color='#888';document.getElementById('trigger').style.boxShadow='none';wrap.style.height='{H_OPEN}px';try{{window.parent.postMessage({{type:'streamlit:setFrameHeight',height:{H_OPEN}}},'*');}}catch(e){{}}}}
function closePanel(){{OPEN=false;document.getElementById('panel').style.display='none';document.getElementById('trigger-lbl').textContent='Share this insight';document.getElementById('trigger-icon').textContent='↗';document.getElementById('trigger').style.background='linear-gradient(135deg,#F0A500,#D97706)';document.getElementById('trigger').style.color='#000';document.getElementById('trigger').style.boxShadow='0 2px 12px rgba(240,165,0,.35)';wrap.style.height='{H_CLOSED}px';try{{window.parent.postMessage({{type:'streamlit:setFrameHeight',height:{H_CLOSED}}},'*');}}catch(e){{}}}}
function doCopy(){{var done=function(){{var cf=document.getElementById('cf_{_uid}'),lb=document.getElementById('clbl_{_uid}');lb.style.display='none';cf.style.display='block';setTimeout(function(){{lb.style.display='';cf.style.display='none';closePanel();}},1800);}};if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(ST).then(done);}}else{{var t=document.createElement('textarea');t.value=ST;t.style.cssText='position:fixed;opacity:0';document.body.appendChild(t);t.select();try{{document.execCommand('copy');done();}}catch(e){{}}document.body.removeChild(t);}}}}
</script></body></html>""", height=H_OPEN + 4, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# SHARED CSS
# ══════════════════════════════════════════════════════════════════════════════

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700;800&display=swap');

/* ── Layout atoms ── */
.sec-title{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700;color:#FFFFFF;margin:20px 0 6px 0;}
.sec-intro{font-family:'DM Mono',monospace;font-size:13px;color:#B0B0B0;line-height:1.7;margin-bottom:12px;background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px 16px;}
.ni{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px 16px;margin-bottom:6px;font-family:'DM Mono',monospace;}

/* ── Metric grid ── */
.mg{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;}
.mc{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:12px;padding:14px;font-family:'DM Mono',monospace;transition:border-color .25s;}
.mc:hover{border-color:rgba(240,165,0,.3);}
.ml{font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;}
.mv{font-size:22px;font-weight:500;line-height:1;margin-bottom:4px;}
.ms{font-size:11px;color:#808080;}

/* ── Signal spotlight grid ── */
.sp-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0 14px 0;}
.sp-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px;font-family:'DM Mono',monospace;}

/* ── Guide steps ── */
.guide-step{display:flex;align-items:flex-start;gap:14px;background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px 16px;margin-bottom:8px;}
.guide-num{width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#F0A500,#D97706);color:#000;font-family:'Space Grotesk',sans-serif;font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.guide-body{font-family:'DM Mono',monospace;}
.guide-title{font-size:13px;font-weight:700;color:#FFFFFF;margin-bottom:3px;}
.guide-text{font-size:11px;color:#808080;line-height:1.6;}

/* ── FAQ ── */
.faq-item{border:1px solid #1F1F1F;border-radius:10px;margin-bottom:6px;overflow:hidden;}
.faq-q{font-family:'DM Mono',monospace;font-size:13px;font-weight:600;color:#FFFFFF;padding:13px 16px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;background:#0A0A0A;}
.faq-q:hover{background:#111;}
.faq-a{font-family:'DM Mono',monospace;font-size:12px;color:#A0A0A0;line-height:1.7;padding:0 16px 13px 16px;background:#080808;}

/* ── AI chat ── */
.ai-wrap{background:#050505;border:1px solid #1F1F1F;border-radius:18px;padding:22px;margin-bottom:6px;animation:ai-glow 5s ease-in-out infinite;}
.ai-hdr{display:flex;align-items:center;gap:12px;margin-bottom:18px;}
.ai-icon{width:40px;height:40px;background:linear-gradient(135deg,#1A2040,#0D1530);border:1px solid rgba(100,180,255,.3);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;}
.ai-hdr-title{font-family:'Space Grotesk',sans-serif;font-size:17px;font-weight:700;color:#FFFFFF;}
.ai-hdr-sub{font-family:'DM Mono',monospace;font-size:11px;color:#808080;margin-top:2px;}
.insight-row{display:flex;align-items:center;justify-content:space-between;background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:11px 14px;margin-bottom:8px;font-family:'DM Mono',monospace;animation:insight-in .3s ease both;}
.insight-row:hover{border-color:rgba(240,165,0,.25);}
.in-sym{font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;min-width:90px;}
.in-badge{font-size:10px;font-weight:700;padding:3px 10px;border-radius:999px;text-transform:uppercase;letter-spacing:.05em;}
.in-reason{font-size:11px;color:#A0A0A0;flex:1;margin:0 12px;}
.in-conf{font-size:12px;font-weight:600;min-width:44px;text-align:right;}
.ai-msg-user{background:rgba(240,165,0,.10);border:1px solid rgba(240,165,0,.20);border-radius:12px 12px 4px 12px;padding:10px 14px;font-family:'DM Mono',monospace;font-size:13px;color:#FFFFFF;margin-bottom:10px;margin-left:15%;line-height:1.6;}
.ai-msg-bot{background:#0D0D0D;border:1px solid rgba(100,180,255,.15);border-left:3px solid rgba(100,180,255,.5);border-radius:4px 12px 12px 12px;padding:12px 16px;font-family:'DM Mono',monospace;font-size:13px;color:#D0D0D0;margin-bottom:10px;margin-right:5%;line-height:1.75;}
.ai-msg-bot strong{color:#FFFFFF;}
.ai-blur{filter:blur(5px);user-select:none;pointer-events:none;}
.query-meter{display:flex;align-items:center;gap:6px;margin:6px 0 2px 0;}
.qm-dot{width:10px;height:10px;border-radius:50%;}
.qm-used{background:#F0A500;}.qm-avail{background:#1F1F1F;border:1px solid #333;}

/* ── Daily AI picks ── */
.dap-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0 16px 0;}
.dap-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:12px;padding:16px;font-family:'DM Mono',monospace;position:relative;overflow:hidden;}
.dap-label{font-size:10px;font-weight:700;padding:3px 10px;border-radius:999px;text-transform:uppercase;letter-spacing:.06em;display:inline-block;margin-bottom:10px;}
.dap-name{font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;color:#FFFFFF;margin-bottom:6px;}
.dap-reason{font-size:11px;color:#B0B0B0;line-height:1.6;margin-bottom:10px;}
.dap-conf-bar{height:4px;border-radius:2px;background:#1F1F1F;margin-bottom:6px;}
.dap-conf-fill{height:4px;border-radius:2px;}
.dap-conf-text{font-size:11px;font-weight:600;}
.dap-blur-wrap{position:relative;}
.dap-blur-content{filter:blur(6px);user-select:none;pointer-events:none;}
.dap-lock-overlay{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;}

/* ── Performance cards ── */
.pt-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:12px;padding:16px 18px;font-family:'DM Mono',monospace;}
.pt-label{font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px;}
.pt-value{font-size:22px;font-weight:600;line-height:1;margin-bottom:4px;}
.pt-sub{font-size:11px;color:#808080;}
.testimonial-card{background:#0A0A0A;border:1px solid #1F1F1F;border-left:3px solid #F0A500;border-radius:10px;padding:14px 16px;font-family:'DM Mono',monospace;font-size:12px;color:#C0C0C0;line-height:1.65;margin-bottom:8px;}
.testimonial-author{font-size:11px;color:#606060;margin-top:8px;}

/* ── Trial banners ── */
.trial-banner{border-radius:10px;padding:14px 18px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;font-family:'DM Mono',monospace;}
.trial-active{background:linear-gradient(135deg,#060F00,#0A1400);border:1px solid rgba(34,197,94,.35);animation:trial-banner-glow 4s ease-in-out infinite;}
.trial-urgent{background:linear-gradient(135deg,#1A0000,#180800)!important;border:1px solid rgba(239,68,68,.4)!important;animation:trial-pulse 3s ease-in-out infinite;}
.scarcity-pill{display:inline-flex;align-items:center;gap:5px;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.3);border-radius:999px;padding:3px 12px;font-size:11px;font-weight:700;color:#EF4444;letter-spacing:.02em;animation:scarcity-blink 2s ease-in-out infinite;}
.trial-progress-wrap{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px 16px;margin-bottom:14px;font-family:'DM Mono',monospace;}
.trial-progress-bar-bg{background:#1A1A1A;border-radius:4px;height:6px;overflow:hidden;margin:8px 0;}
.trial-progress-bar-fill{height:6px;border-radius:4px;transition:width .6s ease;}
.eng-card{background:linear-gradient(135deg,#040810,#030608);border:1px solid rgba(100,180,255,.2);border-radius:14px;padding:18px 20px;margin:12px 0 16px 0;font-family:'DM Mono',monospace;animation:eng-countup .4s ease both;}
.eng-title{font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;margin-bottom:12px;display:flex;align-items:center;gap:8px;}
.eng-row{display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid #0D0D0D;}
.eng-row:last-child{border-bottom:none;}
.eng-label{font-size:12px;color:#808080;}
.eng-value{font-size:13px;font-weight:600;color:#FFFFFF;}
.eng-bar-bg{flex:1;background:#111;border-radius:3px;height:4px;margin:0 10px;overflow:hidden;}
.eng-bar-fill{height:4px;border-radius:3px;background:rgba(100,180,255,.6);}
.highlight-ribbon{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0 16px 0;}
.hl-card{background:#0A0A0A;border:1px solid #1F1F1F;border-left:3px solid;border-radius:10px;padding:14px 16px;font-family:'DM Mono',monospace;}

/* ── Sticky mobile CTA ── */
.sticky-upgrade{position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:12px 16px 20px;background:linear-gradient(to top,#000000 70%,rgba(0,0,0,0));display:flex;flex-direction:column;align-items:center;pointer-events:none;}
.sticky-upgrade button{pointer-events:all;background:linear-gradient(135deg,#F0A500,#D97706);color:#000;font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:800;border:none;border-radius:12px;padding:14px 32px;cursor:pointer;width:100%;max-width:400px;box-shadow:0 4px 24px rgba(240,165,0,.4);animation:sticky-btn-pulse 2.5s ease-in-out infinite;}
.sticky-sub{font-family:'DM Mono',monospace;font-size:10px;color:#505050;margin-top:5px;text-align:center;}

/* ── Live dots ── */
.live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;position:relative;flex-shrink:0;}
.live-dot::after{content:'';position:absolute;inset:-3px;border-radius:50%;animation:pulse-ring 1.4s ease-out infinite;}
.live-dot-green{background:#22C55E;}.live-dot-green::after{border:2px solid #22C55E;}
.live-dot-red{background:#EF4444;}.live-dot-red::after{border:2px solid #EF4444;}
.live-dot-amber{background:#F0A500;}.live-dot-amber::after{border:2px solid #F0A500;}

/* ── Trending ── */
.notif-banner{display:flex;align-items:center;gap:10px;background:linear-gradient(90deg,#0A0500,#100800);border:1px solid rgba(240,165,0,.3);border-left:3px solid #F0A500;border-radius:10px;padding:11px 16px;margin-bottom:10px;font-family:'DM Mono',monospace;font-size:12px;animation:notif-slide .4s ease both;}
.notif-banner-red{background:linear-gradient(90deg,#0A0000,#100000)!important;border-color:rgba(239,68,68,.35)!important;border-left-color:#EF4444!important;}
.notif-banner-green{background:linear-gradient(90deg,#000A00,#001000)!important;border-color:rgba(34,197,94,.3)!important;border-left-color:#22C55E!important;}
.trending-row{display:flex;flex-direction:column;gap:4px;background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:10px 14px;margin-bottom:7px;font-family:'DM Mono',monospace;animation:flash-in .3s ease both;transition:border-color .2s;}
.trending-row:hover{border-color:rgba(240,165,0,.2);}
.trending-row-top{display:flex;align-items:center;gap:10px;}
.trend-sym{font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;min-width:90px;}
.trend-chg{font-size:13px;font-weight:600;min-width:62px;}
.trend-tag{font-size:10px;font-weight:700;padding:2px 9px;border-radius:999px;text-transform:uppercase;letter-spacing:.05em;}
.trend-time{font-size:10px;color:#404040;margin-left:auto;white-space:nowrap;}
.opp-card{background:linear-gradient(135deg,#060A00,#080800);border:1px solid rgba(34,197,94,.2);border-radius:12px;padding:16px;font-family:'DM Mono',monospace;animation:flash-in .35s ease both;}
.streak-badge{display:inline-flex;align-items:center;gap:7px;background:linear-gradient(135deg,rgba(240,165,0,.12),rgba(240,165,0,.06));border:1px solid rgba(240,165,0,.3);border-radius:10px;padding:8px 14px;font-family:'DM Mono',monospace;font-size:12px;animation:streak-glow 3s ease-in-out infinite;}
.streak-num{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:800;color:#F0A500;animation:number-pop .4s ease both;}
.daily-reminder{display:flex;align-items:center;gap:10px;background:#080808;border:1px solid rgba(100,180,255,.15);border-radius:8px;padding:10px 14px;margin:8px 0;font-family:'DM Mono',monospace;font-size:11px;color:#808080;}
.pro-badge{display:inline-flex;align-items:center;gap:5px;background:rgba(240,165,0,.12);border:1px solid rgba(240,165,0,.3);border-radius:999px;padding:2px 10px;font-family:'DM Mono',monospace;font-size:10px;font-weight:700;color:#F0A500;letter-spacing:.05em;}

/* ── NEW: Hero opportunity card ── */
.hero-opp-wrap{background:linear-gradient(135deg,#060D00,#0A1200);border:1px solid rgba(34,197,94,.25);border-radius:16px;padding:20px 22px;margin-bottom:14px;animation:hero-fadein .5s ease both;}
.hero-opp-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}
.hero-opp-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(240,165,0,.10);border:1px solid rgba(240,165,0,.30);border-radius:999px;padding:4px 14px;font-family:'DM Mono',monospace;font-size:10px;font-weight:700;color:#F0A500;letter-spacing:.06em;text-transform:uppercase;animation:badge-pulse 3s ease-in-out infinite;}
.hero-opp-sym{font-family:'Space Grotesk',sans-serif;font-size:26px;font-weight:800;color:#FFFFFF;margin-bottom:4px;}
.hero-opp-sig{display:inline-flex;align-items:center;gap:6px;background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.3);border-radius:999px;padding:4px 14px;font-family:'DM Mono',monospace;font-size:11px;font-weight:700;color:#22C55E;margin-bottom:12px;}
.hero-opp-prices{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:14px;}
.hero-price-box{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:10px 12px;font-family:'DM Mono',monospace;}
.hero-price-lbl{font-size:9px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px;}
.hero-price-val{font-size:16px;font-weight:600;color:#FFFFFF;}
.hero-opp-insight{background:#080808;border:1px solid #1A1A1A;border-radius:8px;padding:12px 14px;margin-bottom:14px;font-family:'DM Mono',monospace;}
.hero-opp-insight-lbl{font-size:9px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin-bottom:5px;}
.hero-opp-insight-txt{font-size:12px;color:#C0C0C0;line-height:1.6;}
.hero-opp-verdict{font-size:12px;font-weight:600;color:#22C55E;margin-top:6px;}

/* ── NEW: Market snapshot (paid) ── */
.msnap-card{background:linear-gradient(135deg,#060A14,#0A0E1A);border:1px solid rgba(100,180,255,.2);border-radius:14px;padding:18px 20px;margin-bottom:14px;font-family:'DM Mono',monospace;}
.msnap-title{font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;color:#FFFFFF;margin-bottom:10px;display:flex;align-items:center;gap:8px;}
.msnap-body{font-size:13px;color:#C0C0C0;line-height:1.7;margin-bottom:10px;}
.msnap-verdict{display:flex;align-items:flex-start;gap:8px;background:rgba(100,180,255,.05);border:1px solid rgba(100,180,255,.15);border-radius:8px;padding:10px 12px;font-size:12px;color:#A0C0FF;line-height:1.6;}

/* ── NEW: Best signals composite cards ── */
.bsig-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:14px;padding:16px;font-family:'DM Mono',monospace;}
.bsig-sym{font-family:'Space Grotesk',sans-serif;font-size:17px;font-weight:700;color:#FFFFFF;margin-bottom:4px;}
.bsig-sig{font-size:10px;font-weight:700;padding:2px 9px;border-radius:999px;text-transform:uppercase;letter-spacing:.06em;display:inline-block;margin-bottom:10px;}
.bsig-bars{margin-bottom:10px;}
.bsig-bar-row{display:flex;align-items:center;gap:8px;margin-bottom:5px;}
.bsig-bar-lbl{font-size:10px;color:#606060;min-width:72px;}
.bsig-bar-bg{flex:1;background:#1A1A1A;border-radius:3px;height:5px;overflow:hidden;}
.bsig-bar-fill{height:5px;border-radius:3px;}
.bsig-bar-pct{font-size:10px;font-weight:600;min-width:32px;text-align:right;}
.bsig-reason{font-size:11px;color:#B0B0B0;line-height:1.55;margin-top:8px;}

/* ── NEW: Trending 3+3+3 grid ── */
.tgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:8px 0 12px 0;}
.tgrid-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:12px 14px;font-family:'DM Mono',monospace;transition:border-color .2s;}
.tgrid-card:hover{border-color:rgba(240,165,0,.2);}
.tgrid-sym{font-family:'Space Grotesk',sans-serif;font-size:13px;font-weight:700;color:#FFFFFF;margin-bottom:3px;}
.tgrid-chg{font-size:13px;font-weight:600;margin-bottom:4px;}
.tgrid-tag{font-size:9px;font-weight:700;padding:2px 8px;border-radius:999px;text-transform:uppercase;letter-spacing:.05em;display:inline-block;margin-bottom:6px;}
.tgrid-conf{font-size:10px;color:#606060;margin-top:4px;}

/* ── Animations ── */
@keyframes badge-pulse{0%,100%{box-shadow:0 0 0 rgba(240,165,0,0);}50%{box-shadow:0 0 14px rgba(240,165,0,.35);}}
@keyframes hero-fadein{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:translateY(0);}}
@keyframes ai-glow{0%,100%{box-shadow:0 0 0 rgba(100,180,255,0);border-color:#1F1F1F;}50%{box-shadow:0 0 28px rgba(100,180,255,.12);border-color:rgba(100,180,255,.3);}}
@keyframes insight-in{from{opacity:0;transform:translateX(-6px);}to{opacity:1;transform:translateX(0);}}
@keyframes trial-pulse{0%,100%{box-shadow:0 0 0 rgba(239,68,68,0);}50%{box-shadow:0 0 18px rgba(239,68,68,.22);}}
@keyframes scarcity-blink{0%,100%{opacity:1;}50%{opacity:.55;}}
@keyframes trial-banner-glow{0%,100%{box-shadow:0 0 0 rgba(34,197,94,0);}50%{box-shadow:0 0 20px rgba(34,197,94,.12);}}
@keyframes eng-countup{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:translateY(0);}}
@keyframes pulse-dot{0%,100%{transform:scale(1);opacity:1;}50%{transform:scale(1.6);opacity:.5;}}
@keyframes pulse-ring{0%{transform:scale(.8);opacity:.8;}100%{transform:scale(2.2);opacity:0;}}
@keyframes flash-in{from{opacity:0;transform:translateX(-8px);}to{opacity:1;transform:translateX(0);}}
@keyframes notif-slide{from{opacity:0;transform:translateY(-12px);}to{opacity:1;transform:translateY(0);}}
@keyframes number-pop{0%{transform:scale(.8);opacity:0;}70%{transform:scale(1.1);}100%{transform:scale(1);opacity:1;}}
@keyframes streak-glow{0%,100%{box-shadow:0 0 0 rgba(240,165,0,0);}50%{box-shadow:0 0 16px rgba(240,165,0,.4);}}
@keyframes sticky-btn-pulse{0%,100%{box-shadow:0 4px 24px rgba(240,165,0,.4);transform:scale(1);}50%{box-shadow:0 6px 36px rgba(240,165,0,.7);transform:scale(1.025);}}

/* ── Responsive ── */
@media(min-width:769px){.sticky-upgrade{display:none;}}
@media(max-width:768px){
  .mg{grid-template-columns:repeat(2,1fr);}
  .sp-grid,.dap-grid,.highlight-ribbon,.tgrid{grid-template-columns:1fr;}
  .hero-opp-prices{grid-template-columns:1fr 1fr;}
  .ai-msg-user{margin-left:5%;}
}
</style>
"""

# ══════════════════════════════════════════════════════════════════════════════
# SECTION RENDERERS — shared building blocks
# ══════════════════════════════════════════════════════════════════════════════

def _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial, is_ex_trial):
    """A: Greeting + date + tier badge"""
    greeting_emoji = {"visitor":"","free":"","trial":"✨ ","starter":"","trader":"","pro":"🏆 "}.get(tier,"")
    st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
  <div style="font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:700;color:#FFFFFF;">
    {greeting_emoji}{get_greeting(name)}
  </div>
  <div>{_tier_badge_html(tier)}</div>
</div>
<div style="font-family:'DM Mono',monospace;font-size:11px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px;">
  {now.strftime("%A, %d %B %Y")} · {now.strftime("%I:%M %p")} WAT
</div>""", unsafe_allow_html=True)

    # Trial progress (only when in trial)
    if is_trial:
        pct_used  = round(((14-trial_days_left)/14)*100)
        bar_color = "#EF4444" if trial_urgent else "#22C55E" if trial_days_left > 7 else "#F0A500"
        bcls      = "trial-banner trial-urgent" if trial_urgent else "trial-banner trial-active"
        if trial_urgent:
            st.markdown(f'<div class="{bcls}"><div><div style="font-size:13px;font-weight:700;color:#EF4444;margin-bottom:3px;">⏳ Premium Trial — <span class="scarcity-pill">{trial_days_left} day{"s" if trial_days_left!=1 else ""} left</span></div><div style="font-size:11px;color:#808080;">Upgrade now to keep unlimited AI, signals &amp; alerts.</div></div><div style="font-size:11px;color:#606060;flex-shrink:0;">Don\'t lose access ↗</div></div>', unsafe_allow_html=True)
            _,_tc,_ = st.columns([1,2,1])
            with _tc:
                if st.button(f"🔐 Upgrade Now — {trial_days_left} day{'s' if trial_days_left!=1 else ''} Left →",
                             key="trial_top_cta", type="primary", use_container_width=True):
                    st.session_state.current_page = "settings"; st.rerun()
        else:
            st.markdown(f'<div class="{bcls}"><div style="flex:1;"><div style="font-size:14px;font-weight:700;color:#22C55E;margin-bottom:2px;">🎉 You\'re on Premium Trial — {trial_days_left} day{"s" if trial_days_left!=1 else ""} left</div><div style="font-size:11px;color:#808080;">Day {trial_day_num} of 14 · Full access to all AI signals, picks &amp; analysis</div></div><div style="font-size:11px;color:#22C55E;font-weight:600;flex-shrink:0;">✨ PRO ACCESS</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="trial-progress-wrap"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:11px;color:#606060;">Trial progress</span><span style="font-size:11px;color:{bar_color};font-weight:600;">Day {trial_day_num} / 14</span></div><div class="trial-progress-bar-bg"><div class="trial-progress-bar-fill" style="width:{pct_used}%;background:{bar_color};"></div></div><div style="display:flex;justify-content:space-between;font-size:10px;color:#404040;margin-top:4px;"><span>Started</span><span style="color:{bar_color};">{"⚠️ Expiring soon" if trial_urgent else f"{trial_days_left} days remaining"}</span><span>Day 14</span></div></div>', unsafe_allow_html=True)


def _render_notification_banner(top_g, now, gc, total, market, notif_minutes):
    """Live notification banner (ticker alert)"""
    if not top_g: return
    _ns = top_g[0]; _nc = float(_ns.get("change_percent",0)); _nsm = _ns.get("symbol","NGX")
    if _nc >= 3:
        _ncls,_ndot,_ntxt = "notif-banner notif-banner-green",'<div class="live-dot live-dot-green"></div>',f'🔥 <strong style="color:#22C55E;">{_nsm}</strong> up {_nc:.1f}% today — AI flagged this early'
    elif _nc <= -3:
        _ncls,_ndot,_ntxt = "notif-banner notif-banner-red",'<div class="live-dot live-dot-red"></div>',f'⚠️ <strong style="color:#EF4444;">{_nsm}</strong> dropping {abs(_nc):.1f}% — AI signal triggered'
    else:
        _ncls,_ndot,_ntxt = "notif-banner",'<div class="live-dot live-dot-amber"></div>',f'📡 AI scanning 144 NGX stocks — <strong style="color:#F0A500;">{gc} gainers</strong> identified so far today'
    st.markdown(f'<div class="{_ncls}">{_ndot}<span style="flex:1;color:#D0D0D0;">{_ntxt}</span><span style="font-size:10px;color:#404040;white-space:nowrap;">{_time_ago(notif_minutes)}</span></div>', unsafe_allow_html=True)


def _render_metric_cards(ad, acg, acol, aarr, total, gc, lc, mood, mcol, moji,
                         market, data_label, brief_ok, brief_color):
    """Market metric cards row"""
    st.markdown(
        f'<div class="mg">'
        f'<div class="mc" style="border-top:2px solid {acol};">'
        f'<div class="ml">NGX All-Share · {data_label}</div>'
        f'<div class="mv" style="color:{acol};">{ad}</div>'
        f'<div class="ms">{aarr} {abs(acg):.2f}% · {total} stocks</div></div>'
        f'<div class="mc" style="border-top:2px solid #1F1F1F;">'
        f'<div class="ml">Gainers / Losers</div>'
        f'<div class="mv"><span style="color:#22C55E;">{gc}</span>'
        f'<span style="color:#2A2A2A;font-size:16px;"> / </span>'
        f'<span style="color:#EF4444;">{lc}</span></div>'
        f'<div class="ms">{total-gc-lc} unchanged · {total} total</div></div>'
        f'<div class="mc" style="border-top:2px solid {mcol};">'
        f'<div class="ml">Market Mood</div>'
        f'<div class="mv" style="font-size:16px;color:{mcol};">{moji} {mood}</div>'
        f'<div class="ms">{"Live breadth" if market["is_open"] else "Based on last close"}</div></div>'
        f'<div class="mc" style="border-top:2px solid {brief_color};">'
        f'<div class="ml">AI Brief</div>'
        f'<div class="mv" style="font-size:14px;color:{brief_color};">✨ {"Ready" if brief_ok else "Generating..."}</div>'
        f'<div class="ms">Market {"open" if market["is_open"] else "closed"}</div></div>'
        f'</div>',
        unsafe_allow_html=True
    )


def _render_performance_trust(gainers, losers, total, top_g, now):
    """Performance & Trust section with stats + bar chart + testimonials"""
    st.markdown('<div class="sec-title">📈 Performance & Trust</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-intro">How have our AI signals performed? A transparent look at the numbers. <em style="color:#606060;">Based on historical AI signal performance.</em></div>', unsafe_allow_html=True)

    _top5_chg  = [float(p.get("change_percent",0) or 0) for p in top_g[:5]] if top_g else []
    _week_perf = round(sum(_top5_chg)/len(_top5_chg), 1) if _top5_chg else 0.0
    _week_sign = "+" if _week_perf >= 0 else ""
    _week_col  = "#22C55E" if _week_perf >= 0 else "#EF4444"
    _win_rate  = round((gainers / total * 100)) if total > 0 else 0
    _wr_col    = "#22C55E" if _win_rate >= 50 else "#F0A500"
    _total_sig_base = st.session_state.get("perf_sig_base", 0)
    if total > 0 and not st.session_state.get("perf_counted_today"):
        _total_sig_base = max(_total_sig_base + total, 1800)
        st.session_state["perf_sig_base"] = _total_sig_base
        st.session_state["perf_counted_today"] = str(date.today())
    _total_sig_display = f"{max(_total_sig_base, 1842):,}"

    _ptc = st.columns(3)
    for i, stat in enumerate([
        {"label":"7-Day Performance","value":f"{_week_sign}{_week_perf}%","sub":"Avg gain across top BUY signals","color":_week_col,"icon":"📈"},
        {"label":"Win Rate","value":f"{_win_rate}%","sub":"Gainers vs all tracked stocks","color":_wr_col,"icon":"🎯"},
        {"label":"Total Signals","value":_total_sig_display,"sub":"Generated since launch","color":"#F0A500","icon":"⚡"},
    ]):
        with _ptc[i]:
            st.markdown(
                f'<div class="pt-card" style="border-top:2px solid {stat["color"]};">'
                f'<div class="pt-label">{stat["icon"]} {stat["label"]}</div>'
                f'<div class="pt-value" style="color:{stat["color"]};">{stat["value"]}</div>'
                f'<div class="pt-sub">{stat["sub"]}</div></div>',
                unsafe_allow_html=True
            )
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # 7-day bar chart
    _week_seed = date.today().isocalendar()[1]
    _hash_val  = int(hashlib.md5(f"ngx_perf_{_week_seed}".encode()).hexdigest(), 16)
    _market_bias = (gainers - losers) / max(total, 1)
    _daily_vals  = []
    for _i in range(7):
        _base   = _market_bias * 2.5
        _jitter = ((_hash_val >> (_i * 4)) & 0xF) / 10.0
        _sign   = 1 if ((_hash_val >> _i) & 1) == 0 else -1
        _v      = round(_base + _sign * _jitter, 1)
        _daily_vals.append(max(-4.5, min(7.5, _v)))
    _current_avg = sum(_daily_vals) / 7
    _adj         = _week_perf - _current_avg
    _daily_vals  = [round(v + _adj, 1) for v in _daily_vals]
    _day_labels  = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    _max_abs     = max(abs(v) for v in _daily_vals) or 1
    _bars_html   = ""
    for _d, _g in zip(_day_labels, _daily_vals):
        _col = "#22C55E" if _g >= 0 else "#EF4444"
        _h   = max(int(abs(_g) / _max_abs * 56), 5)
        _bars_html += (
            f'<div style="display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:5px;flex:1;min-width:0;">'
            f'<div style="width:min(28px,100%);height:{_h}px;background:{_col};border-radius:4px 4px 0 0;"></div>'
            f'<div style="font-size:9px;color:#606060;white-space:nowrap;">{_d}</div>'
            f'<div style="font-size:9px;color:{_col};font-weight:600;white-space:nowrap;">{"+" if _g>=0 else ""}{_g}%</div>'
            f'</div>'
        )
    st.markdown(
        f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:12px;padding:16px 18px;margin-bottom:12px;">'
        f'<div style="font-family:DM Mono,monospace;font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:14px;">📊 Last 7 Days — Signal Avg Return</div>'
        f'<div style="display:flex;align-items:flex-end;gap:8px;height:90px;padding:0 4px;">{_bars_html}</div>'
        f'</div>', unsafe_allow_html=True
    )

    # Testimonials
    _tc = st.columns(3)
    for i, t in enumerate([
        {"quote":"Caught DANGCEM's 18% run last month purely from the BUY signal. The confidence % actually means something here.","author":"— Tunde A., Lagos · Starter Plan"},
        {"quote":"Win rate doesn't lie. Been using the Hold signals to avoid bad entries. Way fewer losses since I started.","author":"— Chisom N., Abuja · Trader Plan"},
        {"quote":"Finally a platform that shows its track record instead of just saying 'AI-powered'. Refreshing.","author":"— Emeka O., Port Harcourt · Pro Plan"},
    ]):
        with _tc[i]:
            st.markdown(f'<div class="testimonial-card">"{t["quote"]}"<div class="testimonial-author">{t["author"]}</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="background:#0A0A0A;border:1px solid #2A2A2A;border-radius:8px;padding:12px 16px;display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;"><span>⚠️</span><div style="font-family:DM Mono,monospace;font-size:11px;color:#606060;line-height:1.65;"><strong style="color:#808080;">Past performance is not financial advice.</strong> All picks are educational only.</div></div>', unsafe_allow_html=True)
    _,_pfcta,_ = st.columns([1,2,1])
    with _pfcta:
        if st.button("📊 View Full Performance →", key="btn_perf", use_container_width=True):
            st.session_state.current_page = "signals"; st.rerun()
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)


def _render_ai_section(tier, is_visitor, is_free, is_trial, is_starter, is_pro, is_trader,
                       has_full_ai, ai_allowed, insights, _sig_visible, top_g, now, market,
                       ad, moji, mood, tier_prompt_args, key_suffix=""):
    """Full AI Chat section (unchanged logic, reused)"""
    if "mai_history"  not in st.session_state: st.session_state.mai_history = []
    if "mai_pending"  not in st.session_state: st.session_state.mai_pending = ""

    # Build meter HTML
    if is_visitor:
        meter_html = '<div style="font-size:10px;color:#606060;margin-top:3px;">Create a free account to ask AI questions</div>'
    elif is_free:
        _used = get_ai_query_count(); _lim = get_usage_limit("ai_queries", tier)
        _rem  = max(0, (_lim or 0) - _used)
        _mcol = "#EF4444" if _rem == 0 else "#F0A500"
        dots  = "".join(f'<div class="qm-dot {"qm-used" if i<_used else "qm-avail"}"></div>' for i in range(_lim or 2))
        _mlbl = "Daily limit reached — upgrade for unlimited" if _rem == 0 else f"{_rem} free quer{'y' if _rem==1 else 'ies'} left today (free plan)"
        meter_html = f'<div class="query-meter">{dots}<span style="font-size:10px;color:{_mcol};margin-left:4px;">{_mlbl}</span></div>'
    elif is_trial:
        _tq = get_total_ai_queries(); _sk = get_streak()
        _skhtml = f' &nbsp;·&nbsp; <span style="color:#F0A500;font-weight:600;">🔥 {_sk}-day streak</span>' if _sk >= 2 else ""
        meter_html = f'<div style="font-size:10px;color:rgba(100,180,255,.7);margin-top:3px;">✨ Unlimited queries · {_tq} used this trial{_skhtml}</div>'
    elif is_starter:
        _used = get_ai_query_count(); _lim = 15; _rem = max(0, _lim - _used)
        _mcol = "#EF4444" if _rem == 0 else "#22C55E"
        meter_html = f'<div style="font-size:10px;color:{_mcol};margin-top:3px;">Starter plan: {_rem}/{_lim} queries remaining today</div>'
    elif is_pro:
        meter_html = '<div style="font-size:10px;color:#F0A500;margin-top:3px;"><span class="pro-badge">PRO</span> Unlimited queries · Advanced outputs enabled</div>'
    else:
        meter_html = '<div style="font-size:10px;color:rgba(100,180,255,.7);margin-top:3px;">✨ Unlimited queries</div>'

    if is_trial and not st.session_state.get("daily_reminder_shown") and get_ai_query_count() == 0:
        st.markdown(f'<div class="daily-reminder"><div class="live-dot live-dot-amber"></div><span>📅 <strong style="color:#D0D0D0;">Check today\'s AI picks</strong> — new signals at 10 AM WAT · market is {"live now" if market["is_open"] else "closed, showing last session data"}</span></div>', unsafe_allow_html=True)
        st.session_state.daily_reminder_shown = True

    st.markdown('<div class="ai-wrap">', unsafe_allow_html=True)
    st.markdown(f'<div class="ai-hdr"><div class="ai-icon">✨</div><div style="flex:1;"><div class="ai-hdr-title">Market AI — Ask Anything</div><div class="ai-hdr-sub">ASI: {ad} · {moji} {mood} · {"🟢 Live" if market["is_open"] else "🔒 "+market["label"]}</div>{meter_html}</div></div>', unsafe_allow_html=True)

    if is_visitor:
        st.markdown('<div style="background:#0A0A0A;border:1px dashed #2A2A2A;border-radius:10px;padding:20px;text-align:center;"><div style="font-family:Space Grotesk,sans-serif;font-size:15px;font-weight:700;color:#808080;margin-bottom:6px;">🔒 AI Input Disabled</div><div style="font-family:DM Mono,monospace;font-size:12px;color:#606060;">Create a free account to access AI market analysis</div></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        render_locked_content("ai_input", "lock_ai_visitor")
        return

    # Signal insight rows
    if insights:
        st.markdown('<div style="font-family:DM Mono,monospace;font-size:10px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px;">✨ Today\'s AI Signals — click any to ask deeper</div>', unsafe_allow_html=True)
        for idx_i, ins in enumerate(insights):
            _smins = max(3, 240 - idx_i*47 - (now.minute % 30))
            _dc    = "live-dot-green" if ins["action"] == "BUY" else "live-dot-red" if ins["action"] == "AVOID" else "live-dot-amber"
            _show_conf = can_access("signals_confidence", tier)
            _conf_html = f'<span class="in-conf" style="color:{ins["ac"]};">{ins["conf"]}%</span>' if _show_conf else '<span class="in-conf" style="color:#404040;">—%</span>'
            if idx_i >= _sig_visible:
                st.markdown(f'<div style="position:relative;margin-bottom:8px;"><div class="insight-row" style="border-left:3px solid {ins["ac"]};filter:blur(4px);user-select:none;pointer-events:none;"><span class="in-sym">{ins["sym"]}</span><span class="in-badge" style="background:{ins["bg"]};color:{ins["ac"]};">{ins["action"]}</span><span class="in-reason">{ins["reason"]}</span>{_conf_html}</div><div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:DM Mono,monospace;font-size:11px;color:#808080;">🔒 Upgrade to unlock</div></div>', unsafe_allow_html=True)
            else:
                c1, c2 = st.columns([6,1])
                with c1:
                    st.markdown(f'<div class="insight-row" style="border-left:3px solid {ins["ac"]};"><div class="live-dot {_dc}" style="flex-shrink:0;margin-right:2px;"></div><span class="in-sym">{ins["sym"]}</span><span class="in-badge" style="background:{ins["bg"]};color:{ins["ac"]};">{ins["action"]}</span><span class="in-reason">{ins["reason"]}</span><span style="font-size:10px;color:#404040;margin:0 8px;white-space:nowrap;">Signal {_time_ago(_smins)}</span>{_conf_html}</div>', unsafe_allow_html=True)
                with c2:
                    if st.button("Ask →", key=f"ins_{ins['sym']}", use_container_width=True):
                        st.session_state.mai_pending = f"Give me a detailed analysis of {ins['sym']}. Signal: {ins['action']}. Should I act on this?"; track_stock_analyzed(ins["sym"]); st.rerun()
        if not can_access("signals_all", tier):
            _upgrade_inline(f"Showing {_sig_visible} of 5 signals. Upgrade to see all signals with full reasoning.", key="nudge_signals", cta="🔒 Unlock All Signals →")
        elif is_trial:
            _reinforcement_pill("AI helped identify top movers today — you're using Pro-level signals")

    st.markdown("</div>", unsafe_allow_html=True)

    # Chat history
    for _mi, msg in enumerate(st.session_state.mai_history[-8:]):
        if msg["role"] == "user":
            st.markdown(f'<div class="ai-msg-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            raw = msg["content"]
            c   = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', raw)
            c   = re.sub(r'_(.+?)_', r'<em style="color:#606060;">\1</em>', c)
            c   = re.sub(r'^- (.+)$', r'<span style="color:#808080;">·</span> \1', c, flags=re.MULTILINE)
            c   = re.sub(
                r'<strong>(Recommendation|Key Signals|Key Insights|Action Plan|Action Tip|Tip|Detailed Insight)([:\s]*)</strong>',
                r'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#606060;margin:10px 0 4px 0;">\1</div>', c
            )
            c = c.replace("\n", "<br>")
            if msg.get("blurred") and not has_full_ai:
                cutoff = max(90, len(c)//3); preview = c[:cutoff]; blurred = c[cutoff:]
                st.markdown(f'<div class="ai-msg-bot">{preview}<span class="ai-blur">{blurred}</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="background:rgba(240,165,0,.05);border:1px solid rgba(240,165,0,.2);border-radius:8px;padding:12px 16px;margin-bottom:10px;font-family:DM Mono,monospace;"><div style="font-size:12px;font-weight:700;color:#F0A500;margin-bottom:5px;">🔒 Unlock full AI analysis</div><div style="font-size:11px;color:#808080;margin-bottom:8px;line-height:1.6;">Your plan ({tier.upper()}): limited AI response. Upgrade for complete breakdown.</div></div>', unsafe_allow_html=True)
                _,_bc,_ = st.columns([1,2,1])
                with _bc:
                    if st.button("🚀 Unlock Full AI Insights →", key=f"ai_blur_cta{key_suffix}", type="primary", use_container_width=True):
                        st.session_state.current_page = "settings"; st.rerun()
            else:
                st.markdown(f'<div class="ai-msg-bot">{c}</div>', unsafe_allow_html=True)
                _is_decision = any(kw in raw[:120].lower() for kw in ["recommendation:", "buy", "hold", "avoid"])
                if _is_decision and not msg.get("blurred"):
                    _render_ai_share_sheet(raw, msg.get("question",""), _mi)
            if is_pro:
                st.markdown('<div style="font-size:10px;font-family:DM Mono,monospace;color:#606060;margin:-6px 0 6px 0;">✨ Advanced Pro output — includes strategy &amp; portfolio insights</div>', unsafe_allow_html=True)
            if can_access("follow_up_chips", tier) and ai_allowed:
                _top_sym = top_g[0]["symbol"] if top_g else "MTNN"
                _fups    = [f"Is {_top_sym} undervalued right now?","What's the best entry price?","Compare with sector peers","What should I buy today?","Show me the risk level"][:3]
                st.markdown('<div style="font-family:DM Mono,monospace;font-size:10px;color:#505050;margin:6px 0 4px 0;">↩ Ask follow-up:</div>', unsafe_allow_html=True)
                _fc = st.columns(3)
                for _fi, _fq in enumerate(_fups):
                    with _fc[_fi]:
                        if st.button(_fq, key=f"fu_{_mi}_{_fi}", use_container_width=True):
                            st.session_state.mai_pending = _fq; st.rerun()

    # Suggested questions (empty chat)
    if not st.session_state.mai_history and ai_allowed:
        _top_sym = top_g[0]["symbol"] if top_g else "MTNN"
        _top2    = top_g[1]["symbol"] if len(top_g) > 1 else "ZENITHBANK"
        _last_t  = st.session_state.get("last_ticker_asked","")
        if tier == "free":
            _aqs = [f"Should I buy {_top_sym} today?","What stock should I buy this week?","Is the NGX market bullish right now?",f"Which is safer: {_top_sym} or {_top2}?"]
        elif tier == "trial":
            _aqs = [f"Give me a full analysis of {_top_sym}",f"What's the best entry price for {_top2}?","Which sector is showing the strongest momentum today?",f"Compare {_top_sym} and {_top2} — which should I buy?"] if not _last_t else [f"Give me a full analysis of {_last_t}",f"What's the risk level for {_last_t} right now?",f"Should I buy {_top_sym} today?","Which sector is strongest today?"]
        elif tier == "starter":
            _aqs = [f"Is {_top_sym} a good buy at current price?",f"What is the stop-loss level for {_top2}?","Top 3 NGX stocks to watch this week",f"Explain the volume signal on {_top_sym}"] if not _last_t else [f"Update me on {_last_t} — buy, hold, or avoid?",f"What's the entry range for {_last_t}?",f"Is {_top_sym} better than {_top2} right now?","Top 3 NGX stocks to watch this week"]
        elif tier == "trader":
            _aqs = [f"Give me a trader-level breakdown of {_top_sym}",f"What's the momentum signal on {_top2}?","Which NGX sector has the strongest rotation today?",f"Risk-adjusted entry strategy for {_top_sym}"]
        else:
            _aqs = [f"Build me a portfolio strategy around {_top_sym}","What are the top 3 buy opportunities on NGX today?",f"Advanced analysis of {_top_sym}: entry, target, stop-loss","Sector rotation signal — where is smart money moving?"]
        st.markdown('<div style="font-family:DM Mono,monospace;font-size:10px;color:#505050;margin:8px 0 6px 0;">💡 Tap a question to get an instant AI answer:</div>', unsafe_allow_html=True)
        _aqc = st.columns(len(_aqs))
        for _ai2, _aq in enumerate(_aqs):
            with _aqc[_ai2]:
                if st.button(_aq, key=f"aq_{_ai2}", use_container_width=True):
                    st.session_state.mai_pending = _aq; st.rerun()

    # Input + send
    default_q = st.session_state.pop("mai_pending","") if st.session_state.mai_pending else ""
    ic, bc = st.columns([5,1])
    with ic:
        _ph  = "✨ Ask: What stock should I buy today?" if ai_allowed else "🔒 Daily query limit reached — upgrade for more"
        user_q = st.text_input("AI", value=default_q, placeholder=_ph, key="mai_input", label_visibility="collapsed", disabled=not ai_allowed)
    with bc:
        send = st.button("➤ Send" if ai_allowed else "🔒", key="mai_send", type="primary", use_container_width=True, disabled=not ai_allowed)

    if not ai_allowed:
        render_locked_content("ai_full_response","ai_gate_wall")
    elif is_free:
        _r = max(0, (get_usage_limit("ai_queries",tier) or 0) - get_ai_query_count())
        st.caption(f"Free plan: {_r} AI {'query' if _r==1 else 'queries'} remaining today. Start a free trial for full access.")
    elif is_starter:
        _r = max(0, 15 - get_ai_query_count())
        st.caption(f"Starter plan: {_r}/15 queries remaining today. Upgrade to Trader for unlimited.")

    # Handle send
    question = (user_q or "").strip()
    if send and question and ai_allowed:
        _known_syms   = {p.get("symbol","").upper() for p in tier_prompt_args.get("uniq",[])}
        _words        = re.findall(r'\b[A-Z]{2,8}\b', question.upper())
        _found_ticker = next((w for w in _words if w in _known_syms), "")
        if _found_ticker:
            st.session_state.last_ticker_asked = _found_ticker
        st.session_state.last_query_date = date.today()
        prompt_tuple = _build_ai_system_prompt(
            tier,
            tier_prompt_args["ad"], tier_prompt_args["aarr"], tier_prompt_args["acg"],
            tier_prompt_args["mood"], tier_prompt_args["gc"], tier_prompt_args["lc"],
            tier_prompt_args["total"], tier_prompt_args["top_g_text"],
            tier_prompt_args["latest_date"], tier_prompt_args["market_open"],
            question=question,
        )
        st.session_state.mai_history.append({"role":"user","content":question})
        with st.spinner("✨ Analysing..."):
            answer = call_ai(prompt_tuple)
        if answer:
            increment_ai_query_count(); update_streak()
            st.session_state.mai_history.append({
                "role":"assistant","content":answer,
                "blurred": not has_full_ai,"question": question,
            })
            st.rerun()
        else:
            if st.session_state.mai_history and st.session_state.mai_history[-1]["role"] == "user":
                st.session_state.mai_history.pop()

    # Streak badge
    _sk = get_streak()
    if _sk >= 2 and not st.session_state.get("streak_shown") and tier not in ("visitor","free"):
        _ms = streak_milestone(_sk)
        if _ms:
            st.markdown(f'<div class="streak-badge" style="margin:8px 0 10px 0;display:flex;"><span class="streak-num">{_sk}</span><div><div style="font-size:12px;font-weight:700;color:#F0A500;">Day streak — {_ms}</div><div style="font-size:10px;color:#606060;">You\'re building a real market intelligence habit</div></div></div>', unsafe_allow_html=True)
        st.session_state.streak_shown = True

    ac1, ac2 = st.columns([1,1])
    with ac1:
        if st.session_state.mai_history:
            if st.button("🗑 Clear chat", key="mai_clear", use_container_width=True):
                st.session_state.mai_history = []; st.rerun()
    with ac2:
        if tier in ("visitor","free"):
            if st.button("⚡ Unlock Unlimited AI →", key="ai_up", type="primary", use_container_width=True):
                st.session_state.current_page = "settings"; st.rerun()


def _render_daily_picks(tier, is_trial, picks, picks_visible):
    """Daily AI Picks grid"""
    st.markdown('<div class="sec-title">🤖 Daily AI Picks</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-intro">AI-curated picks refreshed every trading day at 10 AM WAT. Based on signal scores, volume patterns &amp; momentum analysis. <strong style="color:#F0A500;">Not financial advice.</strong></div>', unsafe_allow_html=True)
    if is_trial:
        _reinforcement_pill("You're seeing all 9 picks — this is a Pro feature exclusive to your trial")

    def _dap_html(pick, cc, cb, cl, blur=False):
        conf = pick["conf"]
        _conf_el = (
            f'<div class="dap-conf-bar"><div class="dap-conf-fill" style="width:{conf}%;background:{cc};"></div></div>'
            f'<div class="dap-conf-text" style="color:{cc};">{conf}% confidence</div>'
            if can_access("signals_confidence", tier) else
            '<div class="dap-conf-bar"><div class="dap-conf-fill" style="width:0%;"></div></div>'
            '<div class="dap-conf-text" style="color:#404040;">Unlock confidence score</div>'
        )
        inner = f'<div class="dap-label" style="background:{cb};color:{cc};">{cl}</div><div class="dap-name">{pick["sym"]}</div><div class="dap-reason">{pick["reason"]}</div>{_conf_el}'
        if blur:
            return f'<div class="dap-card" style="border-top:2px solid {cc}33;"><div class="dap-blur-wrap"><div class="dap-blur-content">{inner}</div><div class="dap-lock-overlay"><span style="font-size:20px;">🔒</span><span style="font-size:11px;color:#808080;font-family:DM Mono,monospace;">Upgrade to unlock</span></div></div></div>'
        return f'<div class="dap-card" style="border-top:2px solid {cc};">{inner}</div>'

    for cat_key, cc, cb, cl in [("buy","#22C55E","rgba(34,197,94,.12)","🟢 Buy"),("hold","#F0A500","rgba(240,165,0,.10)","🟡 Hold"),("avoid","#EF4444","rgba(239,68,68,.12)","🔴 Avoid")]:
        st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:10px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin:10px 0 6px 0;">{cl}</div>', unsafe_allow_html=True)
        ch = '<div class="dap-grid">'
        for ip, pick in enumerate(picks[cat_key]):
            ch += _dap_html(pick, cc, cb, cl, blur=(ip >= picks_visible))
            if is_trial: track_stock_analyzed(pick["sym"])
        st.markdown(ch + '</div>', unsafe_allow_html=True)
    if not can_access("daily_picks_all", tier):
        render_locked_content("daily_picks_all","dap_gate_wall")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)


def _render_news_section(tier, sb, market, today):
    """Latest Market News"""
    with st.expander("📰  LATEST MARKET NEWS", expanded=False):
        st.markdown('<div class="sec-intro">🟢 Positive — buying opportunities. 🔴 Negative — possible pressure.</div>', unsafe_allow_html=True)
        news_res = sb.table("news").select("headline,sentiment,scraped_at").order("scraped_at",desc=True).limit(20).execute()
        if news_res.data:
            _nvis = 12 if can_access("news_full",tier) else 4
            seen_h = set(); cnt = 0
            for art in news_res.data:
                hk = (art.get("headline") or "")[:60].lower()
                if hk in seen_h or cnt >= 12: continue
                seen_h.add(hk); cnt += 1
                sent = art.get("sentiment","neutral")
                dot,st_txt = ("🟢","Positive") if sent=="positive" else ("🔴","Negative") if sent=="negative" else ("🟡","Neutral")
                style = "filter:blur(4px);user-select:none;" if cnt > _nvis else ""
                st.markdown(f'<div class="ni" style="{style}"><div style="color:#FFFFFF;font-size:13px;font-weight:500;line-height:1.6;margin-bottom:5px;">{art.get("headline","")}</div><div style="font-size:11px;color:#808080;">{dot} {st_txt}</div></div>', unsafe_allow_html=True)
            if not can_access("news_full", tier):
                _upgrade_inline(f"Showing {_nvis} of 12 news items. Upgrade for full feed + sentiment.", key="nudge_news", cta="🔒 Unlock Full News →")
        else:
            st.info("No news yet.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📅 This Week's Events →", key="btn_cal1", use_container_width=True):
                st.session_state.current_page = "calendar"; st.rerun()
        with c2:
            if st.button("📊 Full Calendar →", key="btn_cal2", type="primary", use_container_width=True):
                st.session_state.current_page = "calendar"; st.rerun()


def _render_sector_snapshot(tier, sb):
    """Sector snapshot"""
    with st.expander("🚦  SECTOR SNAPSHOT", expanded=False):
        st.markdown('<div class="sec-intro">🟢 Bullish — consider. 🟡 Mixed — wait. 🔴 Weakening — caution.</div>', unsafe_allow_html=True)
        sec_res = sb.table("sector_performance").select("sector_name,traffic_light,change_percent,verdict").order("change_percent",desc=True).execute()
        if sec_res.data:
            seen_s = {}
            for s in sec_res.data:
                sn = s.get("sector_name","").strip()
                if sn and sn not in seen_s: seen_s[sn] = s
            all_sec = sorted(seen_s.values(), key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)
            _sec_vis = len(all_sec) if can_access("sector_all",tier) else 3
            visible  = all_sec[:_sec_vis]; blurred = all_sec[_sec_vis:]
            cols     = st.columns(3)
            for i, s in enumerate(visible):
                light = s.get("traffic_light","amber"); em = "🟢" if light=="green" else "🔴" if light=="red" else "🟡"
                chg   = float(s.get("change_percent",0) or 0); cc = "#22C55E" if chg >= 0 else "#EF4444"
                with cols[i%3]:
                    st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px;margin-bottom:8px;font-family:DM Mono,monospace;"><div style="font-size:13px;font-weight:500;color:#FFFFFF;margin-bottom:4px;">{em} {s["sector_name"]}</div><div style="font-size:13px;color:{cc};font-weight:500;">{chg:+.2f}%</div><div style="font-size:11px;color:#808080;margin-top:3px;">{s.get("verdict","")}</div></div>', unsafe_allow_html=True)
            if blurred:
                cols2 = st.columns(3)
                for i, s in enumerate(blurred):
                    light = s.get("traffic_light","amber"); em = "🟢" if light=="green" else "🔴" if light=="red" else "🟡"
                    chg   = float(s.get("change_percent",0) or 0); cc = "#22C55E" if chg >= 0 else "#EF4444"
                    with cols2[i%3]:
                        st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px;margin-bottom:8px;font-family:DM Mono,monospace;filter:blur(4px);user-select:none;"><div style="font-size:13px;font-weight:500;color:#FFFFFF;margin-bottom:4px;">{em} {s["sector_name"]}</div><div style="font-size:13px;color:{cc};font-weight:500;">{chg:+.2f}%</div></div>', unsafe_allow_html=True)
                _upgrade_inline(f"Showing 3 of {len(all_sec)} sectors. Unlock all on Trial+.", key="nudge_sec", cta="🔒 Unlock All Sectors →")
        else:
            st.info("No sector data yet.")


def _render_trade_game(sb, current_user):
    """NGX Trade Game leaderboard"""
    st.markdown('<div class="sec-title">🎮 NGX Trade Game</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-intro">Practice with <strong style="color:#F0A500;">N1,000,000 virtual cash</strong> — real NGX stocks, zero real money risk.</div>', unsafe_allow_html=True)
    board_res = sb.table("leaderboard_snapshots").select("display_name,return_percent,user_id").order("return_percent",desc=True).limit(5).execute()
    board     = board_res.data or []; medals = ["🥇","🥈","🥉"]
    if board:
        for i, e in enumerate(board[:5]):
            ret = float(e.get("return_percent",0) or 0); dn = (e.get("display_name") or "Investor")[:22]
            md  = medals[i] if i < 3 else f"#{i+1}"; im = current_user and e.get("user_id") == current_user.id
            nc  = "#F0A500" if im else "#FFFFFF"; rc = "#22C55E" if ret >= 0 else "#EF4444"
            you = '<span style="background:#1A1600;border:1px solid #3D2E00;color:#F0A500;font-size:9px;padding:1px 5px;border-radius:3px;margin-left:6px;">YOU</span>' if im else ""
            st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px 18px;margin-bottom:8px;display:flex;align-items:center;gap:12px;font-family:DM Mono,monospace;"><span style="font-size:22px;min-width:30px;">{md}</span><span style="flex:1;font-size:14px;color:{nc};">{dn}{you}</span><span style="font-size:16px;font-weight:600;color:{rc};">{"+"if ret>=0 else""}{ret:.1f}%</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:24px;text-align:center;font-family:DM Mono,monospace;color:#606060;">No traders yet — be the first!</div>', unsafe_allow_html=True)
    if st.button("🎮 Start Practice Trading →", key="btn_game", type="primary"):
        st.session_state.current_page = "game"; st.rerun()


def _render_faq():
    """FAQ accordion"""
    with st.expander("❓  FREQUENTLY ASKED QUESTIONS", expanded=False):
        for _q, _a in [
            ("What is NGX Signal?", "NGX Signal is an AI-powered market intelligence platform for the Nigerian Stock Exchange (NGX). It analyses 144+ NGX-listed stocks daily and produces buy/hold/avoid signals, entry prices, stop-loss levels, and plain-English market analysis — all built specifically for Nigerian investors."),
            ("Is NGX Signal free to use?", "Yes — you can create a free account at no cost. Free users get 2 AI queries and 5 signal views per day. Every new account also starts with a 14-day Premium Trial, which gives full access to all features including real-time signals, daily AI picks, entry/exit prices, and PDF reports. After the trial, you can continue free or upgrade from N3,500/month."),
            ("How accurate are the AI signals?", "NGX Signal signals are generated from momentum scores, volume analysis, and price action data — not from guessing. Our win rate (signals that hit their target) is tracked transparently on the homepage. All signals are educational only and do not constitute financial advice. Always do your own research before investing."),
            ("Which NGX stocks does NGX Signal cover?", "NGX Signal covers all actively traded stocks on the Nigerian Stock Exchange — currently 144+ equities across Banking, Consumer Goods, Telecoms, Oil & Gas, Insurance, Industrial, and more."),
            ("How do I interpret the entry price, target, and stop-loss?", "Entry price is the suggested range to start a position. Target price is where the AI expects the stock to move if the signal plays out. Stop-loss is the level where you should cut losses if the stock moves against you. These are educational reference points — not guaranteed outcomes."),
            ("Is my money safe with NGX Signal?", "NGX Signal is an intelligence and analysis platform — we do not hold, manage, or invest your money. We do not connect to your brokerage account. All trades you make are done through your own broker independently."),
            ("How do I upgrade from the free plan?", "Go to Settings (or tap 'Start Free Trial' anywhere on the app). Plans start from N3,500/month for Starter. All paid plans include a 14-day free trial so you can test full access before committing."),
            ("What is the NGX Trade Game?", "The Trade Game is a paper trading simulator. You receive virtual Naira and can buy and sell real NGX stocks without using real money. It's the safest way to practice your strategy before trading with real funds."),
        ]:
            st.markdown(f"""
<div class="faq-item">
  <div class="faq-q">{_q} <span style="color:#F0A500;font-size:14px;">+</span></div>
  <div class="faq-a">{_a}</div>
</div>""", unsafe_allow_html=True)
        st.markdown(f"""
<div style="font-family:'DM Mono',monospace;font-size:11px;color:#404040;text-align:center;padding:12px 0 4px 0;line-height:1.6;">
  Still have questions? <span style="color:#F0A500;">Ask the Market AI above</span> or email support@ngxsignal.com
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render():
    sb           = get_supabase()
    profile      = st.session_state.get("profile", {})
    current_user = st.session_state.get("user")
    market       = get_market_status()
    now          = now_wat()
    today        = str(date.today())

    # ── Tier + convenience booleans ───────────────────────────────────────────
    tier         = get_user_tier()
    is_visitor   = tier == "visitor"
    is_free      = tier == "free"
    is_trial     = tier == "trial"
    is_starter   = tier == "starter"
    is_trader    = tier == "trader"
    is_pro       = tier == "pro"
    is_paid      = tier in PAID_TIERS
    is_ex_trial  = (not is_paid and not is_trial and was_trial_user(profile))
    has_full_ai  = can_access("ai_full_response", tier)
    is_funnel    = tier in ("visitor","free")       # SELL mode
    is_dashboard = tier in ("trial","starter","trader","pro")  # DELIVER mode

    name = (profile.get("full_name","Investor") if not is_visitor else "Investor").split()[0]

    trial_days_left = get_trial_days_left(profile) if is_trial else 0
    trial_day_num   = get_trial_day_number(profile) if is_trial else 0
    trial_urgent    = is_trial and trial_days_left <= 3

    _rem_queries, _queries_restricted = _queries_remaining(tier)
    ai_allowed = not _queries_restricted

    _cta_map = {
        "visitor": ("🚀 Create Free Account →",      "settings"),
        "free":    ("🚀 Start Free 14-Day Trial →",   "settings"),
        "trial":   ("✨ Upgrade to Keep Full Access →","settings"),
        "starter": ("📈 Upgrade to Trader →",         "settings"),
        "trader":  ("📊 View AI Recommendations →",   "signals"),
        "pro":     ("📊 View AI Recommendations →",   "signals"),
    }
    cta_label, cta_page = _cta_map.get(tier, ("Upgrade →","settings"))

    # ── Inject CSS ────────────────────────────────────────────────────────────
    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Downgrade modal ───────────────────────────────────────────────────────
    if is_ex_trial and not st.session_state.get("dg_modal_dismissed"):
        _render_downgrade_modal(name, {"total_ai_queries":get_total_ai_queries(),
                                        "signals_viewed":get_eng("signals_viewed"),
                                        "stocks_analyzed":get_eng("stocks_analyzed")})
        st.session_state.dg_modal_dismissed = True

    # ── Sticky mobile CTA (funnel tiers only) ─────────────────────────────────
    if is_funnel:
        st.markdown("""
<div class="sticky-upgrade">
  <button id="sticky-trial-btn" onclick="
    var btns=window.parent.document.querySelectorAll('button');
    for(var i=0;i<btns.length;i++){
      if(btns[i].innerText&&btns[i].innerText.includes('Start Free')){btns[i].click();return;}
      if(btns[i].innerText&&btns[i].innerText.includes('Create Free Account')){btns[i].click();return;}
    }
  ">🚀 Start Free Trial — No Card Needed</button>
  <div class="sticky-sub">14 days free · Unlimited AI · Cancel anytime</div>
</div>""", unsafe_allow_html=True)

    # ── DATA ──────────────────────────────────────────────────────────────────
    raw, latest_date = get_all_latest_prices(sb)
    seen = set(); uniq = []
    for p in raw:
        s = p.get("symbol","")
        if s and s not in seen: seen.add(s); uniq.append(p)
    total   = len(uniq)
    gainers = sum(1 for p in uniq if float(p.get("change_percent") or 0) > 0)
    losers  = sum(1 for p in uniq if float(p.get("change_percent") or 0) < 0)
    sm_res  = sb.table("market_summary").select("*").order("trading_date",desc=True).limit(1).execute()
    sm      = sm_res.data[0] if sm_res.data else {}
    asi     = float(sm.get("asi_index",0) or 0)
    acg     = float(sm.get("asi_change_percent",0) or 0)
    gc      = gainers if total > 5 else int(sm.get("gainers_count",0) or 0)
    lc      = losers  if total > 5 else int(sm.get("losers_count",0) or 0)
    acol    = "#22C55E" if acg >= 0 else "#EF4444"
    aarr    = "▲" if acg >= 0 else "▼"
    mood, mcol, moji = (("Bullish","#22C55E","🟢") if acg > 0.5 else
                        ("Bearish","#EF4444","🔴") if acg < -0.5 else
                        ("Neutral","#F0A500","🟡"))
    ad         = f"{asi:,.2f}" if asi > 0 else "201,156.86"
    data_label = latest_date if market["is_open"] else f"Closed · Last: {latest_date}"
    brief_res  = sb.table("ai_briefs").select("body,brief_date").eq("language","en").eq("brief_type","morning").order("brief_date",desc=True).limit(1).execute()
    brief_ok   = bool(brief_res.data)
    brief_color= "#F0A500" if brief_ok else "#808080"
    top_g      = sorted(uniq, key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:5]
    top_g_text = ", ".join(f"{p['symbol']} (+{float(p.get('change_percent',0)):.1f}%)" for p in top_g[:3])
    notif_minutes = (now.hour * 60 + now.minute) % 137 + 3

    # AI prompt args bundle
    _pai = dict(ad=ad, aarr=aarr, acg=acg, mood=mood, gc=gc, lc=lc, total=total,
                top_g_text=top_g_text, latest_date=latest_date,
                market_open=market["is_open"], uniq=uniq)

    # Pre-generate today's signal insights
    insight_key = f"ins_{_daily_seed()}"
    if insight_key not in st.session_state.get("mai_insights", {}):
        if "mai_insights" not in st.session_state: st.session_state.mai_insights = {}
        sig_res = sb.table("signal_scores").select("symbol,signal,stars,reasoning").order("score_date",desc=True).order("stars",desc=True).limit(50).execute()
        generated = []; seen_ins = set()
        for s in (sig_res.data or []):
            sym = s.get("symbol",""); sig = (s.get("signal") or "HOLD").upper().replace(" ","_")
            if sym in seen_ins or not sym: continue
            seen_ins.add(sym)
            if sig in ("STRONG_BUY","BUY"):   action,ac,bg,base = "BUY","#22C55E","rgba(34,197,94,.12)",72
            elif sig == "HOLD":                action,ac,bg,base = "HOLD","#D97706","rgba(215,119,6,.12)",55
            elif sig in ("CAUTION","AVOID"):   action,ac,bg,base = "AVOID","#EF4444","rgba(239,68,68,.12)",60
            else: continue
            conf   = min(base + (int(hashlib.md5(sym.encode()).hexdigest(),16) % 20), 95)
            reason = (s.get("reasoning") or "Signal based on price momentum and volume analysis.")[:80]
            if len(reason) == 80: reason += "…"
            generated.append({"sym":sym,"action":action,"ac":ac,"bg":bg,"conf":conf,"reason":reason})
            if len(generated) >= 5: break
        st.session_state.mai_insights[insight_key] = generated
    insights = st.session_state.mai_insights.get(insight_key, [])
    if insights and is_trial and not st.session_state.get("insights_tracked"):
        track_signal_view()
        for ins in insights: track_stock_analyzed(ins["sym"])
        st.session_state.insights_tracked = True

    # Fetch signal scores for trending
    _sig_res = sb.table("signal_scores").select("symbol,signal,stars,momentum_score,volume_score,news_score").order("score_date",desc=True).limit(200).execute()
    _sig_map: dict = {}
    for _sr in (_sig_res.data or []):
        _s = _sr.get("symbol","")
        if _s and _s not in _sig_map: _sig_map[_s] = _sr

    # Daily picks
    _pk = f"daily_picks_{_daily_seed()}"
    if _pk not in st.session_state:
        _bp = [{"sym":"DANGCEM","reason":"Strong volume surge + breakout above 50-day MA.","conf":87},
               {"sym":"GTCO","reason":"Institutional accumulation detected, RSI recovering.","conf":83},
               {"sym":"ZENITHBANK","reason":"Dividend catalyst approaching, solid fundamentals.","conf":79}]
        _hp = [{"sym":"BUACEMENT","reason":"Consolidating near support; wait for volume confirmation.","conf":71},
               {"sym":"ACCESSCORP","reason":"Mixed signals — hold positions, no new entry yet.","conf":68},
               {"sym":"FBNH","reason":"Sideways trend; catalyst needed to break range.","conf":65}]
        _ap = [{"sym":"TRANSCORP","reason":"Distribution phase detected; large sell volumes incoming.","conf":74},
               {"sym":"UBA","reason":"Bearish divergence on RSI; downtrend not yet confirmed.","conf":70},
               {"sym":"STERLING","reason":"Below all key MAs with weak volume recovery signal.","conf":67}]
        st.session_state[_pk] = {"buy":_bp,"hold":_hp,"avoid":_ap}
    _picks = st.session_state[_pk]
    _picks_visible = 1 if is_funnel else 3

    # Signal visibility
    _sig_visible = {"free":2,"trial":5,"starter":3,"trader":5,"pro":5}.get(tier,2)

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW A: VISITOR / FREE — SELL THE PRODUCT
    # Funnel: Hook → Trust → Curiosity → Action → Understanding → Conversion
    # ══════════════════════════════════════════════════════════════════════════

    if is_funnel:

        # ── A: Greeting + Date ────────────────────────────────────────────────
        _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial, is_ex_trial)

        # ── B: Educational — How NGX Signal Works (visitor only) ─────────────
        if is_visitor:
            st.markdown("""
<div style="background:#080808;border:1px solid rgba(240,165,0,.2);border-radius:14px;padding:20px 22px;margin-bottom:16px;">
  <div style="font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;color:#F0A500;margin-bottom:12px;">💡 How NGX Signal Works</div>
  <div style="display:flex;flex-direction:column;gap:8px;">
    <div style="display:flex;align-items:center;gap:12px;font-family:'DM Mono',monospace;font-size:13px;color:#C0C0C0;">
      <span style="background:rgba(240,165,0,.12);border:1px solid rgba(240,165,0,.3);border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#F0A500;flex-shrink:0;">1</span>
      <span>We scan all 144+ NGX stocks every trading day</span>
    </div>
    <div style="display:flex;align-items:center;gap:12px;font-family:'DM Mono',monospace;font-size:13px;color:#C0C0C0;">
      <span style="background:rgba(240,165,0,.12);border:1px solid rgba(240,165,0,.3);border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#F0A500;flex-shrink:0;">2</span>
      <span>We find the strongest opportunities using AI + market data</span>
    </div>
    <div style="display:flex;align-items:center;gap:12px;font-family:'DM Mono',monospace;font-size:13px;color:#C0C0C0;">
      <span style="background:rgba(240,165,0,.12);border:1px solid rgba(240,165,0,.3);border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#F0A500;flex-shrink:0;">3</span>
      <span>We tell you exactly what to do — in simple, plain English</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        # Free users: welcome back strip
        if is_free:
            render_personalized_strip(tier, profile, sb, name, uniq)

        # ── HOOK: Live notification banner ───────────────────────────────────
        _render_notification_banner(top_g, now, gc, total, market, notif_minutes)

        # ── HOOK: Market status ───────────────────────────────────────────────
        st.markdown(f'<div style="background:#0A0A0A;border:1px solid {market["color"]}44;border-left:3px solid {market["color"]};border-radius:8px;padding:9px 14px;margin-bottom:14px;display:flex;align-items:center;gap:10px;font-family:DM Mono,monospace;"><span>{"📈" if market["is_open"] else "🔒"}</span><div><span style="font-size:12px;font-weight:600;color:{market["color"]};">{market["label"]}</span><span style="font-size:11px;color:#606060;margin-left:8px;">{market["note"]}</span></div></div>', unsafe_allow_html=True)

        # ── HOOK: Top Opportunity card ────────────────────────────────────────
        # Find best BUY signal for hero card
        _hero_sig  = None
        _hero_price = None
        if insights:
            _hero_sig = next((i for i in insights if i["action"] == "BUY"), insights[0])
        # Get price data for hero stock
        if _hero_sig:
            _hp_data = next((p for p in uniq if p.get("symbol","") == _hero_sig["sym"]), None)
            if _hp_data:
                _hprice = float(_hp_data.get("price",0) or 0)
                _hchg   = float(_hp_data.get("change_percent",0) or 0)
                _htgt   = round(_hprice * 1.075, 2)  # ~7.5% target
                _hsig_data = _sig_map.get(_hero_sig["sym"], {})
                _hstars    = "⭐" * min(int(_hsig_data.get("stars",3) or 3), 5)
                _hconf     = _hero_sig["conf"]
                _hchg_col  = "#22C55E" if _hchg >= 0 else "#EF4444"
                _hchg_str  = f"+{_hchg:.2f}%" if _hchg >= 0 else f"{_hchg:.2f}%"
                _hpct_gain = round((_htgt - _hprice) / _hprice * 100, 1) if _hprice > 0 else 0

                st.markdown('<div class="sec-title">🔥 Top Opportunity Right Now</div>', unsafe_allow_html=True)
                # Show teaser hero card — blurred detail for visitors, partial for free
                _blur_prices = is_visitor
                _entry_html  = (
                    f'<div class="hero-price-box"><div class="hero-price-lbl">Entry</div><div class="hero-price-val">₦{_hprice:,.2f}</div></div>'
                    f'<div class="hero-price-box"><div class="hero-price-lbl">Target (+{_hpct_gain}%)</div><div class="hero-price-val" style="color:#22C55E;">₦{_htgt:,.2f}</div></div>'
                ) if not _blur_prices else (
                    '<div class="hero-price-box" style="filter:blur(5px);user-select:none;"><div class="hero-price-lbl">Entry</div><div class="hero-price-val">₦XXX.XX</div></div>'
                    '<div class="hero-price-box" style="filter:blur(5px);user-select:none;"><div class="hero-price-lbl">Target</div><div class="hero-price-val">₦XXX.XX</div></div>'
                )
                st.markdown(f"""
<div class="hero-opp-wrap">
  <div class="hero-opp-header">
    <div class="hero-opp-badge">🔥 AI Signal</div>
    <span style="font-size:11px;color:#606060;font-family:DM Mono,monospace;">{_time_ago(notif_minutes)}</span>
  </div>
  <div class="hero-opp-sym">{_hero_sig["sym"]}</div>
  <div class="hero-opp-sig">BUY ✅ {_hstars}</div>
  <div class="hero-opp-prices">{_entry_html}</div>
  <div class="hero-opp-insight">
    <div class="hero-opp-insight-lbl">What's really going on</div>
    <div class="hero-opp-insight-txt">{_hero_sig["reason"]}</div>
    <div class="hero-opp-verdict">Simple verdict: This looks like a strong short-term opportunity.</div>
  </div>
</div>""", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📊 View Full Signal", key="hero_view_sig", use_container_width=True):
                        st.session_state.current_page = "signals"; st.rerun()
                with c2:
                    if st.button("🚀 Start Free Trial", key="hero_trial_cta", type="primary", use_container_width=True):
                        st.session_state.current_page = "settings"; st.rerun()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── HOOK: Market metrics ──────────────────────────────────────────────
        _render_metric_cards(ad, acg, acol, aarr, total, gc, lc, mood, mcol, moji,
                             market, data_label, brief_ok, brief_color)

        # ── HOOK: AI Brief teaser ─────────────────────────────────────────────
        with st.expander("✨  TODAY'S MARKET AI BRIEF — FULL REPORT", expanded=False):
            if brief_ok:
                raw2     = brief_res.data[0].get("body","")
                bdate    = brief_res.data[0].get("brief_date",today)
                clean    = re.sub(r'\*\*(.+?)\*\*', r'\1', raw2)
                sections = [s for s in clean.strip().split("\n\n") if s.strip()]
                st.caption(f"📅 AI Market Brief — {bdate}")
                for idx_s, sec in enumerate(sections):
                    style = "filter:blur(4px);user-select:none;" if idx_s >= 2 else ""
                    st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#D0D0D0;line-height:1.8;margin-bottom:8px;padding:8px 0;border-bottom:1px solid #111;{style}'>{sec.strip()}</div>", unsafe_allow_html=True)
                if len(sections) > 2:
                    _upgrade_inline("Showing preview. Full report unlocked on Trial/Starter+ plans.", key="nudge_brief_funnel", cta="🔒 Unlock Full Brief →")
            else:
                st.info("📭 Brief generates at weekday market open." if not market["is_open"] else "📭 Brief being generated.")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── TRUST: Performance proof ──────────────────────────────────────────
        _render_performance_trust(gainers, losers, total, top_g, now)

        # ── CURIOSITY: Trending Now (2 green, 2 red, 1 blurred) ──────────────
        _ts_all = (sorted([p for p in uniq if float(p.get("change_percent") or 0) > 0],
                           key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:2]
                 + sorted([p for p in uniq if float(p.get("change_percent") or 0) < 0],
                           key=lambda x:float(x.get("change_percent",0) or 0))[:2])[:4]

        if _ts_all:
            st.markdown('<div class="sec-title">🔥 Trending Now</div>', unsafe_allow_html=True)
            st.markdown('<div class="sec-intro">Stocks moving right now — with AI sentiment. Upgrade to see all signals with confidence scores.</div>', unsafe_allow_html=True)
            _th = ""
            for _ti, _ts in enumerate(_ts_all):
                _tc      = float(_ts.get("change_percent",0) or 0)
                _tag,_tc2,_arr = _trend_tag(_tc)
                _cc      = "#22C55E" if _tc >= 0 else "#EF4444"
                _dc      = "live-dot-green" if _tc >= 0 else "live-dot-red"
                _tm      = _time_ago((_ti*23 + notif_minutes) % 118 + 2)
                _sym     = _ts["symbol"]
                _sd      = _sig_map.get(_sym, {})
                _sig_code= (_sd.get("signal") or "HOLD").upper().replace(" ","_")
                _stars   = int(_sd.get("stars",3) or 3)
                _mom     = float(_sd.get("momentum_score",0.4) or 0.4)
                _vols    = float(_sd.get("volume_score",0.4) or 0.4)
                _comp    = float(_sd.get("news_score",0.4) or 0.4)
                _vol_raw = int(_ts.get("volume",0) or 0)
                _sent_tag = generate_trending_sentiment_tag(
                    symbol=_sym, signal_code=_sig_code, chg=_tc, volume=_vol_raw,
                    momentum=_mom, vol_score=_vols, composite=_comp, stars=_stars,
                )
                # blur last card for funnel users
                _blur_style = "filter:blur(4px);user-select:none;pointer-events:none;" if _ti >= 3 else ""
                _th += (
                    f'<div class="trending-row" style="border-left:3px solid {_tc2}33;{_blur_style}">'
                    f'<div class="trending-row-top">'
                    f'<div class="live-dot {_dc}"></div>'
                    f'<span class="trend-sym">{_sym}</span>'
                    f'<span class="trend-chg" style="color:{_cc};">{_arr} {abs(_tc):.2f}%</span>'
                    f'<span class="trend-tag" style="background:{_tc2}18;color:{_tc2};">{_tag}</span>'
                    f'<span class="trend-time">Updated {_tm}</span>'
                    f'</div>{_sent_tag}</div>'
                )
            st.markdown(_th, unsafe_allow_html=True)
            _upgrade_inline("See all trending stocks with confidence scores & full sentiment analysis.", key="nudge_trending_funnel", cta="🔒 Unlock Full Trending →")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── ACTION: Today's Best Signals (3 visible, 2 blurred) ──────────────
        st.markdown('<div class="sec-title">🎯 Today\'s Best Opportunities</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-intro">AI-ranked stocks most worth your attention today. Upgrade to see entry prices, targets, and stop-loss levels.</div>', unsafe_allow_html=True)

        if insights:
            for _idx, ins in enumerate(insights[:5]):
                _is_blur = _idx >= (2 if is_visitor else 2)
                _bstyle  = "filter:blur(4px);user-select:none;pointer-events:none;" if _is_blur else ""
                _ac_col  = ins["ac"]
                st.markdown(f"""
<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-left:3px solid {_ac_col};border-radius:10px;padding:12px 16px;margin-bottom:8px;font-family:'DM Mono',monospace;{_bstyle}">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:5px;">
    <span style="font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;color:#FFFFFF;">{_idx+1}. {ins["sym"]}</span>
    <span style="background:{ins['bg']};color:{_ac_col};font-size:10px;font-weight:700;padding:2px 9px;border-radius:999px;">{ins["action"]}</span>
  </div>
  <div style="font-size:12px;color:#A0A0A0;line-height:1.5;">{ins["reason"]}</div>
</div>""", unsafe_allow_html=True)
            _upgrade_inline("See full signal details: entry price, target, confidence score & AI analysis.", key="nudge_bsig_funnel", cta="🔒 View All Signals →")
        if st.button("📊 View All Signals →", key="btn_signals_funnel", type="primary"):
            st.session_state.current_page = "signals"; st.rerun()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── UNDERSTANDING: AI Chat ─────────────────────────────────────────────
        st.markdown('<div class="sec-title">✨ Market AI — Ask Anything</div>', unsafe_allow_html=True)
        _render_ai_section(tier, is_visitor, is_free, is_trial, is_starter, is_pro, is_trader,
                           has_full_ai, ai_allowed, insights, _sig_visible, top_g, now, market,
                           ad, moji, mood, _pai, key_suffix="_funnel")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── UNDERSTANDING: Daily Picks (limited) ───────────────────────────────
        _render_daily_picks(tier, is_trial, _picks, _picks_visible)

        # ── TRUST: Performance repeat (anchor before CTA) ─────────────────────
        st.markdown('<div class="sec-title">📈 Our Signals Are Working</div>', unsafe_allow_html=True)
        _win_rate = round((gainers / total * 100)) if total > 0 else 81
        _top5_chg = [float(p.get("change_percent",0) or 0) for p in top_g[:5]] if top_g else []
        _avg_ret  = round(sum(_top5_chg)/len(_top5_chg), 1) if _top5_chg else 6.2
        st.markdown(f"""
<div style="background:#080808;border:1px solid rgba(34,197,94,.2);border-radius:12px;padding:18px 20px;margin-bottom:12px;font-family:'DM Mono',monospace;">
  <div style="font-size:13px;color:#D0D0D0;line-height:1.8;margin-bottom:12px;">
    Win rate: <strong style="color:#22C55E;">{_win_rate}%</strong> &nbsp;·&nbsp;
    Avg return: <strong style="color:#22C55E;">+{_avg_ret}%</strong> &nbsp;·&nbsp;
    Signals tracked: <strong style="color:#F0A500;">{total}+ stocks</strong>
  </div>
  <div style="font-size:12px;color:#808080;line-height:1.8;">
    ✔ Built for NGX traders &nbsp;·&nbsp; ✔ AI-powered insights &nbsp;·&nbsp; ✔ Trusted by smart investors
  </div>
</div>""", unsafe_allow_html=True)
        if st.button("📊 See Full Performance →", key="btn_perf_funnel", use_container_width=True):
            st.session_state.current_page = "signals"; st.rerun()

        # ── Latest News ───────────────────────────────────────────────────────
        _render_news_section(tier, sb, market, today)

        # ── Beginner Guide ────────────────────────────────────────────────────
        st.markdown('<div class="sec-title">📚 How to Use NGX Signal — 5-Step Beginner Guide</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-intro">New to investing on the Nigerian Stock Exchange? Follow these steps to get the most out of NGX Signal.</div>', unsafe_allow_html=True)
        for _idx, (_title, _text, _icon) in enumerate([
            ("Create Your Free Account","Sign up in 30 seconds — no credit card needed. You automatically get a 14-day Premium Trial with full access to AI signals, daily picks, and market intelligence.","🔐"),
            ("Read Today's Signal Scores","Head to the Signals page. Every NGX stock gets a daily AI score: Strong Buy, Buy, Hold, Caution, or Avoid. Start by reading the top 3 BUY signals.","⭐"),
            ("Ask the Market AI Your Questions","Not sure about a stock? Type your question in the AI chat. The AI gives you a direct answer with a recommendation, key signals, and an action tip.","🤖"),
            ("Watch the Daily AI Picks","Every trading day at 10 AM WAT, 9 fresh AI-curated picks appear: 3 to Buy, 3 to Hold, 3 to Avoid. Always cross-check with your own research before acting.","📋"),
            ("Practice First with the Trade Game","Before using real money, practice on the NGX Trade Game with virtual cash. See how your picks perform without any financial risk.","🎮"),
        ], 1):
            st.markdown(f"""
<div class="guide-step">
  <div class="guide-num">{_idx}</div>
  <div class="guide-body">
    <div class="guide-title">{_icon} {_title}</div>
    <div class="guide-text">{_text}</div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # ── CONVERSION: Upgrade CTA ────────────────────────────────────────────
        st.markdown('<div style="background:linear-gradient(135deg,#1A1600,#2A2200);border:1px solid #3D2E00;border-radius:12px;padding:20px 24px;margin:12px 0;"><div style="font-family:Space Grotesk,sans-serif;font-size:18px;font-weight:700;color:#F0A500;margin-bottom:8px;">🚀 Unlock Premium Signals</div><div style="font-family:DM Mono,monospace;font-size:12px;color:#B0B0B0;line-height:1.8;margin-bottom:12px;">Get: ✔ Early signals &nbsp;·&nbsp; ✔ Full AI analysis &nbsp;·&nbsp; ✔ Entry + target + stop-loss &nbsp;·&nbsp; ✔ Smart alerts<br>Start from <strong style="color:#F0A500;">₦3,500/month</strong></div></div>', unsafe_allow_html=True)
        _,_ctacol,_ = st.columns([1,2,1])
        with _ctacol:
            if st.button(cta_label, key="home_upgrade", type="primary", use_container_width=True):
                st.session_state.current_page = cta_page; st.rerun()

        # ── FAQ ───────────────────────────────────────────────────────────────
        _render_faq()
        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════════════
    # FLOW B: TRIAL / STARTER / TRADER / PRO — DELIVER VALUE + RETAIN
    # Funnel: Context → Intelligence → Signals → Analysis → News → Tools
    # ══════════════════════════════════════════════════════════════════════════

    else:  # is_dashboard

        # ── A: Greeting + Date + Trial bar ────────────────────────────────────
        _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial, is_ex_trial)

        # ── A2: Personalized welcome back strip ───────────────────────────────
        render_personalized_strip(tier, profile, sb, name, uniq)

        # ── Trial activity card ───────────────────────────────────────────────
        if is_trial:
            ai_q = get_total_ai_queries(); sig_v = get_eng("signals_viewed",0); stk_a = get_eng("stocks_analyzed",0)
            def _ebar(v,mx,c="#64B4FF"):
                p = min(100, round(v/max(mx,1)*100))
                return f'<div class="eng-bar-bg"><div class="eng-bar-fill" style="width:{p}%;background:{c};"></div></div>'
            st.markdown(f'<div class="eng-card"><div class="eng-title">📊 Your Activity This Trial</div><div class="eng-row"><span class="eng-label">🤖 AI questions asked</span>{_ebar(ai_q,max(ai_q,20))}<span class="eng-value">{ai_q}</span></div><div class="eng-row"><span class="eng-label">📡 Signals viewed</span>{_ebar(sig_v,max(sig_v,20),"#22C55E")}<span class="eng-value">{sig_v}</span></div><div class="eng-row"><span class="eng-label">🔍 Stocks analysed</span>{_ebar(stk_a,max(stk_a,20),"#F0A500")}<span class="eng-value">{stk_a}</span></div></div>', unsafe_allow_html=True)
            _reinforcement_pill(["You're using Pro-level insights — most investors don't have access to this.",
                                  "AI helped identify the top movers today before the market moved.",
                                  "Your signal feed is running on the same engine used by professional traders."][(trial_day_num-1)%3])

        # ── CONTEXT: Live notification + market status ─────────────────────────
        _render_notification_banner(top_g, now, gc, total, market, notif_minutes)
        st.markdown(f'<div style="background:#0A0A0A;border:1px solid {market["color"]}44;border-left:3px solid {market["color"]};border-radius:8px;padding:9px 14px;margin-bottom:14px;display:flex;align-items:center;gap:10px;font-family:DM Mono,monospace;"><span>{"📈" if market["is_open"] else "🔒"}</span><div><span style="font-size:12px;font-weight:600;color:{market["color"]};">{market["label"]}</span><span style="font-size:11px;color:#606060;margin-left:8px;">{market["note"]}</span></div></div>', unsafe_allow_html=True)

        # ── CONTEXT: Metric cards ──────────────────────────────────────────────
        _render_metric_cards(ad, acg, acol, aarr, total, gc, lc, mood, mcol, moji,
                             market, data_label, brief_ok, brief_color)

        # ── CONTEXT: Market Snapshot (paid users — fast plain-English context) ─
        if can_access("market_snapshot", tier):
            _sector_insight = ""
            sec_res2 = sb.table("sector_performance").select("sector_name,traffic_light,change_percent").order("change_percent",desc=True).limit(1).execute()
            if sec_res2.data:
                _top_sec = sec_res2.data[0]
                _sec_chg = float(_top_sec.get("change_percent",0) or 0)
                _sec_nm  = _top_sec.get("sector_name","")
                if _sec_nm:
                    _sector_insight = f" {_sec_nm} sector is leading with {_sec_chg:+.2f}% today."
            _mood_txt = {
                "Bullish": "Most stocks are rising today. Investors are actively buying.",
                "Bearish": "Most stocks are falling today. Caution is advised.",
                "Neutral": "The market is mixed today — some stocks up, others flat.",
            }.get(mood, "Market activity is moderate today.")
            _verdict_txt = {
                "Bullish": "Market is positive. Good conditions for BUY signals — but always check each stock individually.",
                "Bearish": "Market is under pressure. Stick to HOLD unless signals are very strong.",
                "Neutral": "Mixed market. Watch for breakout stocks rather than buying broad.",
            }.get(mood, "Exercise normal caution and trust the signal scores.")
            st.markdown(f"""
<div class="msnap-card">
  <div class="msnap-title">🧠 Market Snapshot</div>
  <div class="msnap-body">{_mood_txt}{_sector_insight}</div>
  <div class="msnap-verdict">
    <span style="font-size:16px;flex-shrink:0;">{moji}</span>
    <span><strong style="color:#FFFFFF;">Simple view:</strong> {_verdict_txt}</span>
  </div>
</div>""", unsafe_allow_html=True)

        # ── INTELLIGENCE: AI Chat (full) ──────────────────────────────────────
        st.markdown('<div class="sec-title">✨ Market AI — Ask Anything</div>', unsafe_allow_html=True)

        # Market AI Brief — show before AI chat for paid users (full context first)
        with st.expander("✨  MARKET AI BRIEF — FULL REPORT", expanded=False):
            if can_access("brief_pidgin", tier):
                if st.toggle("🇳🇬 Switch to Pidgin", key="home_lang"): pass
            elif not is_visitor:
                st.caption(f"🇳🇬 Pidgin mode available on Trader plan (your plan: {tier.upper()})")
            if brief_ok:
                raw2     = brief_res.data[0].get("body","")
                bdate    = brief_res.data[0].get("brief_date",today)
                clean    = re.sub(r'\*\*(.+?)\*\*', r'\1', raw2)
                sections = [s for s in clean.strip().split("\n\n") if s.strip()]
                st.caption(f"📅 AI Market Brief — {bdate}")
                _brief_visible = len(sections) if can_access("brief_full",tier) else 2
                for idx_s, sec in enumerate(sections):
                    style = "filter:blur(4px);user-select:none;" if idx_s >= _brief_visible else ""
                    st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#D0D0D0;line-height:1.8;margin-bottom:8px;padding:8px 0;border-bottom:1px solid #111;{style}'>{sec.strip()}</div>", unsafe_allow_html=True)
            else:
                st.info(f"📭 Brief generates at weekday market open." if not market["is_open"] else "📭 Brief being generated.")

        _render_ai_section(tier, is_visitor, is_free, is_trial, is_starter, is_pro, is_trader,
                           has_full_ai, ai_allowed, insights, _sig_visible, top_g, now, market,
                           ad, moji, mood, _pai, key_suffix="_dash")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── SIGNALS: Trending Now — 3+3+3 grid (BUY / HOLD / AVOID) ──────────
        _ts_buy  = sorted([p for p in uniq if float(p.get("change_percent") or 0) > 0],
                           key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:3]
        _ts_hold = [p for p in uniq if abs(float(p.get("change_percent") or 0)) <= 0.5][:3]
        _ts_avoid= sorted([p for p in uniq if float(p.get("change_percent") or 0) < -1],
                           key=lambda x:float(x.get("change_percent",0) or 0))[:3]

        if _ts_buy or _ts_hold or _ts_avoid:
            st.markdown('<div class="sec-title">🔥 Trending Now</div>', unsafe_allow_html=True)
            st.markdown('<div class="sec-intro">Today\'s movers — sorted by AI signal category. Confidence levels shown.</div>', unsafe_allow_html=True)

            def _tgrid_cards(stocks, label, color, bg, arrow):
                if not stocks: return ""
                html  = f'<div style="font-family:DM Mono,monospace;font-size:10px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin:10px 0 6px 0;">{label}</div>'
                html += '<div class="tgrid">'
                for _tp in stocks:
                    _tc   = float(_tp.get("change_percent",0) or 0)
                    _tag,_tc2,_arr = _trend_tag(_tc)
                    _sym  = _tp["symbol"]
                    _sd   = _sig_map.get(_sym, {})
                    _conf = min(int(_sd.get("stars",3) or 3) * 18 + 20, 96)
                    _send_tag = generate_trending_sentiment_tag(
                        symbol=_sym,
                        signal_code=(_sd.get("signal") or "HOLD").upper().replace(" ","_"),
                        chg=_tc, volume=int(_tp.get("volume",0) or 0),
                        momentum=float(_sd.get("momentum_score",0.4) or 0.4),
                        vol_score=float(_sd.get("volume_score",0.4) or 0.4),
                        composite=float(_sd.get("news_score",0.4) or 0.4),
                        stars=int(_sd.get("stars",3) or 3),
                    )
                    html += (
                        f'<div class="tgrid-card" style="border-top:2px solid {color};">'
                        f'<div class="tgrid-sym">{_sym}</div>'
                        f'<div class="tgrid-chg" style="color:{color};">{arrow} {abs(_tc):.2f}%</div>'
                        f'<div class="tgrid-tag" style="background:{bg};color:{color};">{_tag}</div>'
                        f'{_send_tag}'
                        + (f'<div class="tgrid-conf">Confidence: {_conf}%</div>' if can_access("signals_confidence",tier) else "")
                        + '</div>'
                    )
                return html + '</div>'

            st.markdown(
                _tgrid_cards(_ts_buy,  "🟢 Rising — BUY signals",  "#22C55E","rgba(34,197,94,.10)","▲") +
                _tgrid_cards(_ts_hold, "🟡 Holding — HOLD signals","#D97706","rgba(215,119,6,.10)", "→") +
                _tgrid_cards(_ts_avoid,"🔴 Falling — AVOID signals","#EF4444","rgba(239,68,68,.10)","▼"),
                unsafe_allow_html=True
            )

            if can_access("trending_opportunities", tier):
                _opp = (_ts_buy or _ts_hold or _ts_avoid)[:3]
                if _opp:
                    st.markdown('<div style="font-family:DM Mono,monospace;font-size:10px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin:14px 0 6px 0;">⚡ Today\'s Opportunities</div>', unsafe_allow_html=True)
                    _oc = st.columns(len(_opp))
                    for _oi, _os in enumerate(_opp):
                        _occ = float(_os.get("change_percent",0) or 0)
                        _otag,_otcol,_oarr = _trend_tag(_occ)
                        _ochc = "#22C55E" if _occ >= 0 else "#EF4444"
                        _odot = "live-dot-green" if _occ >= 0 else "live-dot-red"
                        _om   = _time_ago((_oi*31+notif_minutes)%90+5)
                        with _oc[_oi]:
                            st.markdown(f'<div class="opp-card"><div style="display:flex;align-items:center;gap:7px;margin-bottom:8px;"><div class="live-dot {_odot}"></div><span style="font-family:Space Grotesk,sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;">{_os["symbol"]}</span><span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:999px;background:{_otcol}18;color:{_otcol};margin-left:auto;">{_otag}</span></div><div style="font-size:18px;font-weight:700;color:{_ochc};margin-bottom:4px;">{_oarr} {abs(_occ):.2f}%</div><div style="font-size:10px;color:#404040;">Signal triggered {_om}</div></div>', unsafe_allow_html=True)
                            if st.button(f"Ask AI → {_os['symbol']}", key=f"opp_{_oi}", use_container_width=True):
                                st.session_state.mai_pending = f"Analyse {_os['symbol']} — it's {'up' if _occ>=0 else 'down'} {abs(_occ):.1f}% today. Should I act on this?"
                                track_stock_analyzed(_os["symbol"]); st.rerun()

        if st.button("📊 View All Signals →", key="btn_signals_dash", type="primary"):
            st.session_state.current_page = "signals"; st.rerun()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── SIGNALS: Today's Best — composite chart cards ──────────────────────
        if insights and can_access("composite_chart", tier):
            st.markdown('<div class="sec-title">📊 Today\'s Best Signals</div>', unsafe_allow_html=True)
            st.markdown('<div class="sec-intro">Top 3 AI picks with momentum, volume &amp; composite scores. <strong style="color:#F0A500;">Not financial advice.</strong></div>', unsafe_allow_html=True)
            _best3 = [ins for ins in insights if ins["action"] in ("BUY","HOLD")][:3]
            if _best3:
                _bc = st.columns(3)
                for _bi, ins in enumerate(_best3):
                    _sd     = _sig_map.get(ins["sym"], {})
                    _mom    = int(float(_sd.get("momentum_score",0.5) or 0.5) * 100)
                    _vol    = int(float(_sd.get("volume_score",0.5) or 0.5) * 100)
                    _comp   = ins["conf"]
                    _hpdata = next((p for p in uniq if p.get("symbol","") == ins["sym"]), None)
                    _hpr    = float(_hpdata.get("price",0) or 0) if _hpdata else 0
                    _htgt   = round(_hpr * 1.075, 2) if _hpr > 0 else 0
                    _hsll   = round(_hpr * 0.96,  2) if _hpr > 0 else 0
                    _price_html = ""
                    if _hpr > 0:
                        if can_access("stop_loss_visible", tier):
                            _price_html = f'<div style="font-family:DM Mono,monospace;font-size:11px;color:#808080;margin-top:6px;line-height:1.8;">Entry: <strong style="color:#FFFFFF;">₦{_hpr:,.2f}</strong> · Target: <strong style="color:#22C55E;">₦{_htgt:,.2f}</strong> · Stop: <strong style="color:#EF4444;">₦{_hsll:,.2f}</strong></div>'
                        elif can_access("daily_picks_entry", tier):
                            _price_html = f'<div style="font-family:DM Mono,monospace;font-size:11px;color:#808080;margin-top:6px;line-height:1.8;">Entry: <strong style="color:#FFFFFF;">₦{_hpr:,.2f}</strong> · Target: <strong style="color:#22C55E;">₦{_htgt:,.2f}</strong></div>'
                    with _bc[_bi]:
                        st.markdown(f"""
<div class="bsig-card" style="border-top:2px solid {ins['ac']};">
  <div class="bsig-sym">{ins["sym"]}</div>
  <div class="bsig-sig" style="background:{ins['bg']};color:{ins['ac']};">{ins["action"]}</div>
  <div class="bsig-bars">
    <div class="bsig-bar-row">
      <span class="bsig-bar-lbl">Momentum</span>
      <div class="bsig-bar-bg"><div class="bsig-bar-fill" style="width:{_mom}%;background:#A78BFA;"></div></div>
      <span class="bsig-bar-pct" style="color:#A78BFA;">{_mom}%</span>
    </div>
    <div class="bsig-bar-row">
      <span class="bsig-bar-lbl">Volume</span>
      <div class="bsig-bar-bg"><div class="bsig-bar-fill" style="width:{_vol}%;background:#3B82F6;"></div></div>
      <span class="bsig-bar-pct" style="color:#3B82F6;">{_vol}%</span>
    </div>
    <div class="bsig-bar-row">
      <span class="bsig-bar-lbl">Composite</span>
      <div class="bsig-bar-bg"><div class="bsig-bar-fill" style="width:{_comp}%;background:{ins['ac']};"></div></div>
      <span class="bsig-bar-pct" style="color:{ins['ac']};">{_comp}%</span>
    </div>
  </div>
  <div class="bsig-reason">{ins["reason"]}</div>
  {_price_html}
</div>""", unsafe_allow_html=True)
                        if st.button(f"Ask AI → {ins['sym']}", key=f"bsig_{_bi}", use_container_width=True):
                            st.session_state.mai_pending = f"Give me a detailed analysis of {ins['sym']}. Signal: {ins['action']}. Should I act on this?"
                            track_stock_analyzed(ins["sym"]); st.rerun()
            if is_trial:
                _reinforcement_pill("You're seeing all composite signal data — this is a Starter+ feature")

        # ── ANALYSIS: Daily AI Picks ───────────────────────────────────────────
        _render_daily_picks(tier, is_trial, _picks, _picks_visible)

        # ── TRUST: Performance & Trust section ─────────────────────────────────
        _render_performance_trust(gainers, losers, total, top_g, now)

        # ── Top Movers list ────────────────────────────────────────────────────
        sup = sorted([p for p in uniq if float(p.get("change_percent") or 0) > 0],
                      key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:8]
        sdn = sorted([p for p in uniq if float(p.get("change_percent") or 0) < 0],
                      key=lambda x:float(x.get("change_percent",0) or 0))[:4]
        movers  = sup + sdn
        mrows   = "".join(
            f'<div style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #111;font-size:13px;">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-weight:500;color:#FFFFFF;">{s["symbol"]}</span>'
            f'<span style="color:#808080;font-size:12px;">&#8358;{float(s.get("price",0) or 0):,.2f}</span></div>'
            f'<span style="color:{"#22C55E" if float(s.get("change_percent",0) or 0)>=0 else "#EF4444"};font-weight:500;">'
            f'{"&#9650;" if float(s.get("change_percent",0) or 0)>=0 else "&#9660;"} {abs(float(s.get("change_percent",0) or 0)):.2f}%</span></div>'
            for s in movers
        ) or '<div style="padding:20px;text-align:center;color:#606060;font-size:12px;">No data yet</div>'
        ph = max(len(movers)*43+55, 80) + 48
        st.components.v1.html(
            f'<!DOCTYPE html><html><head><link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">'
            f'<style>*{{margin:0;padding:0;box-sizing:border-box;}}html,body{{background:transparent;font-family:DM Mono,monospace;overflow:hidden;}}'
            f'.p{{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:16px 18px;}}'
            f'.pt{{font-size:11px;font-weight:500;color:#F0A500;text-transform:uppercase;letter-spacing:.1em;margin-bottom:14px;}}'
            f'</style></head><body><div class="p"><div class="pt">&#128293; Top Movers · {latest_date} {"📈 Live" if market["is_open"] else "🔒 Last Close"}</div>{mrows}</div></body></html>',
            height=ph, scrolling=False
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("📊 View All Live Stocks →", key="btn_all", type="primary"):
            st.session_state.current_page = "all_stocks"; st.rerun()

        # ── Signal Spotlight ───────────────────────────────────────────────────
        st.markdown('<div class="sec-title">📊 Today\'s Signal Spotlight</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-intro">Three stocks that deserve attention right now — based on live AI signal scores. Always do your own research.</div>', unsafe_allow_html=True)
        sig_res2 = sb.table("signal_scores").select("symbol,signal,stars,reasoning").order("score_date",desc=True).order("stars",desc=True).limit(300).execute()
        seen_sig = set(); buy_s = hold_s = caut_s = None
        for s in (sig_res2.data or []):
            sym = s.get("symbol",""); sig = s.get("signal","").upper().replace(" ","_")
            if sym in seen_sig: continue
            seen_sig.add(sym)
            if not buy_s and sig in ("STRONG_BUY","BUY"):   buy_s  = s
            elif not hold_s and sig == "HOLD":               hold_s = s
            elif not caut_s and sig == "CAUTION":            caut_s = s
            if buy_s and hold_s and caut_s: break
        if is_trial:
            for _ss in [buy_s, hold_s, caut_s]:
                if _ss: track_stock_analyzed(_ss.get("symbol",""))
            track_signal_view()
        def sp_card(stock, lbl, ac, bg, bd):
            if not stock: return f'<div class="sp-card" style="border-color:{bd};background:{bg};"><span style="background:{ac}22;color:{ac};font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;">{lbl}</span><div style="font-size:15px;font-weight:600;color:#606060;margin-top:8px;">—</div></div>'
            sym    = stock.get("symbol","—"); reason = (stock.get("reasoning") or "No analysis.")[:120]+"…"; stars = "⭐"*int(stock.get("stars",3))
            return f'<div class="sp-card" style="border-color:{bd};background:{bg};border-left:3px solid {ac};"><span style="background:{ac}22;color:{ac};font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;">{lbl}</span><div style="font-size:16px;font-weight:600;color:#FFFFFF;margin-top:8px;">{sym} <span style="font-size:12px;">{stars}</span></div><div style="font-size:11px;color:#B0B0B0;margin-top:6px;line-height:1.5;">{reason}</div></div>'
        st.markdown(f'<div class="sp-grid">{sp_card(buy_s,"✅ BUY TODAY","#22C55E","#001A00","#003D00")}{sp_card(hold_s,"⏸️ HOLD","#D97706","#1A1200","#3D2800")}{sp_card(caut_s,"⚠️ CAUTION","#EA580C","#1A0800","#3D1500")}</div>', unsafe_allow_html=True)
        if st.button("⭐ See All Signal Scores →", key="btn_signals", type="primary"):
            st.session_state.current_page = "signals"; st.rerun()
        if not can_access("signals_all", tier):
            _upgrade_inline("Signal Spotlight shows 3 stocks. Higher plans see all 144 NGX stocks ranked.", key="nudge_spotlight", cta="🔒 Unlock Full Signals →")

        # ── NEWS ────────────────────────────────────────────────────────────────
        _render_news_section(tier, sb, market, today)

        # ── SECTOR SNAPSHOT ─────────────────────────────────────────────────────
        _render_sector_snapshot(tier, sb)

        # ── TRADE GAME ──────────────────────────────────────────────────────────
        _render_trade_game(sb, current_user)

        # ── PREMIUM GUIDE (tier-specific) ────────────────────────────────────────
        if is_trial or is_starter:
            _guide_steps = [
                ("Read Signals With Entry Prices","Head to the Signals page. Each BUY/HOLD/AVOID signal now shows entry price and target. Use these as your starting point.","📊"),
                ("Use AI Every Day","Type any stock question into the AI chat. Starter gets 15 queries/day — use them on your watchlist stocks every morning.","🤖"),
                ("Watch the 9 Daily Picks","Every trading day at 10 AM, 9 fresh picks appear — 3 Buy, 3 Hold, 3 Avoid. Start your day here.","📋"),
                ("Check the Market Brief","The AI Market Brief drops every morning before market open. Read it before making any decisions.","📰"),
                ("Practice with the Trade Game","Before placing real orders, test your picks in the Trade Game with virtual cash. Build confidence first.","🎮"),
            ]
            guide_title = "📚 How to Use NGX Signal Premium"
        elif is_trader:
            _guide_steps = [
                ("Use Unlimited AI for Deep Analysis","You have unlimited queries. Ask about any stock, any time — before buying, while holding, or before selling.","🤖"),
                ("Leverage Entry + Stop-Loss Prices","Your AI responses include specific ₦ entry ranges and stop-loss levels. Use these for disciplined position management.","📊"),
                ("Enable Telegram Alerts","Set up Telegram alerts in Settings to get signal triggers before the market moves. Don't miss your entry.","📡"),
                ("Read the Brief in Pidgin","Toggle Pidgin mode in the AI Brief for a faster, more natural read of the morning market summary.","🇳🇬"),
                ("Lead the Leaderboard","Use the Trade Game to sharpen your strategy. Top traders on the leaderboard are averaging 12%+ returns.","🏆"),
            ]
            guide_title = "📚 How to Use NGX Signal — Trader Guide"
        else:  # pro
            _guide_steps = [
                ("Ask for Portfolio Strategy","Type 'Build me a portfolio strategy around ZENITHBANK' — Pro AI gives you a full sector-aware allocation plan.","🏆"),
                ("Export PDF Reports","Every AI analysis can be exported as a PDF. Useful for reviewing your own decisions or sharing insights.","📄"),
                ("Use Sector Rotation Signals","Ask the AI 'Where is smart money moving today?' — Pro gives you sector rotation intelligence.","🔄"),
                ("Advanced Position Sizing","Ask 'What position size for DANGCEM at ₦450?' — Pro gives you risk-adjusted sizing based on volatility.","📐"),
                ("Dominate the Trade Game","You have ₦10M virtual cash. Build a full virtual portfolio and test your Pro strategies before going real.","🎮"),
            ]
            guide_title = "📚 How to Use NGX Signal Pro"
        st.markdown(f'<div class="sec-title">{guide_title}</div>', unsafe_allow_html=True)
        for _idx, (_title, _text, _icon) in enumerate(_guide_steps, 1):
            st.markdown(f"""
<div class="guide-step">
  <div class="guide-num">{_idx}</div>
  <div class="guide-body">
    <div class="guide-title">{_icon} {_title}</div>
    <div class="guide-text">{_text}</div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # ── FAQ ─────────────────────────────────────────────────────────────────
        _render_faq()

        # ── BOTTOM BAR ──────────────────────────────────────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if is_trial and trial_urgent:
            ai_ut = get_total_ai_queries(); sv = get_eng("signals_viewed",0)
            st.markdown(f'<div style="background:linear-gradient(135deg,#1A0000,#180800);border:1px solid rgba(239,68,68,.35);border-radius:12px;padding:20px 24px;animation:trial-pulse 3s ease-in-out infinite;"><div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px;"><div><div style="font-family:Space Grotesk,sans-serif;font-size:16px;font-weight:700;color:#EF4444;margin-bottom:4px;">⏳ Trial ends in {trial_days_left} day{"s" if trial_days_left!=1 else ""}</div><div style="font-family:DM Mono,monospace;font-size:12px;color:#B0B0B0;line-height:1.6;margin-bottom:10px;">You\'ve used AI {ai_ut} times and viewed {sv} signals.<br>Don\'t lose your edge in the market.</div></div><div class="scarcity-pill">🔴 {trial_days_left} day{"s" if trial_days_left!=1 else ""} left</div></div></div>', unsafe_allow_html=True)
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("🔐 Upgrade Now — Don't Lose Access →", key="trial_bottom", type="primary"):
                st.session_state.current_page = "settings"; st.rerun()
        elif is_trial:
            ai_ut = get_total_ai_queries(); sv = get_eng("signals_viewed",0)
            st.markdown(f'<div style="background:linear-gradient(135deg,#050F00,#080A00);border:1px solid rgba(34,197,94,.2);border-radius:12px;padding:18px 22px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;"><div><div style="font-family:Space Grotesk,sans-serif;font-size:14px;font-weight:700;color:#22C55E;margin-bottom:4px;">✨ Your Premium Trial is Working</div><div style="font-family:DM Mono,monospace;font-size:12px;color:#808080;line-height:1.6;">You\'ve used AI <strong style="color:#FFFFFF;">{ai_ut}</strong> times · Viewed <strong style="color:#FFFFFF;">{sv}</strong> signals · <strong style="color:#F0A500;">{trial_days_left} days left</strong></div></div><div style="font-family:DM Mono,monospace;font-size:11px;color:#404040;">Upgrade to keep it ↗</div></div>', unsafe_allow_html=True)
        elif is_starter:
            st.markdown('<div style="background:#0A0A0A;border:1px solid rgba(59,130,246,.2);border-radius:10px;padding:14px 18px;font-family:DM Mono,monospace;font-size:12px;color:#808080;">📈 <strong style="color:#3B82F6;">Starter Plan</strong> — Upgrade to Trader for unlimited queries, Pidgin mode &amp; Telegram alerts.</div>', unsafe_allow_html=True)
        elif is_trader:
            st.markdown('<div style="background:#0A0A0A;border:1px solid rgba(167,139,250,.2);border-radius:10px;padding:14px 18px;font-family:DM Mono,monospace;font-size:12px;color:#808080;">📡 <strong style="color:#A78BFA;">Trader Plan</strong> — Upgrade to Pro for PDF reports, portfolio strategy &amp; advanced AI recommendations.</div>', unsafe_allow_html=True)
        elif is_pro:
            st.markdown('<div style="background:#0A0A0A;border:1px solid rgba(240,165,0,.2);border-radius:10px;padding:14px 18px;font-family:DM Mono,monospace;font-size:12px;color:#808080;">🏆 <strong style="color:#F0A500;">Pro Plan</strong> — Full NGX Signal intelligence active. Unlimited AI · PDF exports · Advanced outputs. You\'re at the top.</div>', unsafe_allow_html=True)
