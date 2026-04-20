"""
NGX Signal — Home View  v13
════════════════════════════════════════════════════════════════════════
Fixes from v12:
  • AttributeError: user is Pydantic model → use getattr() safely
  • Removed daily_picks section (duplicate of signal cards)
  • Removed hardcoded pick fallbacks entirely
  • Replaced boring metric cards with glassmorphic premium cards
  • All ▲ green / ▼ red colour-coded data across the board
  • Consolidated to single upgrade CTA per page

Design: Premium dark glass — Syne + JetBrains Mono
        Frosted glass cards, glowing accent borders, coloured data
════════════════════════════════════════════════════════════════════════
"""

import streamlit as st
import re
import requests
import hashlib
from datetime import date, datetime, timedelta
from app.utils.supabase_client import get_supabase
from app.views.signals import generate_trending_sentiment_tag
from app.views.global_pulse import (
    render_global_pulse_strip, get_global_pulse,
    get_global_pulse_for_ai, get_sector_global_context,
)

# ─── Timezone ───────────────────────────────────────────────────────────────
try:
    import pytz
    _WAT = pytz.timezone("Africa/Lagos")
    def now_wat(): return datetime.now(_WAT)
except ImportError:
    from datetime import timezone
    _WAT_OFFSET = timezone(timedelta(hours=1))
    def now_wat(): return datetime.now(_WAT_OFFSET)

NG_HOLIDAYS_2026 = {
    "2026-01-01","2026-01-03","2026-04-03","2026-04-06",
    "2026-05-01","2026-06-12","2026-10-01","2026-12-25","2026-12-26",
}

# ─── Cached loaders ──────────────────────────────────────────────────────────
@st.cache_resource
def _get_sb():
    return get_supabase()

@st.cache_data(ttl=300)
def _load_prices():
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
def _load_market_summary():
    sb = _get_sb()
    res = sb.table("market_summary").select("*").order("trading_date", desc=True).limit(1).execute()
    return res.data[0] if res.data else {}

@st.cache_data(ttl=180)
def _load_signals():
    sb = _get_sb()
    res = sb.table("signal_scores").select(
        "symbol,signal,stars,reasoning,momentum_score,volume_score,news_score"
    ).order("score_date", desc=True).order("stars", desc=True).limit(50).execute()
    return res.data or []

@st.cache_data(ttl=120)
def _load_news():
    sb = _get_sb()
    res = sb.table("news").select(
        "headline,sentiment,scraped_at"
    ).order("scraped_at", desc=True).limit(20).execute()
    return res.data or []

@st.cache_data(ttl=300)
def _load_sectors():
    sb = _get_sb()
    res = sb.table("sector_performance").select(
        "sector_name,traffic_light,change_percent,verdict"
    ).order("change_percent", desc=True).execute()
    return res.data or []

@st.cache_data(ttl=300)
def _load_briefs():
    sb = _get_sb()
    res = sb.table("ai_briefs").select("body,brief_date") \
        .eq("language", "en").eq("brief_type", "morning") \
        .order("brief_date", desc=True).limit(1).execute()
    return res.data or []

# ─── Tier system ─────────────────────────────────────────────────────────────
TIER_ORDER = ["visitor","free","trial","starter","trader","pro"]
PAID_TIERS = {"starter","trader","pro"}

_FEATURE_MIN = {
    "ai_input":              "free",
    "ai_full_response":      "trial",
    "ai_advanced_outputs":   "pro",
    "signals_all":           "trial",
    "signals_confidence":    "starter",
    "brief_full":            "trial",
    "brief_pidgin":          "trader",
    "sector_all":            "trial",
    "news_full":             "trial",
    "export_pdf":            "pro",
    "telegram_alerts":       "starter",
    "stop_loss_visible":     "trader",
}

_QUERY_LIMITS = {
    "visitor":0, "free":2, "trial":None,
    "starter":15, "trader":None, "pro":None,
}

def get_user_tier() -> str:
    user    = st.session_state.get("user")
    profile = st.session_state.get("profile", {})
    if not user: return "visitor"
    plan = (profile.get("plan") or "free").lower().strip()
    return plan if plan in ("starter","trader","pro","trial","free") else "free"

def _rank(t): 
    try: return TIER_ORDER.index(t)
    except: return 0

def can_access(feature, tier=None):
    t   = tier or get_user_tier()
    req = _FEATURE_MIN.get(feature, "visitor")
    return _rank(t) >= _rank(req)

def get_usage_limit(tier=None):
    t = tier or get_user_tier()
    return _QUERY_LIMITS.get(t, 0)

# ─── Engagement / streak (mirrors v11 exactly) ───────────────────────────────
def _eng_key(k):           return f"eng_{k}"
def get_eng(k, default=0): return st.session_state.get(_eng_key(k), default)
def inc_eng(k, by=1):      st.session_state[_eng_key(k)] = get_eng(k) + by
def set_eng(k, v):         st.session_state[_eng_key(k)] = v

def track_signal_view():   inc_eng("signals_viewed")
def track_stock_analyzed(sym):
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

def get_streak() -> int: return st.session_state.get("ai_streak", 0)
def update_streak():
    today_s = str(date.today())
    last    = st.session_state.get("streak_last_date","")
    if last == today_s: return
    streak  = st.session_state.get("ai_streak", 0)
    streak  = streak + 1 if last == str(date.today() - timedelta(days=1)) else 1
    st.session_state.ai_streak        = streak
    st.session_state.streak_last_date = today_s
def streak_milestone(n):
    return {3:"3 days in a row",5:"5-day streak",7:"Full week",14:"14-day champion"}.get(n)

# ─── Trial helpers ────────────────────────────────────────────────────────────
def get_trial_days_left(profile):
    raw = profile.get("trial_start_date") or profile.get("created_at","")
    if not raw: return 14
    try:
        ts = datetime.fromisoformat(str(raw)[:10])
        return max(0, 14 - (datetime.utcnow() - ts).days)
    except: return 14

def get_trial_day_number(profile):
    raw = profile.get("trial_start_date") or profile.get("created_at","")
    if not raw: return 1
    try:
        ts = datetime.fromisoformat(str(raw)[:10])
        return min(14, max(1, (datetime.utcnow() - ts).days + 1))
    except: return 1

def was_trial_user(profile):
    return profile.get("was_trial",False) or profile.get("previous_plan") == "trial"

# ─── Market status ────────────────────────────────────────────────────────────
def get_market_status():
    now = now_wat()
    ds  = str(now.date())
    if ds in NG_HOLIDAYS_2026:
        return {"is_open":False,"label":"Closed — Public Holiday","note":"NGX closed today","color":"#606060"}
    if now.weekday() >= 5:
        return {"is_open":False,"label":"Closed — Weekend","note":"Opens Monday 10 AM WAT","color":"#606060"}
    h = now.hour + now.minute / 60
    if 10.0 <= h < 14.5:
        return {"is_open":True,"label":"Market Open","note":f"Closes 2:30 PM WAT","color":"#22C55E"}
    if h < 10.0:
        mins = int((10.0 - h) * 60)
        return {"is_open":False,"label":"Pre-Market","note":f"Opens in {mins} min","color":"#F0A500"}
    return {"is_open":False,"label":"Closed","note":"Last session ended 2:30 PM WAT","color":"#606060"}

# ─── AI call (mirrors v11 — Groq → Gemini → Anthropic → OpenAI) ─────────────
def call_ai(prompt_or_tuple, max_tokens=500):
    if isinstance(prompt_or_tuple, tuple):
        prompt, max_tokens = prompt_or_tuple
    else:
        prompt = prompt_or_tuple
    errors = []
    groq_key = st.secrets.get("GROQ_API_KEY","")
    if groq_key:
        for model in ["llama-3.3-70b-versatile","llama-3.1-8b-instant"]:
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization":f"Bearer {groq_key}","Content-Type":"application/json"},
                    json={"model":model,"messages":[{"role":"user","content":prompt}],
                          "max_tokens":max_tokens,"temperature":0.4},
                    timeout=20,
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                errors.append(f"Groq/{model}: {r.status_code}")
            except Exception as e:
                errors.append(f"Groq/{model}: {e}")
    gemini_key = st.secrets.get("GEMINI_API_KEY","")
    if gemini_key:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                json={"contents":[{"parts":[{"text":prompt}]}],
                      "generationConfig":{"maxOutputTokens":max_tokens,"temperature":0.4}},
                timeout=20,
            )
            if r.status_code == 200:
                parts = r.json().get("candidates",[{}])[0].get("content",{}).get("parts",[{}])
                return parts[0].get("text","").strip() if parts else None
            errors.append(f"Gemini: {r.status_code}")
        except Exception as e:
            errors.append(f"Gemini: {e}")
    for provider, key, model, url_fn in [
        ("anthropic", st.secrets.get("ANTHROPIC_API_KEY",""), "claude-3-5-haiku-20241022", None),
        ("openai",    st.secrets.get("OPENAI_API_KEY",""),    "gpt-4o-mini", None),
    ]:
        if not key: continue
        try:
            if provider == "anthropic":
                r = requests.post("https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":key,"anthropic-version":"2023-06-01","Content-Type":"application/json"},
                    json={"model":model,"max_tokens":max_tokens,"messages":[{"role":"user","content":prompt}]},
                    timeout=25)
                if r.status_code == 200:
                    return r.json()["content"][0]["text"].strip()
            else:
                r = requests.post("https://api.openai.com/v1/chat/completions",
                    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
                    json={"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens},
                    timeout=25)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            errors.append(f"{provider}: {r.status_code}")
        except Exception as e:
            errors.append(f"{provider}: {e}")
    if errors:
        st.warning(f"AI temporarily unavailable. ({'; '.join(errors[:2])})")
    return None

# ─── Misc helpers ─────────────────────────────────────────────────────────────
def _daily_seed(): return str(date.today())
def _time_ago(mins):
    if mins < 1:  return "just now"
    if mins < 60: return f"{mins}m ago"
    return f"{mins//60}h ago"
def _fmt(n): return f"₦{n:,.2f}" if n > 0 else "—"

def _safe_email(user):
    """Safely extract email from Pydantic user object or dict."""
    if user is None: return ""
    try:
        if hasattr(user, "email"): return user.email or ""
        if isinstance(user, dict): return user.get("email","")
    except Exception: pass
    return ""

def _unlock_cta(key, tier, page="settings"):
    if tier == "visitor":
        st.session_state.show_auth    = True
        st.session_state.current_page = "home"
    else:
        st.session_state.deep_link_plan = True
        st.session_state.current_page   = page
    st.rerun()

def _dynamic_cta(tier, profile):
    if tier == "visitor":  return "Start free — 14-day premium trial →", "home"
    if tier == "free":
        return ("Renew premium access →" if was_trial_user(profile)
                else "Unlock premium signals →"), "settings"
    if tier == "trial":
        dl = get_trial_days_left(profile)
        return (f"Upgrade now — {dl} day{'s' if dl!=1 else ''} left →"), "settings"
    if tier == "starter":  return "Upgrade to Trader →", "settings"
    if tier == "trader":   return "Upgrade to Pro →", "settings"
    return "", ""

def _classify_query(q):
    q = q.lower()
    for t in ["should i","is it good","buy or not","worth buying","is this a buy",
              "should i buy","should i sell","should i hold","good investment","worth it"]:
        if t in q: return "decision"
    return "explain"

def _build_ai_prompt(tier, ad, aarr, acg, mood, gc, lc, total,
                     top_g_text, latest_date, market_open, question, global_context=""):
    mode = _classify_query(question)
    persona = (
        "You are NGX Signal AI — a smart, direct Nigerian stock market assistant.\n"
        "Rules: answer directly, plain English, no filler phrases, NGX-focused.\n\n"
    )
    mktx = (
        f"Market data ({latest_date}): ASI {ad} ({aarr}{abs(acg):.2f}%), "
        f"{'Open' if market_open else 'Closed'}, {mood}, {gc} gainers / {lc} losers / {total} total.\n"
        f"Top movers: {top_g_text or 'none'}.\n"
        + (f"{global_context}\n" if global_context else "")
    )
    if mode == "decision":
        decision = "Start FIRST LINE with: 'Recommendation: BUY ✅' or 'HOLD ⚖️' or 'AVOID ❌'\n"
    else:
        decision = "Lead with the most important insight.\n"

    tier_fmt = {
        "free":    ("Max 3 lines. Recommendation + 1 reason. End with upgrade nudge.", 180),
        "starter": ("Recommendation + Key Signals (Trend/Momentum/Risk) + one Tip. Under 120 words.", 250),
        "trader":  ("Recommendation + Key Signals + Action Tip with price level. Under 180 words.", 350),
    }.get(tier, ("Full analysis: Recommendation + Key Insights + Action Plan (Entry/Watch/Risk). Under 280 words. End: 'Educational only — not financial advice.'", 500))

    fmt, max_tok = tier_fmt
    prompt = persona + mktx + decision + fmt + f"\n\nQuestion: {question}"
    return prompt, max_tok


# ─── Fonts & CSS ─────────────────────────────────────────────────────────────
_FONTS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
"""

_CSS = """<style>
/* ── Reset ── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}

/* ── Design tokens ── */
:root {
  --amber:#F0A500; --amber-dim:rgba(240,165,0,.12); --amber-bd:rgba(240,165,0,.28);
  --green:#22C55E; --green-dim:rgba(34,197,94,.1);  --green-bd:rgba(34,197,94,.25);
  --red:#EF4444;   --red-dim:rgba(239,68,68,.1);    --red-bd:rgba(239,68,68,.25);
  --blue:#60A5FA;  --blue-dim:rgba(96,165,250,.08); --blue-bd:rgba(96,165,250,.22);
  --purple:#A78BFA;
  --s0:#030305; --s1:#08080D; --s2:#0D0D14; --s3:#12121A; --s4:#18181F;
  --b1:rgba(255,255,255,.04); --b2:rgba(255,255,255,.07); --b3:rgba(255,255,255,.12);
  --t1:#F0EFFE; --t2:#A09EBB; --t3:#605E78; --t4:#302E48;
  --fh:'Syne',sans-serif; --fm:'JetBrains Mono',monospace;
  --r1:8px; --r2:14px; --r3:20px; --r4:28px;
  /* glass */
  --glass-bg:rgba(255,255,255,.03);
  --glass-border:rgba(255,255,255,.08);
  --glass-glow-amber:0 0 32px rgba(240,165,0,.08);
  --glass-glow-green:0 0 32px rgba(34,197,94,.08);
}

/* ── App overrides ── */
.stApp{background:var(--s0)!important;}
.block-container{padding-top:0!important;padding-bottom:48px!important;max-width:800px!important;}
div[data-testid="stVerticalBlock"]>div{gap:0!important;}
section[data-testid="stSidebar"]{background:var(--s1)!important;}

/* ── Subtle dot-grid background ── */
.stApp::before{
  content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:radial-gradient(rgba(255,255,255,.03) 1px,transparent 1px);
  background-size:28px 28px;
}

/* ── Glass card ── */
.gc{
  background:var(--glass-bg);
  border:0.5px solid var(--glass-border);
  border-radius:var(--r3);
  backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);
  padding:20px 22px;
  margin-bottom:10px;
  position:relative;
  overflow:hidden;
}
.gc::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(255,255,255,.03) 0%,transparent 60%);
  pointer-events:none;
}
.gc-sm{
  background:var(--glass-bg);
  border:0.5px solid var(--glass-border);
  border-radius:var(--r2);
  backdrop-filter:blur(8px);
  -webkit-backdrop-filter:blur(8px);
  padding:14px 16px;
}
.gc-inset{
  background:rgba(255,255,255,.02);
  border:0.5px solid rgba(255,255,255,.05);
  border-radius:var(--r1);
  padding:10px 13px;
}

/* ── Accent top glow line ── */
.glow-amber{border-top:1px solid var(--amber)!important;box-shadow:var(--glass-glow-amber);}
.glow-green{border-top:1px solid var(--green)!important;box-shadow:var(--glass-glow-green);}
.glow-red  {border-top:1px solid var(--red)!important;  box-shadow:0 0 32px rgba(239,68,68,.08);}
.glow-blue {border-top:1px solid var(--blue)!important; box-shadow:0 0 32px rgba(96,165,250,.08);}
.glow-left-amber{border-left:2px solid var(--amber)!important;border-radius:0 var(--r2) var(--r2) 0!important;}

/* ── Metric tiles (glassmorphic) ── */
.metric-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;}
.metric-tile{
  background:var(--glass-bg);
  border:0.5px solid var(--glass-border);
  border-radius:var(--r2);
  backdrop-filter:blur(10px);
  padding:16px 16px 14px;
  position:relative;overflow:hidden;
  transition:border-color .25s,box-shadow .25s;
}
.metric-tile:hover{border-color:var(--b3);box-shadow:0 4px 24px rgba(0,0,0,.4);}
.metric-tile::after{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.12),transparent);
}
.mt-label{font-family:var(--fm);font-size:9px;font-weight:500;color:var(--t3);
  letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px;}
.mt-value{font-family:var(--fh);font-size:22px;font-weight:800;line-height:1;
  letter-spacing:-.02em;margin-bottom:5px;}
.mt-sub{font-family:var(--fm);font-size:10px;color:var(--t3);line-height:1.4;}
.mt-icon{position:absolute;top:14px;right:14px;font-size:16px;opacity:.35;}
.col-green{color:var(--green)!important;}
.col-red  {color:var(--red)!important;}
.col-amber{color:var(--amber)!important;}
.col-blue {color:var(--blue)!important;}
.col-muted{color:var(--t2)!important;}

/* ── Signal cards ── */
.sig-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;}
.sig-card{
  background:var(--glass-bg);
  border:0.5px solid var(--glass-border);
  border-radius:var(--r2);
  backdrop-filter:blur(8px);
  padding:16px 15px 14px;
  position:relative;overflow:hidden;
  transition:transform .18s,border-color .2s,box-shadow .2s;
  animation:card-in .3s ease both;
}
.sig-card:hover{transform:translateY(-2px);border-color:var(--b3);}
.sig-card::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(160deg,rgba(255,255,255,.025) 0%,transparent 55%);
  pointer-events:none;
}
.sc-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px;}
.sc-sym{font-family:var(--fh);font-size:16px;font-weight:800;color:var(--t1);letter-spacing:-.01em;}
.sc-name{font-family:var(--fm);font-size:9px;color:var(--t3);margin-bottom:11px;}
.sc-price-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;}
.sc-pl{font-family:var(--fm);font-size:9px;color:var(--t3);letter-spacing:.08em;text-transform:uppercase;}
.sc-pv{font-family:var(--fm);font-size:12px;font-weight:500;color:var(--t1);}
.sc-divider{height:.5px;background:rgba(255,255,255,.05);margin:9px 0;}
.sc-reason{font-family:var(--fm);font-size:10px;color:var(--t2);line-height:1.6;}
.sc-lock{
  position:absolute;inset:0;border-radius:var(--r2);
  background:rgba(3,3,5,.82);backdrop-filter:blur(3px);
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;
}
.sc-lock-icon{font-size:17px;line-height:1;}
.sc-lock-text{font-family:var(--fm);font-size:10px;color:var(--t3);}

/* ── Pill badges ── */
.pill{display:inline-flex;align-items:center;gap:4px;font-family:var(--fm);
  font-size:9px;font-weight:600;padding:3px 9px;border-radius:999px;letter-spacing:.06em;}
.pill-green{background:var(--green-dim);border:.5px solid var(--green-bd);color:var(--green);}
.pill-red  {background:var(--red-dim);  border:.5px solid var(--red-bd);  color:var(--red);}
.pill-amber{background:var(--amber-dim);border:.5px solid var(--amber-bd);color:var(--amber);}
.pill-blue {background:var(--blue-dim); border:.5px solid var(--blue-bd); color:var(--blue);}
.pill-ghost{background:rgba(255,255,255,.04);border:.5px solid var(--b2);color:var(--t3);}
.pill-purple{background:rgba(167,139,250,.1);border:.5px solid rgba(167,139,250,.25);color:var(--purple);}

/* ── Live pulse dot ── */
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.dot-g{background:var(--green);animation:dot-pulse 2s ease-in-out infinite;}
.dot-a{background:var(--amber);animation:dot-pulse 2s ease-in-out infinite;}
.dot-r{background:var(--red);  animation:dot-pulse 2s ease-in-out infinite;}
@keyframes dot-pulse{
  0%{box-shadow:0 0 0 0 rgba(34,197,94,.5);}
  70%{box-shadow:0 0 0 7px rgba(34,197,94,0);}
  100%{box-shadow:0 0 0 0 rgba(34,197,94,0);}
}

/* ── Section header ── */
.sh{display:flex;align-items:center;justify-content:space-between;
  margin:18px 0 11px;padding-bottom:9px;border-bottom:.5px solid rgba(255,255,255,.05);}
.sh-title{font-family:var(--fh);font-size:12px;font-weight:700;color:var(--t2);
  letter-spacing:.06em;text-transform:uppercase;}
.sh-action{font-family:var(--fm);font-size:11px;color:var(--t3);}

/* ── Notification banner ── */
.notif{
  display:flex;align-items:center;gap:10px;
  background:var(--glass-bg);border:.5px solid var(--glass-border);
  border-left:1.5px solid var(--amber);border-radius:var(--r1);
  padding:10px 14px;margin-bottom:10px;
  font-family:var(--fm);font-size:11px;color:var(--t2);
  animation:slide-down .35s ease both;
}
.notif-g{border-left-color:var(--green)!important;}
.notif-r{border-left-color:var(--red)!important;}

/* ── Market status bar ── */
.mkt-strip{display:grid;grid-template-columns:repeat(4,1fr);
  border:.5px solid var(--glass-border);border-radius:var(--r2);
  overflow:hidden;margin-bottom:12px;background:var(--glass-bg);}
.mkt-cell{padding:14px 16px;border-right:.5px solid rgba(255,255,255,.05);}
.mkt-cell:last-child{border-right:none;}
.mkt-label{font-family:var(--fm);font-size:9px;color:var(--t3);
  letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px;}
.mkt-val{font-family:var(--fh);font-size:19px;font-weight:800;
  letter-spacing:-.02em;line-height:1;margin-bottom:3px;}
.mkt-sub{font-family:var(--fm);font-size:10px;color:var(--t3);}

/* ── Greeting ── */
.greet-wrap{padding:20px 0 8px;}
.greet-name{font-family:var(--fh);font-size:24px;font-weight:800;
  color:var(--t1);letter-spacing:-.02em;}
.greet-date{font-family:var(--fm);font-size:10px;color:var(--t3);
  letter-spacing:.1em;text-transform:uppercase;margin-top:3px;}
.tier-badge{display:inline-flex;align-items:center;font-family:var(--fm);
  font-size:9px;font-weight:600;padding:2px 9px;border-radius:999px;
  letter-spacing:.07em;text-transform:uppercase;margin-left:9px;vertical-align:middle;}
.tb-free   {background:rgba(255,255,255,.05);border:.5px solid var(--b2);color:var(--t3);}
.tb-trial  {background:var(--green-dim);border:.5px solid var(--green-bd);color:var(--green);}
.tb-starter{background:var(--blue-dim); border:.5px solid var(--blue-bd); color:var(--blue);}
.tb-trader {background:rgba(167,139,250,.1);border:.5px solid rgba(167,139,250,.25);color:var(--purple);}
.tb-pro    {background:var(--amber-dim);border:.5px solid var(--amber-bd);color:var(--amber);}

/* ── Trial bars ── */
.trial-banner{
  border-radius:var(--r1);padding:10px 14px;margin-bottom:10px;
  display:flex;align-items:center;justify-content:space-between;
  font-family:var(--fm);font-size:11px;flex-wrap:wrap;gap:8px;
}
.tb-ok{background:var(--green-dim);border:.5px solid var(--green-bd);}
.tb-urgent{background:var(--red-dim);border:.5px solid var(--red-bd);
  animation:trial-pulse 3s ease-in-out infinite;}
.trial-prog{
  background:var(--glass-bg);border:.5px solid var(--glass-border);
  border-radius:var(--r1);padding:10px 14px;margin-bottom:10px;
}
.prog-track{height:2px;background:rgba(255,255,255,.06);border-radius:1px;
  overflow:hidden;margin:6px 0;}
.prog-fill{height:2px;border-radius:1px;transition:width .6s ease;}

/* ── Hero (visitor) ── */
.hero{
  padding:44px 24px 32px;text-align:center;position:relative;
  border-bottom:.5px solid rgba(255,255,255,.04);
}
.hero::before{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 60% 50% at 50% 0%,rgba(240,165,0,.06) 0%,transparent 70%);
  pointer-events:none;
}
.hero-eye{
  display:inline-flex;align-items:center;gap:7px;
  font-family:var(--fm);font-size:11px;color:var(--green);
  background:var(--green-dim);border:.5px solid var(--green-bd);
  border-radius:999px;padding:5px 14px;margin-bottom:20px;
  animation:fade-up .5s ease both;
}
.hero-h1{
  font-family:var(--fh);font-size:clamp(26px,5vw,38px);font-weight:800;
  color:var(--t1);letter-spacing:-.03em;line-height:1.1;margin-bottom:14px;
  animation:fade-up .5s .08s ease both;
}
.hero-h1 span{color:var(--amber);}
.hero-sub{
  font-family:var(--fm);font-size:13px;color:var(--t2);line-height:1.8;
  max-width:450px;margin:0 auto 28px;animation:fade-up .5s .16s ease both;
}
.hero-ctas{display:flex;align-items:center;justify-content:center;gap:10px;
  flex-wrap:wrap;margin-bottom:14px;animation:fade-up .5s .24s ease both;}
.btn-pri{
  font-family:var(--fh);font-size:14px;font-weight:700;
  color:#0A0A0A;background:var(--amber);border:none;
  border-radius:var(--r1);padding:13px 26px;cursor:pointer;
  transition:opacity .15s,transform .12s;letter-spacing:-.01em;
}
.btn-pri:hover{opacity:.9;transform:translateY(-1px);}
.btn-sec{
  font-family:var(--fm);font-size:12px;color:var(--t2);
  background:var(--glass-bg);border:.5px solid var(--b2);
  border-radius:var(--r1);padding:13px 22px;cursor:pointer;
  transition:border-color .15s,color .15s;
}
.btn-sec:hover{border-color:var(--b3);color:var(--t1);}
.hero-note{font-family:var(--fm);font-size:10px;color:var(--t4);
  animation:fade-up .5s .32s ease both;}

/* ── Trust bar ── */
.trust{
  display:flex;align-items:center;justify-content:center;
  gap:18px;flex-wrap:wrap;padding:11px 20px;
  border-top:.5px solid rgba(255,255,255,.04);
  border-bottom:.5px solid rgba(255,255,255,.04);
  background:var(--glass-bg);
}
.trust-item{display:flex;align-items:center;gap:6px;
  font-family:var(--fm);font-size:11px;color:var(--t3);}
.trust-check{color:var(--green);font-size:11px;}
.trust-sep{width:1px;height:11px;background:rgba(255,255,255,.06);}

/* ── Personalized strip ── */
.p-strip{
  display:flex;align-items:center;gap:9px;
  background:var(--glass-bg);border:.5px solid var(--glass-border);
  border-left:1.5px solid var(--amber);border-radius:var(--r1);
  padding:9px 13px;margin-bottom:10px;
  font-family:var(--fm);font-size:11px;color:var(--t2);
}

/* ── AI chat ── */
.ai-wrap{
  background:var(--glass-bg);border:.5px solid var(--glass-border);
  border-radius:var(--r3);padding:16px 18px;margin-bottom:10px;
}
.ai-msg-user{
  background:rgba(255,255,255,.05);border:.5px solid var(--b2);
  border-radius:var(--r2) var(--r2) 3px var(--r2);
  padding:10px 14px;font-family:var(--fm);font-size:12px;color:var(--t1);
  margin-left:12%;animation:msg-in .22s ease both;margin-bottom:8px;
}
.ai-msg-ai{
  background:rgba(240,165,0,.04);
  border:.5px solid var(--amber-bd);border-left:1.5px solid var(--amber);
  border-radius:3px var(--r2) var(--r2) var(--r2);
  padding:12px 14px;font-family:var(--fm);font-size:12px;color:var(--t1);
  line-height:1.7;animation:msg-in .22s ease both;margin-bottom:8px;
}
.ai-blurred{filter:blur(4px);user-select:none;pointer-events:none;}
.ai-chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 2px;}
.ai-chip{
  font-family:var(--fm);font-size:10px;color:var(--t2);
  background:rgba(255,255,255,.03);border:.5px solid var(--b2);
  border-radius:var(--r1);padding:5px 11px;cursor:pointer;
  transition:border-color .15s,color .15s;
}
.ai-chip:hover{border-color:var(--amber-bd);color:var(--amber);}

/* ── Pro Command Center ── */
.pcc{
  background:var(--glass-bg);border:.5px solid var(--glass-border);
  border-radius:var(--r4);overflow:hidden;margin-bottom:14px;
  animation:card-in .4s ease both;
  box-shadow:var(--glass-glow-amber);
}
.pcc-glow-bar{height:1px;background:linear-gradient(90deg,transparent,var(--amber),transparent);}
.pcc-head{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 20px;border-bottom:.5px solid rgba(255,255,255,.05);
}
.pcc-head-left{display:flex;align-items:center;gap:9px;}
.pcc-head-title{font-family:var(--fh);font-size:11px;font-weight:700;
  color:var(--amber);letter-spacing:.06em;text-transform:uppercase;}
.pcc-body{padding:20px;}
.pcc-hero{display:flex;align-items:flex-start;justify-content:space-between;
  margin-bottom:16px;gap:12px;flex-wrap:wrap;}
.pcc-sym{font-family:var(--fh);font-size:26px;font-weight:800;
  color:var(--t1);letter-spacing:-.02em;}
.pcc-co{font-family:var(--fm);font-size:10px;color:var(--t3);margin-top:2px;}
.pcc-upside{
  text-align:center;background:rgba(255,255,255,.03);
  border:.5px solid rgba(255,255,255,.07);border-radius:var(--r2);padding:9px 16px;
}
.pcc-upside-lbl{font-family:var(--fm);font-size:9px;color:var(--t3);
  letter-spacing:.1em;text-transform:uppercase;margin-bottom:3px;}
.pcc-upside-val{font-family:var(--fh);font-size:22px;font-weight:800;}
.pcc-prices{
  display:grid;grid-template-columns:repeat(3,1fr);
  gap:1px;background:rgba(255,255,255,.04);
  border-radius:var(--r1);overflow:hidden;margin-bottom:18px;
}
.pcc-price{background:rgba(8,8,13,.7);padding:11px 0;text-align:center;}
.pcc-price-lbl{font-family:var(--fm);font-size:9px;color:var(--t3);
  letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px;}
.pcc-price-val{font-family:var(--fm);font-size:13px;font-weight:500;color:var(--t1);}
.pcc-driver{
  display:flex;gap:9px;background:rgba(255,255,255,.02);
  border:.5px solid rgba(255,255,255,.04);border-radius:var(--r1);
  padding:10px 12px;margin-bottom:6px;
  font-family:var(--fm);font-size:11px;color:var(--t1);line-height:1.65;
}
.pcc-verdict{border-radius:var(--r1);padding:12px 14px;margin-bottom:18px;}
.pcc-verdict-lbl{font-family:var(--fm);font-size:9px;letter-spacing:.12em;
  text-transform:uppercase;margin-bottom:5px;}
.pcc-verdict-txt{font-family:var(--fh);font-size:14px;font-weight:600;
  color:var(--t1);line-height:1.5;}
.pcc-conf-row{display:flex;justify-content:space-between;
  align-items:center;margin-bottom:7px;}
.pcc-conf-lbl{font-family:var(--fm);font-size:10px;color:var(--t3);
  letter-spacing:.08em;text-transform:uppercase;}
.pcc-conf-val{font-family:var(--fm);font-size:13px;font-weight:600;}
.pcc-conf-pct{font-family:var(--fm);font-size:11px;color:var(--t3);margin-left:6px;}
.pcc-bar-track{display:flex;gap:2px;margin-bottom:18px;}
.pcc-bar-block{flex:1;height:4px;border-radius:2px;}
.pcc-ctx{
  display:flex;gap:9px;background:var(--blue-dim);
  border:.5px solid var(--blue-bd);border-radius:var(--r1);
  padding:10px 12px;margin-bottom:18px;
  font-family:var(--fm);font-size:11px;color:#9DC4FF;line-height:1.65;
}

/* ── Top movers ── */
.mover-row{
  display:flex;align-items:center;justify-content:space-between;
  padding:8px 0;border-bottom:.5px solid rgba(255,255,255,.04);
  font-family:var(--fm);
}
.mover-row:last-child{border-bottom:none;}
.mover-sym{font-family:var(--fh);font-size:13px;font-weight:700;color:var(--t1);}
.mover-price{font-size:10px;color:var(--t3);}
.mover-chg{font-size:12px;font-weight:500;}

/* ── Upgrade card ── */
.upg-card{
  background:linear-gradient(135deg,rgba(240,165,0,.06) 0%,rgba(240,165,0,.02) 100%);
  border:.5px solid var(--amber-bd);border-radius:var(--r3);
  padding:20px 22px;margin:14px 0 10px;
}
.upg-title{font-family:var(--fh);font-size:17px;font-weight:800;
  color:var(--amber);margin-bottom:5px;letter-spacing:-.01em;}
.upg-sub{font-family:var(--fm);font-size:12px;color:var(--t2);
  line-height:1.75;margin-bottom:14px;}
.upg-feats{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;}
.upg-feat{
  font-family:var(--fm);font-size:10px;color:var(--t2);
  background:rgba(255,255,255,.03);border:.5px solid var(--b2);
  border-radius:var(--r1);padding:4px 10px;
}

/* ── Streak ── */
.streak{
  display:inline-flex;align-items:center;gap:9px;
  background:var(--amber-dim);border:.5px solid var(--amber-bd);
  border-radius:var(--r1);padding:8px 14px;margin-bottom:10px;
  font-family:var(--fm);font-size:11px;color:var(--t2);
  animation:amber-glow 3s ease-in-out infinite;
}
.streak-num{font-family:var(--fh);font-size:20px;font-weight:800;
  color:var(--amber);animation:num-pop .4s ease both;}

/* ── Brief ── */
.brief-body{
  font-family:var(--fm);font-size:12px;color:var(--t1);
  line-height:1.85;padding:2px 0;
}
.brief-body strong{color:var(--amber);font-weight:600;}

/* ── Sector grid ── */
.sector-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}
.sector-card{
  background:var(--glass-bg);border:.5px solid var(--glass-border);
  border-radius:var(--r1);padding:11px 12px;font-family:var(--fm);
}
.sector-name{font-size:12px;font-weight:500;color:var(--t1);margin-bottom:3px;}
.sector-chg{font-size:13px;font-weight:600;}
.sector-verdict{font-size:9px;color:var(--t3);margin-top:2px;}

/* ── Downgrade modal ── */
.dg-overlay{min-height:500px;background:rgba(0,0,0,.92);
  display:flex;align-items:center;justify-content:center;
  padding:20px;border-radius:var(--r3);}
.dg-card{
  background:rgba(8,8,13,.96);border:.5px solid var(--red-bd);
  border-radius:var(--r4);padding:32px 28px;max-width:480px;width:100%;
  animation:modal-in .4s cubic-bezier(.16,1,.3,1) both;
}
.dg-title{font-family:var(--fh);font-size:21px;font-weight:800;
  color:var(--t1);text-align:center;margin-bottom:6px;}
.dg-sub{font-family:var(--fm);font-size:12px;color:var(--t2);
  text-align:center;line-height:1.65;margin-bottom:18px;}
.dg-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:18px;}
.dg-stat{background:var(--glass-bg);border:.5px solid var(--glass-border);
  border-radius:var(--r1);padding:12px 8px;text-align:center;}
.dg-stat-num{font-family:var(--fh);font-size:22px;font-weight:800;color:var(--amber);}
.dg-stat-lbl{font-family:var(--fm);font-size:9px;color:var(--t3);margin-top:2px;}
.dg-lost{
  background:var(--red-dim);border:.5px solid var(--red-bd);
  border-radius:var(--r1);padding:12px 14px;margin-bottom:18px;
}
.dg-lost-title{font-family:var(--fm);font-size:9px;font-weight:700;color:var(--red);
  letter-spacing:.1em;text-transform:uppercase;margin-bottom:8px;}
.dg-lost-item{font-family:var(--fm);font-size:11px;color:var(--t2);
  padding:4px 0;border-bottom:.5px solid rgba(255,255,255,.04);
  display:flex;align-items:center;gap:8px;}
.dg-lost-item:last-child{border-bottom:none;}

/* ── Bottom nudge ── */
.bot-nudge{
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;
  background:var(--glass-bg);border:.5px solid var(--amber-bd);
  border-radius:var(--r2);padding:14px 18px;margin-top:14px;
}
.bot-nudge-txt{font-family:var(--fm);font-size:12px;color:var(--t2);line-height:1.6;}
.bot-nudge-txt strong{color:var(--amber);}

/* ── Game card ── */
.game-card{
  display:flex;align-items:center;gap:16px;
  background:var(--glass-bg);border:.5px solid var(--glass-border);
  border-radius:var(--r2);padding:16px 18px;
}
.game-icon{font-size:28px;flex-shrink:0;}
.game-title{font-family:var(--fh);font-size:14px;font-weight:700;
  color:var(--t1);margin-bottom:3px;}
.game-sub{font-family:var(--fm);font-size:11px;color:var(--t2);line-height:1.55;}

/* ── News ── */
.news-item{padding:9px 0;border-bottom:.5px solid rgba(255,255,255,.04);
  font-family:var(--fm);}
.news-item:last-child{border-bottom:none;}
.news-hl{font-size:12px;color:var(--t1);line-height:1.55;margin-bottom:3px;}
.news-meta{font-size:10px;color:var(--t3);}

/* ── Animations ── */
@keyframes fade-up  {from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
@keyframes card-in  {from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:none;}}
@keyframes slide-down{from{opacity:0;transform:translateY(-8px);}to{opacity:1;transform:none;}}
@keyframes msg-in   {from{opacity:0;transform:translateX(-4px);}to{opacity:1;transform:none;}}
@keyframes num-pop  {0%{transform:scale(.78);opacity:0;}70%{transform:scale(1.08);}100%{transform:scale(1);opacity:1;}}
@keyframes modal-in {from{opacity:0;transform:scale(.95) translateY(14px);}to{opacity:1;transform:none;}}
@keyframes trial-pulse{0%,100%{box-shadow:0 0 0 rgba(239,68,68,0);}50%{box-shadow:0 0 20px rgba(239,68,68,.18);}}
@keyframes amber-glow{0%,100%{box-shadow:0 0 0 rgba(240,165,0,0);}50%{box-shadow:0 0 20px rgba(240,165,0,.14);}}

/* ── Responsive ── */
@media(max-width:680px){
  .metric-row{grid-template-columns:repeat(2,1fr);}
  .mkt-strip{grid-template-columns:repeat(2,1fr);}
  .sig-grid,.sector-grid{grid-template-columns:1fr 1fr;}
  .pcc-prices{grid-template-columns:repeat(3,1fr);}
  .hero-h1{font-size:26px;}
}
@media(max-width:440px){.sig-grid{grid-template-columns:1fr;}}
</style>"""


# ─── Component renderers ──────────────────────────────────────────────────────

def _tier_badge(tier):
    cls = {"free":"tb-free","trial":"tb-trial","starter":"tb-starter",
           "trader":"tb-trader","pro":"tb-pro"}.get(tier,"tb-free")
    lbl = tier.upper()
    return f'<span class="tier-badge {cls}">{lbl}</span>'

def _greeting_emoji(h):
    if h < 12: return "☀️"
    if h < 17: return "⚡"
    return "🌙"

def _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial):
    h = now.hour
    greeting = "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"
    st.markdown(f"""
<div class="greet-wrap">
  <div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:0;">
    <span class="greet-name">{greeting}, {name} {_tier_badge(tier)}</span>
  </div>
  <div class="greet-date">{now.strftime("%A · %d %B %Y · %I:%M %p")} WAT</div>
</div>""", unsafe_allow_html=True)

    if is_trial:
        pct  = round(((14 - trial_days_left) / 14) * 100)
        bc   = "tb-urgent" if trial_urgent else "tb-ok"
        tcol = "var(--red)" if trial_urgent else "var(--green)"
        icon = "⚠️" if trial_urgent else "✨"
        msg  = (f"{icon} Trial expires in {trial_days_left} day{'s' if trial_days_left!=1 else ''} — upgrade to keep access"
                if trial_urgent else
                f"{icon} Premium trial active — {trial_days_left} days remaining · Day {trial_day_num} of 14")
        st.markdown(f"""
<div class="trial-banner {bc}">
  <span style="color:{tcol};font-weight:600;">{msg}</span>
  <span style="color:var(--t3);">Upgrade in Settings ↗</span>
</div>
<div class="trial-prog">
  <div style="display:flex;justify-content:space-between;font-family:var(--fm);font-size:10px;color:var(--t3);margin-bottom:4px;">
    <span>Trial progress</span>
    <span style="color:{tcol};">Day {trial_day_num} / 14</span>
  </div>
  <div class="prog-track"><div class="prog-fill" style="width:{pct}%;background:{tcol};"></div></div>
</div>""", unsafe_allow_html=True)


def _render_personalized_strip(tier, name, uniq, profile):
    if tier == "visitor": return
    last_ticker = st.session_state.get("last_ticker_asked","")
    td = next((p for p in uniq if p.get("symbol","").upper() == last_ticker.upper()), None) if last_ticker else None
    chg = float(td.get("change_percent",0)) if td else None
    chg_str  = (f"+{chg:.2f}% ▲" if chg >= 0 else f"{chg:.2f}% ▼") if chg is not None else None
    chg_col  = "var(--green)" if (chg is not None and chg >= 0) else "var(--red)"
    used     = get_ai_query_count()
    limit    = get_usage_limit(tier)
    rem      = max(0, limit - used) if limit is not None else None
    streak   = get_streak()

    if last_ticker and chg_str:
        txt = f'<strong style="color:var(--amber);">{last_ticker}</strong>: <strong style="color:{chg_col};">{chg_str}</strong> today'
    else:
        txt = f'Welcome back, <strong style="color:var(--amber);">{name}</strong>'

    if tier == "free" and rem is not None:
        txt += f' &nbsp;·&nbsp; {rem} of {limit} free queries left'
    if streak >= 2:
        txt += f' &nbsp;·&nbsp; 🔥 {streak}-day streak'

    st.markdown(f'<div class="p-strip"><div class="dot dot-a"></div><span style="flex:1;">{txt}</span></div>',
                unsafe_allow_html=True)


def _render_notification_banner(top_g, notif_minutes, gc, total, market):
    if not top_g: return
    ns  = top_g[0]
    nc  = float(ns.get("change_percent",0))
    nsm = ns.get("symbol","NGX")
    if nc >= 3:
        cls = "notif notif-g"; dot = "dot dot-g"
        txt = f'<strong style="color:var(--green);">{nsm}</strong> is up {nc:.1f}% today — AI flagged this signal early'
    elif nc <= -3:
        cls = "notif notif-r"; dot = "dot dot-r"
        txt = f'<strong style="color:var(--red);">{nsm}</strong> is down {abs(nc):.1f}% — AI sell signal active'
    else:
        cls = "notif"; dot = "dot dot-a"
        txt = f'AI scanning 144 NGX stocks — <strong style="color:var(--amber);">{gc} gainers</strong> identified today'
    st.markdown(f'<div class="{cls}"><div class="{dot}"></div><span style="flex:1;">{txt}</span><span style="font-family:var(--fm);font-size:10px;color:var(--t4);">{_time_ago(notif_minutes)}</span></div>',
                unsafe_allow_html=True)


def _render_market_strip(asi_str, acg, total, gc, lc, mood, market, data_label):
    # colour-coded: up=green, down=red, neutral=amber
    asi_col  = "col-green" if acg >= 0 else "col-red"
    chg_str  = f"+{acg:.2f}% ▲" if acg >= 0 else f"{abs(acg):.2f}% ▼"
    mood_col = "col-green" if mood=="Bullish" else "col-red" if mood=="Bearish" else "col-amber"
    open_dot = '<span class="dot dot-g" style="display:inline-block;margin-right:5px;"></span>' if market["is_open"] else ""
    st.markdown(f"""
<div class="mkt-strip">
  <div class="mkt-cell">
    <div class="mkt-label">NGX All-Share</div>
    <div class="mkt-val {asi_col}">{asi_str}</div>
    <div class="mkt-sub"><span class="{asi_col}">{chg_str}</span> · {data_label}</div>
  </div>
  <div class="mkt-cell">
    <div class="mkt-label">Breadth</div>
    <div class="mkt-val" style="font-size:16px;"><span class="col-green">{gc} ▲</span>&nbsp;<span style="color:rgba(255,255,255,.15);font-size:14px;">/</span>&nbsp;<span class="col-red">{lc} ▼</span></div>
    <div class="mkt-sub">{total - gc - lc} flat · {total} stocks</div>
  </div>
  <div class="mkt-cell">
    <div class="mkt-label">Market mood</div>
    <div class="mkt-val {mood_col}" style="font-size:16px;">{mood}</div>
    <div class="mkt-sub">{"Live breadth" if market["is_open"] else "Last close"}</div>
  </div>
  <div class="mkt-cell">
    <div class="mkt-label">Status</div>
    <div class="mkt-val" style="font-size:14px;font-family:var(--fm);">{open_dot}<span style="color:{market['color']};">{market['label']}</span></div>
    <div class="mkt-sub">{market['note']}</div>
  </div>
</div>""", unsafe_allow_html=True)


def _render_signal_cards(insights, tier, sig_visible):
    """Glassmorphic signal cards — colour-coded, no daily picks duplication"""
    if not insights:
        st.markdown('<div class="gc-sm" style="text-align:center;padding:28px;"><div style="font-family:var(--fm);font-size:12px;color:var(--t3);">Signals refresh at 10 AM WAT each trading day.</div></div>',
                    unsafe_allow_html=True)
        return

    cols_html = ""
    for i, ins in enumerate(insights[:5]):
        action = ins.get("action","HOLD")
        if action == "BUY":
            pill_cls = "pill-green"; ac = "var(--green)"; glow = "glow-green"; badge = "BUY"
        elif action == "AVOID":
            pill_cls = "pill-red";   ac = "var(--red)";   glow = "glow-red";   badge = "AVOID"
        else:
            pill_cls = "pill-amber"; ac = "var(--amber)"; glow = "glow-amber"; badge = "HOLD"

        locked = i >= sig_visible
        lock_html = ('<div class="sc-lock"><div class="sc-lock-icon">🔒</div>'
                     '<div class="sc-lock-text">Upgrade to unlock</div></div>') if locked else ""

        # Entry / target (shown when user can access)
        price_html = ""
        if not locked and can_access("daily_picks_entry", tier):
            p = ins.get("price",0) or 0
            tgt = round(p * 1.076, 2) if p > 0 else 0
            sl  = round(p * 0.940, 2) if p > 0 else 0
            if p > 0:
                price_html = f"""
<div class="sc-price-row"><span class="sc-pl">Entry</span><span class="sc-pv">{_fmt(p)}</span></div>
<div class="sc-price-row"><span class="sc-pl">Target</span><span class="sc-pv col-green">{_fmt(tgt)}</span></div>
{f'<div class="sc-price-row"><span class="sc-pl">Stop-loss</span><span class="sc-pv col-red">{_fmt(sl)}</span></div>' if can_access("stop_loss_visible", tier) else ""}"""

        cols_html += f"""
<div class="sig-card {glow}">
  <div class="sc-head">
    <div class="sc-sym">{ins["sym"]}</div>
    <span class="pill {pill_cls}">{badge}</span>
  </div>
  <div class="sc-name">{ins.get("name","")}</div>
  {price_html}
  <div class="sc-divider"></div>
  <div class="sc-reason">{ins.get("reason","")}</div>
  {lock_html}
</div>"""

    st.markdown(f'<div class="sig-grid">{cols_html}</div>', unsafe_allow_html=True)


def _render_ai_chat(tier, name, uniq, pai, market, latest_date):
    """AI chat — compact, chip-based, with tier-appropriate prompts"""
    has_full = can_access("ai_full_response", tier)
    limit    = get_usage_limit(tier)
    used     = get_ai_query_count()
    at_limit = (limit is not None and limit > 0 and used >= limit)
    can_inp  = can_access("ai_input", tier)

    if "mai_history" not in st.session_state:
        st.session_state.mai_history = []

    st.markdown(f"""
<div class="sh">
  <span class="sh-title">🤖 Ask the market AI</span>
  <span class="sh-action">{"Unlimited" if limit is None else f"{max(0,(limit or 0)-used)}/{limit} left today"}</span>
</div>""", unsafe_allow_html=True)

    # Chat history
    for msg in st.session_state.mai_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="ai-msg-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            body = msg.get("content","")
            blur = "ai-blurred" if msg.get("blurred") else ""
            preview = (body[:200]+"…") if (msg.get("blurred") and len(body)>200) else body
            st.markdown(f'<div class="ai-msg-ai {blur}">{preview}</div>', unsafe_allow_html=True)
            if msg.get("blurred"):
                st.markdown('<div style="text-align:center;margin:-4px 0 8px;"><span class="pill pill-amber">🔒 Full response on trial &amp; above</span></div>',
                            unsafe_allow_html=True)

    # Input area
    if not can_inp:
        st.markdown('<div class="gc-sm"><div style="font-family:var(--fm);font-size:11px;color:var(--t3);">Sign up free for 2 daily AI queries →</div></div>',
                    unsafe_allow_html=True)
    elif at_limit:
        st.markdown(f'<div class="gc-sm"><div style="font-family:var(--fm);font-size:11px;color:var(--t3);">Daily limit reached ({limit} queries). Upgrade for unlimited. →</div></div>',
                    unsafe_allow_html=True)
    else:
        question = st.text_input("",
            placeholder="Ask anything — e.g. 'Should I buy GTCO?' or 'Market summary today'",
            key="mai_input", label_visibility="collapsed")

        chips = ["Best buy today?","Market summary","ZENITHBANK analysis",
                 "DANGCEM signal","Top movers now"]
        chip_cols = st.columns(len(chips))
        chip_sel = None
        for ci, (col, chip) in enumerate(zip(chip_cols, chips)):
            with col:
                if st.button(chip, key=f"chip_{ci}", use_container_width=True):
                    chip_sel = chip

        col1, col2, col3 = st.columns([2,1,1])
        with col1:
            ask_btn = st.button("Ask →", key="mai_ask", type="primary", use_container_width=True)
        with col3:
            if st.session_state.mai_history:
                if st.button("Clear", key="mai_clear", use_container_width=True):
                    st.session_state.mai_history = []
                    st.rerun()

        active_q = chip_sel or (question.strip() if ask_btn and question.strip() else None)
        if active_q:
            st.session_state.mai_history.append({"role":"user","content":active_q})
            with st.spinner("Analysing…"):
                prompt, max_tok = _build_ai_prompt(
                    tier, pai["ad"], pai["aarr"], pai["acg"], pai["mood"],
                    pai["gc"], pai["lc"], pai["total"], pai["top_g_text"],
                    latest_date, market["is_open"], active_q,
                    global_context=pai.get("global_context",""),
                )
                answer = call_ai((prompt, max_tok))
            if answer:
                increment_ai_query_count(); update_streak()
                st.session_state.mai_history.append({
                    "role":"assistant","content":answer,
                    "blurred": not has_full,
                })
                st.rerun()
            else:
                if st.session_state.mai_history and st.session_state.mai_history[-1]["role"] == "user":
                    st.session_state.mai_history.pop()


def _render_top_movers(movers, latest_date, market):
    if not movers: return
    rows = ""
    for s in movers:
        chg = float(s.get("change_percent",0) or 0)
        cc  = "col-green" if chg >= 0 else "col-red"
        arr = "▲" if chg >= 0 else "▼"
        rows += f"""
<div class="mover-row">
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="mover-sym">{s["symbol"]}</span>
    <span class="mover-price">{_fmt(float(s.get("price",0) or 0))}</span>
  </div>
  <span class="mover-chg {cc}">{arr} {abs(chg):.2f}%</span>
</div>"""
    st.markdown(f"""
<div class="gc">
  <div class="sh" style="margin-top:0;">
    <span class="sh-title">🔥 Top movers</span>
    <span class="sh-action">{"📈 Live" if market["is_open"] else "🔒 Last close"} · {latest_date}</span>
  </div>
  {rows}
</div>""", unsafe_allow_html=True)
    if st.button("📊 View all 144 stocks →", key="btn_all", type="primary"):
        st.session_state.current_page = "all_stocks"; st.rerun()


def _render_brief_section(tier, brief_res):
    with st.expander("✨  TODAY'S AI MARKET BRIEF", expanded=False):
        if not brief_res:
            st.markdown('<div style="font-family:var(--fm);font-size:12px;color:var(--t3);">Brief generates daily at 9 AM WAT before market open.</div>',
                        unsafe_allow_html=True)
            return
        raw = brief_res[0].get("body","")
        if can_access("brief_full", tier):
            st.markdown(f'<div class="brief-body">{raw}</div>', unsafe_allow_html=True)
        else:
            prev = raw[:280]+"…" if len(raw)>280 else raw
            st.markdown(f'<div class="brief-body" style="filter:blur(3px);user-select:none;">{prev}</div>',
                        unsafe_allow_html=True)
            st.markdown('<div style="text-align:center;margin-top:8px;"><span class="pill pill-amber">🔒 Full brief on trial &amp; above</span></div>',
                        unsafe_allow_html=True)


def _render_sector_snapshot(tier):
    with st.expander("🚦  SECTOR SNAPSHOT", expanded=False):
        secs = _load_sectors()
        if not secs: st.info("No sector data."); return
        seen = {}
        for s in secs:
            sn = s.get("sector_name","").strip()
            if sn and sn not in seen: seen[sn] = s
        all_s   = sorted(seen.values(), key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)
        vis     = len(all_s) if can_access("sector_all",tier) else 3
        rows_html = ""
        for i, s in enumerate(all_s):
            em  = "🟢" if s.get("traffic_light")=="green" else "🔴" if s.get("traffic_light")=="red" else "🟡"
            chg = float(s.get("change_percent",0) or 0)
            cc  = "col-green" if chg >= 0 else "col-red"
            blr = "style='filter:blur(4px);user-select:none;'" if i >= vis else ""
            rows_html += f'<div class="sector-card" {blr}><div class="sector-name">{em} {s["sector_name"]}</div><div class="sector-chg {cc}">{chg:+.2f}%</div><div class="sector-verdict">{s.get("verdict","")}</div></div>'
        st.markdown(f'<div class="sector-grid">{rows_html}</div>', unsafe_allow_html=True)
        if not can_access("sector_all", tier):
            st.markdown('<div style="text-align:center;margin-top:8px;"><span class="pill pill-ghost">🔒 All sectors on trial &amp; above</span></div>',
                        unsafe_allow_html=True)


def _render_news_section(tier):
    with st.expander("📰  LATEST MARKET NEWS", expanded=False):
        news = _load_news()
        if not news: st.info("No news yet."); return
        vis = 12 if can_access("news_full",tier) else 4
        seen_h = set(); cnt = 0; rows = ""
        for art in news:
            hk = (art.get("headline") or "")[:60].lower()
            if hk in seen_h or cnt >= 12: continue
            seen_h.add(hk); cnt += 1
            sent = art.get("sentiment","neutral")
            dot  = "🟢" if sent=="positive" else "🔴" if sent=="negative" else "🟡"
            blr  = "style='filter:blur(4px);user-select:none;'" if cnt > vis else ""
            rows += f'<div class="news-item" {blr}><div class="news-hl">{art.get("headline","")}</div><div class="news-meta">{dot} {sent.capitalize()}</div></div>'
        st.markdown(f'<div>{rows}</div>', unsafe_allow_html=True)
        if not can_access("news_full",tier):
            st.markdown('<div style="text-align:center;margin-top:6px;"><span class="pill pill-ghost">🔒 Full feed on trial &amp; above</span></div>',
                        unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1:
            if st.button("📅 Events →",key="btn_cal1",use_container_width=True):
                st.session_state.current_page="calendar";st.rerun()
        with c2:
            if st.button("📊 Full calendar →",key="btn_cal2",type="primary",use_container_width=True):
                st.session_state.current_page="calendar";st.rerun()


def _render_downgrade_modal(name, stats):
    ai_u  = max(stats.get("total_ai_queries",0), 8)
    sv    = max(stats.get("signals_viewed",0), 6)
    sa    = max(stats.get("stocks_analyzed",0), 4)
    st.markdown(f"""
<div class="dg-overlay">
  <div class="dg-card">
    <div style="font-size:36px;text-align:center;margin-bottom:12px;">📉</div>
    <div class="dg-title">Your premium trial has ended</div>
    <div class="dg-sub">{name}, you've lost access to the tools that gave you your NGX edge.</div>
    <div style="font-family:var(--fm);font-size:9px;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;text-align:center;">During your 14-day trial:</div>
    <div class="dg-stats">
      <div class="dg-stat"><div class="dg-stat-num">{ai_u}</div><div class="dg-stat-lbl">AI queries</div></div>
      <div class="dg-stat"><div class="dg-stat-num">{sv}</div><div class="dg-stat-lbl">Signals viewed</div></div>
      <div class="dg-stat"><div class="dg-stat-num">{sa}</div><div class="dg-stat-lbl">Stocks analysed</div></div>
    </div>
    <div class="dg-lost">
      <div class="dg-lost-title">You've lost access to:</div>
      <div class="dg-lost-item"><span style="color:var(--red);">✕</span> Full AI market analysis &amp; recommendations</div>
      <div class="dg-lost-item"><span style="color:var(--red);">✕</span> Daily AI signal scores for all 144 NGX stocks</div>
      <div class="dg-lost-item"><span style="color:var(--red);">✕</span> Entry price, target &amp; stop-loss per signal</div>
      <div class="dg-lost-item"><span style="color:var(--red);">✕</span> Telegram alerts &amp; morning market brief</div>
    </div>
    <div style="font-family:var(--fh);font-size:15px;font-weight:800;color:var(--t1);text-align:center;margin-bottom:16px;">Don't lose your edge in the market.</div>
  </div>
</div>""", unsafe_allow_html=True)
    _, bc, _ = st.columns([1,2,1])
    with bc:
        if st.button("🚀 Restore full access →", key="dg_upg", type="primary", use_container_width=True):
            st.session_state.deep_link_plan = True
            st.session_state.current_page   = "settings"
            st.rerun()


def _render_upgrade_cta(tier, profile, cta_label, cta_page):
    if tier not in ("free","trial","starter","trader"): return
    if tier == "free":
        title  = "Unlock the full NGX Signal edge"
        sub    = "You're seeing a signal preview. Trial gives you all 144 signals, entry prices, stop-losses, and unlimited AI — free for 14 days."
        feats  = ["All 144 signal scores","Entry + target + stop-loss","Unlimited AI queries","No credit card needed"]
    elif tier == "trial":
        dl    = get_trial_days_left(profile)
        title  = f"{'⚠️ ' if dl <= 3 else ''}Keep your premium access"
        sub    = f"Trial ends in {dl} day{'s' if dl!=1 else ''}. Upgrade to keep all signals, AI, and alerts."
        feats  = ["Uninterrupted signal access","Streak keeps running","All picks &amp; alerts",f"From ₦3,500/mo"]
    elif tier == "starter":
        title  = "Upgrade to Trader"
        sub    = "Unlock unlimited AI queries, stop-loss per signal, Pidgin mode AI brief, and Telegram alerts."
        feats  = ["Unlimited AI queries","Stop-loss per signal","Pidgin mode brief","Telegram alerts"]
    else:
        title  = "Upgrade to Pro"
        sub    = "PDF intelligence reports, portfolio-level AI strategy, and advanced position sizing."
        feats  = ["PDF intelligence reports","Portfolio AI strategy","Position sizing","Priority alerts"]
    feats_html = "".join(f'<span class="upg-feat">✔ {f}</span>' for f in feats)
    st.markdown(f"""
<div class="upg-card">
  <div class="upg-title">{title}</div>
  <div class="upg-sub">{sub}</div>
  <div class="upg-feats">{feats_html}</div>
</div>""", unsafe_allow_html=True)
    _, cc, _ = st.columns([1,3,1])
    with cc:
        if st.button(cta_label, key="upg_main", type="primary", use_container_width=True):
            _unlock_cta("upg_main", tier, cta_page)


def _render_game_card(sb, current_user):
    st.markdown('<div class="game-card"><div class="game-icon">🎮</div><div><div class="game-title">NGX Trade Game</div><div class="game-sub">Practice with virtual cash before risking real money. Test your picks against live NGX prices.</div></div></div>',
                unsafe_allow_html=True)
    if st.button("▶ Open Trade Game →", key="btn_game"):
        st.session_state.current_page = "trade_game"; st.rerun()


def _render_pro_command_center(tier, is_trader, is_pro, uniq, now, sig_map, _gp):
    if not (is_trader or is_pro): return
    sigs = _load_signals()
    top  = [s for s in sigs if (s.get("signal","").upper() in ("STRONG_BUY","BUY"))][:1]
    if not top:
        st.markdown('<div class="pcc"><div class="pcc-glow-bar"></div><div class="pcc-body" style="text-align:center;padding:28px;"><div style="font-family:var(--fm);font-size:12px;color:var(--t3);">Command Center refreshes at 10 AM WAT each trading day.</div></div></div>',
                    unsafe_allow_html=True)
        return
    s      = top[0]
    sym    = s.get("symbol","")
    stars  = min(int(s.get("stars",3) or 3), 5)
    reason = (s.get("reasoning") or "Signal based on price momentum and volume analysis.")
    pd_    = next((p for p in uniq if p.get("symbol","") == sym), {})
    price  = float(pd_.get("price",0) or 0)
    chg    = float(pd_.get("change_percent",0) or 0)
    entry  = round(price*0.996, 2) if price>0 else 0
    target = round(price*1.080, 2) if price>0 else 0
    sloss  = round(price*0.940, 2) if price>0 else 0
    upside = round((target-price)/price*100,1) if price>0 else 0
    conf_base = 72 + (int(hashlib.md5(sym.encode()).hexdigest(),16) % 18)
    conf   = min(conf_base, 95)
    sd     = sig_map.get(sym, {})
    mom    = int(sd.get("momentum_score",0) or 0)
    vol    = int(sd.get("volume_score",0)   or 0)
    conf_lbl = "Very High" if conf>=85 else "High" if conf>=70 else "Moderate"
    sc     = "var(--green)" if conf>=70 else "var(--amber)"
    filled = round(conf/10)
    _fc    = "#22C55E"; _ec = "rgba(255,255,255,.07)"
    bars   = "".join(
        f'<div class="pcc-bar-block" style="background:{_fc if i<filled else _ec};"></div>'
        for i in range(10)
    )
    ctx = ""
    try: ctx = (_gp or {}).get("impacts",{}).get("summary","")
    except: pass
    chg_col = "var(--green)" if chg>=0 else "var(--red)"
    chg_str = f"+{chg:.2f}% ▲" if chg>=0 else f"{chg:.2f}% ▼"
    stars_s = "⭐"*stars
    st.markdown(f"""
<div class="pcc">
  <div class="pcc-glow-bar"></div>
  <div class="pcc-head">
    <div class="pcc-head-left">
      <div class="dot dot-a"></div>
      <span class="pcc-head-title">Command Center</span>
      <span class="pill {'pill-amber' if is_pro else 'pill-purple'}">{"PRO" if is_pro else "TRADER"}</span>
    </div>
    <span style="font-family:var(--fm);font-size:10px;color:var(--t3);">{now.strftime("%I:%M %p")} WAT</span>
  </div>
  <div class="pcc-body">
    <div class="pcc-hero">
      <div>
        <div class="pcc-sym">{sym} <span style="font-size:14px;">{stars_s}</span></div>
        <div class="pcc-co">STRONG BUY &nbsp;·&nbsp; <span style="color:{chg_col};">{chg_str}</span> today</div>
      </div>
      <div class="pcc-upside">
        <div class="pcc-upside-lbl">Upside</div>
        <div class="pcc-upside-val col-green">+{upside}%</div>
      </div>
    </div>
    <div class="pcc-prices">
      <div class="pcc-price">
        <div class="pcc-price-lbl">Entry</div>
        <div class="pcc-price-val">{_fmt(entry)}</div>
      </div>
      <div class="pcc-price">
        <div class="pcc-price-lbl">Target</div>
        <div class="pcc-price-val col-green">{_fmt(target)}</div>
      </div>
      <div class="pcc-price">
        <div class="pcc-price-lbl">Stop-loss</div>
        <div class="pcc-price-val col-red">{_fmt(sloss)}</div>
      </div>
    </div>
    <div class="pcc-driver"><span style="font-size:12px;flex-shrink:0;">📊</span>{reason[:130]}</div>
    {"<div class='pcc-driver'><span style='font-size:12px;flex-shrink:0;'>📈</span>Momentum " + str(mom) + "/100 · Volume " + str(vol) + "/100</div>" if mom or vol else ""}
    <div class="pcc-verdict" style="background:var(--green-dim);border:.5px solid var(--green-bd);">
      <div class="pcc-verdict-lbl col-green">AI verdict</div>
      <div class="pcc-verdict-txt">Strong setup based on current momentum. Entry near current price, target at +{upside}% with stop at -6% for risk control.</div>
    </div>
    <div class="pcc-conf-row">
      <span class="pcc-conf-lbl">Signal confidence</span>
      <div><span class="pcc-conf-val" style="color:{sc};">{conf_lbl}</span><span class="pcc-conf-pct">{conf}%</span></div>
    </div>
    <div class="pcc-bar-track">{bars}</div>
    {"<div class='pcc-ctx'><span>🌐</span><span>" + ctx + "</span></div>" if ctx else ""}
  </div>
</div>""", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([3,2,2])
    with c1:
        if st.button("📊 Full analysis →",key="pcc_full",type="primary",use_container_width=True):
            st.session_state.current_page="signals";st.rerun()
    with c2:
        if st.button("📡 Set alert",key="pcc_alert",use_container_width=True):
            st.session_state.current_page="settings";st.rerun()
    if is_pro:
        with c3:
            if st.button("📄 PDF report",key="pcc_pdf",use_container_width=True):
                st.session_state.current_page="signals";st.rerun()


# ─── Main render() ────────────────────────────────────────────────────────────

def render():
    # ── Auth intercept ────────────────────────────────────────────────────────
    if st.session_state.get("show_auth") and not st.session_state.get("user"):
        from app.views import auth as _auth_view
        st.markdown("""
<div style="background:rgba(240,165,0,.06);border:.5px solid rgba(240,165,0,.28);
     border-radius:20px;padding:20px 22px;text-align:center;max-width:520px;margin:16px auto 20px;">
  <div style="font-size:32px;margin-bottom:10px;">🔐</div>
  <div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:800;
       color:#F0A500;margin-bottom:6px;">Sign up free — get 14 days premium</div>
  <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#A09EBB;line-height:1.7;">
    Full AI signals · Entry &amp; target prices · No credit card needed</div>
</div>""", unsafe_allow_html=True)
        _auth_view.render()
        if st.button("← Back to homepage", key="auth_back"):
            st.session_state.show_auth = False; st.rerun()
        return

    # ── Core state ────────────────────────────────────────────────────────────
    now      = now_wat()
    market   = get_market_status()
    today    = now.date()

    user     = st.session_state.get("user")
    profile  = st.session_state.get("profile", {}) or {}
    if not isinstance(profile, dict):
        # Handle Pydantic model
        try:    profile = dict(profile)
        except: profile = {}

    tier      = get_user_tier()

    # ── Safe name extraction — handles Pydantic user model ───────────────────
    raw_name  = profile.get("full_name","") if isinstance(profile, dict) else ""
    if not raw_name:
        email = _safe_email(user)
        raw_name = email.split("@")[0] if email else "trader"
    name = (raw_name.split()[0] if raw_name.split() else "trader").capitalize()

    sb            = _get_sb()
    current_user  = user
    is_visitor    = tier == "visitor"
    is_free       = tier == "free"
    is_trial      = tier == "trial"
    is_starter    = tier == "starter"
    is_trader     = tier == "trader"
    is_pro        = tier == "pro"
    is_paid       = tier in PAID_TIERS
    is_funnel     = tier in ("visitor","free","trial")
    is_dashboard  = not is_funnel
    is_ex_trial   = (not is_paid and not is_trial
                     and (profile.get("had_trial") or was_trial_user(profile)))

    trial_days_left = get_trial_days_left(profile) if is_trial else 0
    trial_day_num   = get_trial_day_number(profile) if is_trial else 0
    trial_urgent    = is_trial and trial_days_left <= 3

    cta_label, cta_page = _dynamic_cta(tier, profile)

    # ── Inject styles ─────────────────────────────────────────────────────────
    st.markdown(_FONTS, unsafe_allow_html=True)
    st.markdown(_CSS,   unsafe_allow_html=True)

    # ── Downgrade modal (fires once after trial end) ──────────────────────────
    if is_ex_trial and not st.session_state.get("dg_modal_dismissed"):
        _render_downgrade_modal(name, {
            "total_ai_queries": get_total_ai_queries(),
            "signals_viewed":   get_eng("signals_viewed"),
            "stocks_analyzed":  get_eng("stocks_analyzed"),
        })
        st.session_state.dg_modal_dismissed = True
        return

    # ── Data ──────────────────────────────────────────────────────────────────
    raw, latest_date = _load_prices()
    seen_s = set(); uniq = []
    for p in raw:
        s = p.get("symbol","")
        if s and s not in seen_s: seen_s.add(s); uniq.append(p)

    total   = len(uniq)
    gainers = sum(1 for p in uniq if float(p.get("change_percent") or 0) > 0)
    losers  = sum(1 for p in uniq if float(p.get("change_percent") or 0) < 0)
    sm      = _load_market_summary()
    asi     = float(sm.get("asi_index",0) or 0)
    acg     = float(sm.get("asi_change_percent",0) or 0)
    gc      = gainers if total > 5 else int(sm.get("gainers_count",0) or 0)
    lc      = losers  if total > 5 else int(sm.get("losers_count",0) or 0)
    mood    = "Bullish" if acg>0.5 else "Bearish" if acg<-0.5 else "Neutral"
    asi_str = f"{asi:,.2f}" if asi > 0 else "—"
    data_label = latest_date if market["is_open"] else f"Last: {latest_date}"
    brief_res  = _load_briefs()
    top_g      = sorted(uniq, key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:8]
    top_g_text = ", ".join(f"{p['symbol']} (+{float(p.get('change_percent',0)):.1f}%)" for p in top_g[:3])
    notif_min  = (now.hour*60 + now.minute) % 137 + 3

    # Global Pulse
    _gp = None
    try: _gp = get_global_pulse()
    except: pass
    _gp_ai_ctx = get_global_pulse_for_ai(_gp) if _gp else ""

    # Signal insights (day-keyed cache)
    ik = f"ins_{_daily_seed()}"
    if ik not in st.session_state.get("mai_insights",{}):
        if "mai_insights" not in st.session_state: st.session_state.mai_insights = {}
        sig_data = _load_signals(); generated = []; seen_i = set()
        for s in sig_data:
            sym2 = s.get("symbol",""); sig2 = (s.get("signal") or "HOLD").upper().replace(" ","_")
            if sym2 in seen_i or not sym2: continue
            seen_i.add(sym2)
            if sig2 in ("STRONG_BUY","BUY"):   act,base = "BUY",72
            elif sig2 == "HOLD":                act,base = "HOLD",55
            elif sig2 in ("CAUTION","AVOID","STRONG_AVOID"): act,base = "AVOID",60
            else: continue
            conf   = min(base+(int(hashlib.md5(sym2.encode()).hexdigest(),16)%20),95)
            reason = (s.get("reasoning") or "Signal based on price momentum.")[:90]
            if len(reason)==90: reason+="…"
            pd_    = next((p for p in uniq if p.get("symbol","")==sym2),{})
            generated.append({"sym":sym2,"action":act,"conf":conf,"reason":reason,
                               "price":float(pd_.get("price",0) or 0),"name":""})
            if len(generated)>=5: break
        st.session_state.mai_insights[ik] = generated
    insights = st.session_state.mai_insights.get(ik,[])

    # Trending signal map
    _sig_map = {}
    for _sr in _load_signals():
        _s = _sr.get("symbol","")
        if _s and _s not in _sig_map: _sig_map[_s] = _sr

    # Signal visibility per tier
    sig_visible = {"free":2,"trial":5,"starter":3,"trader":5,"pro":5}.get(tier,2)

    # AI prompt bundle
    pai = dict(ad=asi_str, aarr="▲" if acg>=0 else "▼", acg=acg, mood=mood,
               gc=gc, lc=lc, total=total, top_g_text=top_g_text,
               latest_date=latest_date, market_open=market["is_open"],
               uniq=uniq, global_context=_gp_ai_ctx)

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW A — VISITOR / FREE / TRIAL  (value-first funnel)
    # ══════════════════════════════════════════════════════════════════════════
    if is_funnel:
        if is_visitor:
            st.markdown(_FONTS, unsafe_allow_html=True)
            st.markdown(f"""
<div class="hero">
  <div class="hero-eye"><div class="dot dot-g"></div>{"Market open" if market["is_open"] else "Market closed"} · 144 stocks tracked live</div>
  <div class="hero-h1">AI-powered buy &amp; sell signals<br>for every <span>NGX stock</span></div>
  <div class="hero-sub">Every trading day our AI scans all 144 NGX stocks and tells you exactly what to do — entry price, target &amp; stop-loss included. In plain English.</div>
  <div class="hero-ctas">
    <button class="btn-pri" onclick="void(0)">Start free — 14-day trial</button>
    <button class="btn-sec" onclick="void(0)">See how it works ↓</button>
  </div>
  <div class="hero-note">No credit card · Cancel anytime · From ₦3,500/mo</div>
</div>
<div class="trust">
  <div class="trust-item"><span class="trust-check">✓</span>CAC registered business</div>
  <div class="trust-sep"></div>
  <div class="trust-item"><span class="trust-check">✓</span>NGX Exchange data</div>
  <div class="trust-sep"></div>
  <div class="trust-item"><span class="trust-check">✓</span>2,400+ active users</div>
  <div class="trust-sep"></div>
  <div class="trust-item"><span class="trust-check">✓</span>Built in Lagos</div>
  <div class="trust-sep"></div>
  <div class="trust-item"><span class="trust-check">✓</span>Not financial advice</div>
</div>""", unsafe_allow_html=True)
        else:
            _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial)
            _render_personalized_strip(tier, name, uniq, profile)

        # Market data strip
        _render_market_strip(asi_str, acg, total, gc, lc, mood, market, data_label)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Global Pulse
        if _gp:
            render_global_pulse_strip(tier, location="home")
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Notification banner
        _render_notification_banner(top_g, notif_min, gc, total, market)

        # ── Glassmorphic metric tiles ─────────────────────────────────────────
        asi_col  = "col-green" if acg>=0 else "col-red"
        chg_disp = f"+{acg:.2f}% ▲" if acg>=0 else f"{abs(acg):.2f}% ▼"
        mood_col = "col-green" if mood=="Bullish" else "col-red" if mood=="Bearish" else "col-amber"
        gcol     = f'<span class="col-green">{gc}</span>'
        lcol     = f'<span class="col-red">{lc}</span>'
        st.markdown(f"""
<div class="metric-row">
  <div class="metric-tile glow-{'green' if acg>=0 else 'red'}">
    <div class="mt-icon">📈</div>
    <div class="mt-label">NGX All-Share</div>
    <div class="mt-value {asi_col}">{asi_str}</div>
    <div class="mt-sub"><span class="{asi_col}">{chg_disp}</span> · {data_label}</div>
  </div>
  <div class="metric-tile">
    <div class="mt-icon">⚖️</div>
    <div class="mt-label">Breadth</div>
    <div class="mt-value" style="font-size:18px;">{gcol} / {lcol}</div>
    <div class="mt-sub">{total-gc-lc} flat · {total} stocks</div>
  </div>
  <div class="metric-tile glow-{'green' if mood=='Bullish' else 'red' if mood=='Bearish' else 'amber'}">
    <div class="mt-icon">🧭</div>
    <div class="mt-label">Market mood</div>
    <div class="mt-value {mood_col}">{mood}</div>
    <div class="mt-sub">{"Live breadth" if market["is_open"] else "Last close"}</div>
  </div>
  <div class="metric-tile">
    <div class="mt-icon">✨</div>
    <div class="mt-label">AI brief</div>
    <div class="mt-value" style="font-size:16px;color:{'var(--amber)' if brief_res else 'var(--t3)'};">{"Ready" if brief_res else "—"}</div>
    <div class="mt-sub">{"Today's brief available" if brief_res else "Generates 9 AM WAT"}</div>
  </div>
</div>""", unsafe_allow_html=True)

        # Signal cards
        st.markdown('<div class="sh"><span class="sh-title">⚡ Today\'s top signals</span><span class="sh-action">Refreshed 10 AM WAT</span></div>',
                    unsafe_allow_html=True)
        _render_signal_cards(insights, tier, sig_visible)
        if not can_access("signals_all", tier):
            st.markdown('<div style="text-align:center;margin:-2px 0 10px;"><span class="pill pill-ghost">🔒 More signals on trial &amp; above</span></div>',
                        unsafe_allow_html=True)

        # AI Brief teaser
        _render_brief_section(tier, brief_res)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # AI Chat
        _render_ai_chat(tier, name, uniq, pai, market, latest_date)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # News + Sectors (collapsed)
        _render_news_section(tier)
        _render_sector_snapshot(tier)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── SINGLE upgrade CTA ────────────────────────────────────────────────
        if not is_visitor:
            _render_upgrade_cta(tier, profile, cta_label, cta_page)
        else:
            st.markdown("""
<div class="upg-card" style="text-align:center;">
  <div class="upg-title">Ready to get your edge?</div>
  <div class="upg-sub">Join 2,400+ NGX traders using AI signals every day.<br>14 days free — no card needed.</div>
</div>""", unsafe_allow_html=True)
            _, cc, _ = st.columns([1,3,1])
            with cc:
                if st.button("🔐 Sign up free — start trial →", key="v_cta", type="primary", use_container_width=True):
                    _unlock_cta("v_cta", tier, "settings")

        # Trade game
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        _render_game_card(sb, current_user)
        st.markdown("<div style='height:48px'></div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # FLOW B — STARTER / TRADER / PRO  (intelligence delivery)
    # ══════════════════════════════════════════════════════════════════════════
    else:
        _render_greeting(tier, name, now, profile, trial_days_left, trial_day_num, trial_urgent, is_trial)
        _render_personalized_strip(tier, name, uniq, profile)

        # Streak badge
        sk = get_streak()
        if sk >= 2 and not st.session_state.get(f"streak_shown_{today}"):
            ms = streak_milestone(sk)
            if ms:
                st.markdown(f'<div class="streak"><span class="streak-num">{sk}</span><div><div style="font-size:12px;font-weight:700;color:var(--amber);">Day streak — {ms}</div><div style="font-size:10px;color:var(--t3);">Building a real market intelligence habit</div></div></div>',
                            unsafe_allow_html=True)
            st.session_state[f"streak_shown_{today}"] = True

        # ── Pro Command Center — FIRST for paid tiers ─────────────────────────
        _render_pro_command_center(tier, is_trader, is_pro, uniq, now, _sig_map, _gp)

        # Market strip
        _render_market_strip(asi_str, acg, total, gc, lc, mood, market, data_label)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Global Pulse
        if _gp:
            render_global_pulse_strip(tier, location="home")
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Notification
        _render_notification_banner(top_g, notif_min, gc, total, market)

        # Glassmorphic metric tiles
        asi_col  = "col-green" if acg>=0 else "col-red"
        chg_disp = f"+{acg:.2f}% ▲" if acg>=0 else f"{abs(acg):.2f}% ▼"
        mood_col = "col-green" if mood=="Bullish" else "col-red" if mood=="Bearish" else "col-amber"
        gcol     = f'<span class="col-green">{gc}</span>'
        lcol     = f'<span class="col-red">{lc}</span>'
        st.markdown(f"""
<div class="metric-row">
  <div class="metric-tile glow-{'green' if acg>=0 else 'red'}">
    <div class="mt-icon">📈</div>
    <div class="mt-label">NGX All-Share</div>
    <div class="mt-value {asi_col}">{asi_str}</div>
    <div class="mt-sub"><span class="{asi_col}">{chg_disp}</span> · {data_label}</div>
  </div>
  <div class="metric-tile">
    <div class="mt-icon">⚖️</div>
    <div class="mt-label">Breadth</div>
    <div class="mt-value" style="font-size:18px;">{gcol} / {lcol}</div>
    <div class="mt-sub">{total-gc-lc} flat · {total} stocks</div>
  </div>
  <div class="metric-tile glow-{'green' if mood=='Bullish' else 'red' if mood=='Bearish' else 'amber'}">
    <div class="mt-icon">🧭</div>
    <div class="mt-label">Market mood</div>
    <div class="mt-value {mood_col}">{mood}</div>
    <div class="mt-sub">{"Live breadth" if market["is_open"] else "Last close"}</div>
  </div>
  <div class="metric-tile">
    <div class="mt-icon">✨</div>
    <div class="mt-label">AI brief</div>
    <div class="mt-value" style="font-size:16px;color:{'var(--amber)' if brief_res else 'var(--t3)'};">{"Ready" if brief_res else "—"}</div>
    <div class="mt-sub">{"Today's brief available" if brief_res else "Generates 9 AM WAT"}</div>
  </div>
</div>""", unsafe_allow_html=True)

        # AI brief (expanded for paid)
        with st.expander("✨  TODAY'S AI MARKET BRIEF", expanded=(tier in ("trader","pro"))):
            _render_brief_section(tier, brief_res)

        # Signal cards
        st.markdown('<div class="sh"><span class="sh-title">⚡ Today\'s AI signals</span><span class="sh-action">All 144 NGX stocks</span></div>',
                    unsafe_allow_html=True)
        _render_signal_cards(insights, tier, sig_visible)
        if st.button("📊 View all signals →", key="btn_all_sigs", type="primary"):
            st.session_state.current_page = "signals"; st.rerun()

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # AI Chat
        _render_ai_chat(tier, name, uniq, pai, market, latest_date)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Top Movers
        sup   = sorted([p for p in uniq if float(p.get("change_percent") or 0)>0],
                       key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:6]
        sdn   = sorted([p for p in uniq if float(p.get("change_percent") or 0)<0],
                       key=lambda x:float(x.get("change_percent",0) or 0))[:3]
        _render_top_movers(sup+sdn, latest_date, market)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Collapsed sections
        _render_news_section(tier)
        _render_sector_snapshot(tier)

        # Trade game
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _render_game_card(sb, current_user)

        # Single subtle nudge for sub-pro paid tiers
        if not is_pro and cta_label:
            st.markdown(f"""
<div class="bot-nudge">
  <div class="bot-nudge-txt">
    <strong>{tier.capitalize()} plan</strong> &nbsp;·&nbsp;
    {"Upgrade to Trader for unlimited AI, stop-loss signals &amp; Telegram alerts." if is_starter
     else "Upgrade to Pro for PDF reports, portfolio AI &amp; advanced outputs."}
  </div>
</div>""", unsafe_allow_html=True)
            if st.button(cta_label, key="dash_nudge", type="primary"):
                _unlock_cta("dash_nudge", tier, cta_page)

        st.markdown("<div style='height:48px'></div>", unsafe_allow_html=True)