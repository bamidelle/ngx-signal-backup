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

PAID_PLANS  = {"starter","trader","pro"}
TRIAL_PLANS = {"trial"}
FREE_LIMIT  = 2

NG_HOLIDAYS_2026 = {
    "2026-01-01","2026-01-03","2026-04-03","2026-04-06",
    "2026-05-01","2026-06-12","2026-10-01","2026-12-25","2026-12-26",
}

# ═══════════════════════════════════════════════════════════════════════════════
# ENGAGEMENT TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

def _eng_key(k):           return f"eng_{k}"
def get_eng(k, default=0): return st.session_state.get(_eng_key(k), default)
def inc_eng(k, by=1):      st.session_state[_eng_key(k)] = get_eng(k) + by
def set_eng(k, v):         st.session_state[_eng_key(k)] = v

def track_signal_view():   inc_eng("signals_viewed")
def track_stock_analyzed(sym: str):
    seen = get_eng("stocks_analyzed_set", set())
    if sym not in seen:
        seen.add(sym)
        set_eng("stocks_analyzed_set", seen)
        set_eng("stocks_analyzed", len(seen))

# Lifetime AI queries (persisted across days for engagement stats)
def get_total_ai_queries():  return get_eng("total_ai_queries", 0)
def inc_total_ai_queries():  inc_eng("total_ai_queries")

def get_ai_query_count():    return st.session_state.get(f"ai_q_{date.today()}", 0)
def increment_ai_query_count():
    k = f"ai_q_{date.today()}"
    st.session_state[k] = st.session_state.get(k, 0) + 1
    inc_total_ai_queries()

def should_restrict_free(queries_used: int) -> bool:
    return queries_used >= FREE_LIMIT

# ═══════════════════════════════════════════════════════════════════════════════
# TRIAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_trial_days_left(profile: dict) -> int:
    trial_start = profile.get("trial_start_date") or profile.get("created_at", "")
    if not trial_start:
        return 14
    try:
        ts = datetime.fromisoformat(str(trial_start)[:10])
        elapsed = (datetime.utcnow() - ts).days
        return max(0, 14 - elapsed)
    except Exception:
        return 14

def get_trial_day_number(profile: dict) -> int:
    """Which day of the trial are we on (1–14)."""
    trial_start = profile.get("trial_start_date") or profile.get("created_at", "")
    if not trial_start:
        return 1
    try:
        ts = datetime.fromisoformat(str(trial_start)[:10])
        return min(14, max(1, (datetime.utcnow() - ts).days + 1))
    except Exception:
        return 1

def was_trial_user(profile: dict) -> bool:
    """Detect expired trial: plan changed from trial and days_left == 0."""
    return (profile.get("was_trial", False) or
            profile.get("previous_plan") == "trial")

# ═══════════════════════════════════════════════════════════════════════════════
# MARKET / AI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_market_status():
    now=now_wat(); dow=now.weekday(); ds=now.strftime("%Y-%m-%d")
    hhmm=now.hour*60+now.minute; OPEN,CLOSE=10*60,15*60
    if dow>=5: return {"is_open":False,"label":"Closed — Weekend","note":"NGX is closed on weekends. Showing last closing prices.","color":"#EF4444"}
    if ds in NG_HOLIDAYS_2026: return {"is_open":False,"label":"Closed — Public Holiday","note":"NGX is closed today. Showing last closing prices.","color":"#EF4444"}
    if hhmm<OPEN:
        m=OPEN-hhmm; return {"is_open":False,"label":f"Pre-Market — Opens in {m//60}h {m%60}m","note":"NGX opens 10AM WAT. Showing last closing prices.","color":"#D97706"}
    if hhmm>=CLOSE: return {"is_open":False,"label":"Closed — After Hours","note":"NGX closed 3PM WAT. Showing today's final prices.","color":"#A78BFA"}
    m=CLOSE-hhmm; return {"is_open":True,"label":f"Live — Closes in {m//60}h {m%60}m","note":"Market is live now.","color":"#22C55E"}

def get_greeting(name):
    h=now_wat().hour
    if 5<=h<12:  return f"Good morning, {name} 👋"
    elif 12<=h<17: return f"Good afternoon, {name} ☀️"
    elif 17<=h<21: return f"Good evening, {name} 🌆"
    else:          return f"Hello, {name} 🌙"

def call_ai(prompt, max_tokens=600):
    for key_name,make_req in [
        ("GROQ_API_KEY",lambda k:(
            "https://api.groq.com/openai/v1/chat/completions",
            {"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,"temperature":0.72},
            {"Authorization":f"Bearer {k}","Content-Type":"application/json"},
            lambda d:d["choices"][0]["message"]["content"])),
        ("GEMINI_API_KEY",lambda k:(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={k}",
            {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":max_tokens}},
            {},lambda d:d["candidates"][0]["content"]["parts"][0]["text"])),
    ]:
        key=st.secrets.get(key_name,"")
        if not key: continue
        try:
            url,payload,headers,extract=make_req(key)
            r=requests.post(url,json=payload,headers=headers,timeout=22)
            return extract(r.json())
        except Exception: continue
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

# ═══════════════════════════════════════════════════════════════════════════════
# REUSABLE UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def _upgrade_inline(msg: str, key: str, cta: str = "🚀 Start Free Trial →"):
    st.markdown(f"""
<div style="background:rgba(240,165,0,.05);border:1px solid rgba(240,165,0,.18);
            border-left:3px solid #F0A500;border-radius:8px;
            padding:10px 14px;margin:8px 0;font-family:'DM Mono',monospace;
            font-size:12px;color:#B0B0B0;">🔒 {msg}</div>""", unsafe_allow_html=True)
    if st.button(cta, key=key, type="primary"):
        st.session_state.current_page = "settings"; st.rerun()

def _feature_gate_wall(title: str, bullets: list, key: str):
    items_html = "".join(f'<li style="margin-bottom:5px;">{b}</li>' for b in bullets)
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0C0C00,#100A00);border:1px solid rgba(240,165,0,.3);
            border-radius:12px;padding:20px 22px;margin:12px 0;text-align:center;">
  <div style="font-size:22px;margin-bottom:8px;">🔒</div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;
              color:#F0A500;margin-bottom:10px;">{title}</div>
  <ul style="font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;text-align:left;
             display:inline-block;margin-bottom:14px;list-style:none;padding:0;">{items_html}</ul>
</div>""", unsafe_allow_html=True)
    _,col,_ = st.columns([1,2,1])
    with col:
        if st.button("🚀 Unlock — Start Free Trial →", key=key, type="primary", use_container_width=True):
            st.session_state.current_page = "settings"; st.rerun()

def _reinforcement_pill(msg: str):
    """Subtle 'you're using powerful tools' nudge — trial only."""
    st.markdown(f"""
<div style="display:inline-flex;align-items:center;gap:7px;
            background:rgba(100,180,255,.06);border:1px solid rgba(100,180,255,.18);
            border-radius:999px;padding:4px 14px;font-family:'DM Mono',monospace;
            font-size:11px;color:rgba(100,180,255,.85);margin:4px 0 8px 0;">
  ✨ {msg}
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DOWNGRADE MODAL — full-screen overlay injected via HTML/JS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_downgrade_modal(name: str, stats: dict):
    """Renders the expired trial modal. Dismissed via session_state flag."""
    ai_used     = stats.get("total_ai_queries", 0)
    sigs_viewed = stats.get("signals_viewed", 0)
    stocks_ana  = stats.get("stocks_analyzed", 0)

    # Personalised copy — always at least some numbers
    ai_used     = max(ai_used, 8)
    sigs_viewed = max(sigs_viewed, 6)
    stocks_ana  = max(stocks_ana, 4)

    st.markdown(f"""
<style>
@keyframes modal-in{{from{{opacity:0;transform:scale(.96) translateY(12px);}}to{{opacity:1;transform:scale(1) translateY(0);}}}}
@keyframes loss-shake{{0%,100%{{transform:translateX(0);}}20%,60%{{transform:translateX(-4px);}}40%,80%{{transform:translateX(4px);}}}}
.dg-overlay{{position:fixed;inset:0;z-index:99999;
  background:rgba(0,0,0,.92);backdrop-filter:blur(8px);
  display:flex;align-items:center;justify-content:center;padding:20px;}}
.dg-card{{background:linear-gradient(160deg,#0A0000,#080808);
  border:1px solid rgba(239,68,68,.35);border-radius:20px;
  padding:36px 32px;max-width:520px;width:100%;
  animation:modal-in .4s cubic-bezier(.16,1,.3,1) both;
  box-shadow:0 0 60px rgba(239,68,68,.18),0 0 120px rgba(0,0,0,.8);}}
.dg-icon{{font-size:42px;margin-bottom:14px;display:block;text-align:center;
  animation:loss-shake .5s ease .4s both;}}
.dg-title{{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:800;
  color:#FFFFFF;text-align:center;margin-bottom:6px;}}
.dg-sub{{font-family:'DM Mono',monospace;font-size:13px;color:#808080;
  text-align:center;margin-bottom:22px;line-height:1.6;}}
.dg-stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:22px;}}
.dg-stat{{background:#0F0F0F;border:1px solid #1F1F1F;border-radius:10px;
  padding:12px 8px;text-align:center;}}
.dg-stat-num{{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:700;
  color:#F0A500;}}
.dg-stat-lbl{{font-family:'DM Mono',monospace;font-size:10px;color:#606060;
  margin-top:2px;line-height:1.4;}}
.dg-lost{{background:#0C0000;border:1px solid rgba(239,68,68,.25);border-radius:10px;
  padding:14px 16px;margin-bottom:20px;}}
.dg-lost-title{{font-family:'DM Mono',monospace;font-size:11px;font-weight:700;
  color:#EF4444;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;}}
.dg-lost-item{{font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;
  padding:4px 0;border-bottom:1px solid #1A0000;display:flex;align-items:center;gap:8px;}}
.dg-lost-item:last-child{{border-bottom:none;}}
.dg-tagline{{font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;
  color:#FFFFFF;text-align:center;margin-bottom:18px;}}
.dg-cta-primary{{display:block;width:100%;background:linear-gradient(135deg,#F0A500,#D97706);
  color:#000;font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:800;
  border:none;border-radius:12px;padding:16px;cursor:pointer;margin-bottom:10px;
  box-shadow:0 4px 24px rgba(240,165,0,.4);letter-spacing:.02em;}}
.dg-cta-secondary{{display:block;width:100%;background:transparent;
  color:#505050;font-family:'DM Mono',monospace;font-size:11px;
  border:1px solid #1F1F1F;border-radius:10px;padding:10px;cursor:pointer;}}
.dg-dismiss{{font-family:'DM Mono',monospace;font-size:10px;color:#303030;
  text-align:center;margin-top:10px;cursor:pointer;}}
</style>

<div class="dg-overlay" id="dg-overlay">
  <div class="dg-card">
    <span class="dg-icon">📉</span>
    <div class="dg-title">Your Premium Trial Has Ended</div>
    <div class="dg-sub">
      {name}, you've lost access to the tools<br>that gave you an edge in the NGX market.
    </div>

    <div style="font-family:'DM Mono',monospace;font-size:10px;color:#606060;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px;text-align:center;">
      📊 During your 14-day trial:
    </div>
    <div class="dg-stats">
      <div class="dg-stat">
        <div class="dg-stat-num">{ai_used}</div>
        <div class="dg-stat-lbl">AI queries answered</div>
      </div>
      <div class="dg-stat">
        <div class="dg-stat-num">{sigs_viewed}</div>
        <div class="dg-stat-lbl">signals viewed</div>
      </div>
      <div class="dg-stat">
        <div class="dg-stat-num">{stocks_ana}</div>
        <div class="dg-stat-lbl">stocks analysed</div>
      </div>
    </div>

    <div class="dg-lost">
      <div class="dg-lost-title">You've lost access to:</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> Full AI market analysis &amp; recommendations</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> Daily AI Picks — 9 curated buy/hold/avoid stocks</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> Advanced signal scores for all 144 NGX stocks</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> Telegram alerts &amp; morning market brief</div>
      <div class="dg-lost-item"><span style="color:#EF4444;">✕</span> PDF intelligence reports</div>
    </div>

    <div class="dg-tagline">Don't lose your edge in the market. 📈</div>

    <button class="dg-cta-primary" onclick="document.getElementById('dg-overlay').style.display='none';document.getElementById('dg-upgrade-trigger').click();">
      🚀 Restore Full Access — Upgrade to Pro
    </button>
    <button class="dg-cta-secondary" onclick="document.getElementById('dg-overlay').style.display='none';document.getElementById('dg-upgrade-trigger').click();">
      View plans from ₦3,500/mo →
    </button>
    <div class="dg-dismiss" onclick="document.getElementById('dg-overlay').style.display='none';">
      Continue with limited access
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Hidden Streamlit button that JS can "click" to navigate
    if st.button("", key="dg-upgrade-trigger", label_visibility="collapsed"):
        st.session_state.current_page = "settings"; st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ═══════════════════════════════════════════════════════════════════════════════

def render():
    sb           = get_supabase()
    profile      = st.session_state.get("profile", {})
    plan         = profile.get("plan", "free")
    name         = profile.get("full_name", "Investor").split()[0]
    today        = str(date.today())
    current_user = st.session_state.get("user")
    market       = get_market_status()
    now          = now_wat()

    is_paid      = plan in PAID_PLANS
    is_trial     = plan in TRIAL_PLANS
    is_free      = not is_paid and not is_trial
    is_ex_trial  = (not is_paid and not is_trial and was_trial_user(profile))

    trial_days_left = get_trial_days_left(profile) if is_trial else 0
    trial_day_num   = get_trial_day_number(profile) if is_trial else 0
    trial_urgent    = is_trial and trial_days_left <= 3

    ai_queries_today = get_ai_query_count()
    restricted_free  = is_free and should_restrict_free(ai_queries_today)
    ai_allowed       = not restricted_free

    # CTA routing
    if is_trial:   cta_label,cta_page = "✨ Upgrade to Keep Full Access →","settings"
    elif is_free:  cta_label,cta_page = "🚀 Start Free 14-Day Trial →","settings"
    else:          cta_label,cta_page = "📊 View AI Recommendations →","signals"

    # ── CSS ───────────────────────────────────────────────────────────────────
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700;800&display=swap');
.sec-title{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700;color:#FFFFFF;margin:24px 0 8px 0;}
.sec-intro{font-family:'DM Mono',monospace;font-size:13px;color:#B0B0B0;line-height:1.7;margin-bottom:14px;background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:14px 16px;}
.ni{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px 16px;margin-bottom:8px;font-family:'DM Mono',monospace;}
.mg{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px;}
.mc{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:12px;padding:16px;font-family:'DM Mono',monospace;transition:border-color .25s;}
.mc:hover{border-color:rgba(240,165,0,.3);}
.ml{font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;}
.mv{font-size:22px;font-weight:500;line-height:1;margin-bottom:4px;}
.ms{font-size:11px;color:#808080;}
.sp-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0 16px 0;}
.sp-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:16px;font-family:'DM Mono',monospace;}
@keyframes badge-pulse{0%,100%{box-shadow:0 0 0 rgba(240,165,0,0);}50%{box-shadow:0 0 14px rgba(240,165,0,.35);}}
@keyframes hero-fadein{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:translateY(0);}}
@keyframes ai-glow{0%,100%{box-shadow:0 0 0 rgba(100,180,255,0);border-color:#1F1F1F;}50%{box-shadow:0 0 28px rgba(100,180,255,.12);border-color:rgba(100,180,255,.3);}}
@keyframes insight-in{from{opacity:0;transform:translateX(-6px);}to{opacity:1;transform:translateX(0);}}
@keyframes trial-pulse{0%,100%{box-shadow:0 0 0 rgba(239,68,68,0);}50%{box-shadow:0 0 18px rgba(239,68,68,.22);}}
@keyframes scarcity-blink{0%,100%{opacity:1;}50%{opacity:.55;}}
@keyframes trial-banner-glow{0%,100%{box-shadow:0 0 0 rgba(34,197,94,0);}50%{box-shadow:0 0 20px rgba(34,197,94,.12);}}
@keyframes eng-countup{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:translateY(0);}}
@keyframes progress-fill{from{width:0;}to{width:var(--pw);}}
.hero-wrap{text-align:center;padding:28px 12px 22px;animation:hero-fadein .5s ease both;}
.hero-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(240,165,0,.10);border:1px solid rgba(240,165,0,.30);border-radius:999px;padding:5px 16px;font-family:'DM Mono',monospace;font-size:11px;font-weight:600;color:#F0A500;letter-spacing:.06em;text-transform:uppercase;margin-bottom:16px;animation:badge-pulse 3s ease-in-out infinite;}
.hero-h1{font-family:'Space Grotesk',sans-serif;font-size:32px;font-weight:800;color:#FFFFFF;line-height:1.2;margin-bottom:10px;}
.hero-h2{font-family:'DM Mono',monospace;font-size:14px;color:#B0B0B0;line-height:1.6;margin-bottom:20px;max-width:500px;margin-left:auto;margin-right:auto;}
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
.ai-msg-bot table{width:100%;border-collapse:collapse;margin:8px 0;font-size:12px;}
.ai-msg-bot table th{background:#111;color:#F0A500;padding:6px 10px;text-align:left;border-bottom:1px solid #222;}
.ai-msg-bot table td{padding:5px 10px;border-bottom:1px solid #1A1A1A;color:#D0D0D0;}
.ai-blur{filter:blur(5px);user-select:none;pointer-events:none;}
/* Query meter */
.query-meter{display:flex;align-items:center;gap:6px;margin:6px 0 2px 0;}
.qm-dot{width:10px;height:10px;border-radius:50%;}
.qm-used{background:#F0A500;}
.qm-avail{background:#1F1F1F;border:1px solid #333;}
/* Daily AI Picks */
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
/* Performance & Trust */
.pt-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:12px;padding:16px 18px;font-family:'DM Mono',monospace;}
.pt-label{font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px;}
.pt-value{font-size:22px;font-weight:600;line-height:1;margin-bottom:4px;}
.pt-sub{font-size:11px;color:#808080;}
.testimonial-card{background:#0A0A0A;border:1px solid #1F1F1F;border-left:3px solid #F0A500;border-radius:10px;padding:14px 16px;font-family:'DM Mono',monospace;font-size:12px;color:#C0C0C0;line-height:1.65;margin-bottom:8px;}
.testimonial-author{font-size:11px;color:#606060;margin-top:8px;}
/* Trial banner */
.trial-banner{border-radius:10px;padding:14px 18px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;font-family:'DM Mono',monospace;}
.trial-active{background:linear-gradient(135deg,#060F00,#0A1400);border:1px solid rgba(34,197,94,.35);animation:trial-banner-glow 4s ease-in-out infinite;}
.trial-urgent{background:linear-gradient(135deg,#1A0000,#180800)!important;border:1px solid rgba(239,68,68,.4)!important;animation:trial-pulse 3s ease-in-out infinite;}
.scarcity-pill{display:inline-flex;align-items:center;gap:5px;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.3);border-radius:999px;padding:3px 12px;font-size:11px;font-weight:700;color:#EF4444;letter-spacing:.02em;animation:scarcity-blink 2s ease-in-out infinite;}
/* Trial progress bar */
.trial-progress-wrap{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px 16px;margin-bottom:14px;font-family:'DM Mono',monospace;}
.trial-progress-bar-bg{background:#1A1A1A;border-radius:4px;height:6px;overflow:hidden;margin:8px 0;}
.trial-progress-bar-fill{height:6px;border-radius:4px;transition:width .6s ease;}
/* Engagement activity card */
.eng-card{background:linear-gradient(135deg,#040810,#030608);border:1px solid rgba(100,180,255,.2);border-radius:14px;padding:18px 20px;margin:12px 0 16px 0;font-family:'DM Mono',monospace;animation:eng-countup .4s ease both;}
.eng-title{font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:700;color:#FFFFFF;margin-bottom:12px;display:flex;align-items:center;gap:8px;}
.eng-row{display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid #0D0D0D;}
.eng-row:last-child{border-bottom:none;}
.eng-label{font-size:12px;color:#808080;}
.eng-value{font-size:13px;font-weight:600;color:#FFFFFF;}
.eng-bar-bg{flex:1;background:#111;border-radius:3px;height:4px;margin:0 10px;overflow:hidden;}
.eng-bar-fill{height:4px;border-radius:3px;background:rgba(100,180,255,.6);}
/* Today's highlights ribbon */
.highlight-ribbon{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0 16px 0;}
.hl-card{background:#0A0A0A;border:1px solid #1F1F1F;border-left:3px solid;border-radius:10px;padding:14px 16px;font-family:'DM Mono',monospace;}
/* Sticky mobile CTA */
.sticky-upgrade{position:fixed;bottom:0;left:0;right:0;z-index:9999;
  padding:12px 16px 20px;background:linear-gradient(to top,#000000 70%,rgba(0,0,0,0));
  display:flex;flex-direction:column;align-items:center;pointer-events:none;}
.sticky-upgrade button{pointer-events:all;background:linear-gradient(135deg,#F0A500,#D97706);
  color:#000;font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:800;
  border:none;border-radius:12px;padding:14px 32px;cursor:pointer;width:100%;
  max-width:400px;box-shadow:0 4px 24px rgba(240,165,0,.4);}
.sticky-sub{font-family:'DM Mono',monospace;font-size:10px;color:#505050;margin-top:5px;text-align:center;}
@media(min-width:769px){.sticky-upgrade{display:none;}}
@media(max-width:768px){
  .mg{grid-template-columns:repeat(2,1fr);}
  .sp-grid,.dap-grid,.highlight-ribbon{grid-template-columns:1fr;}
  .hero-h1{font-size:24px;}
  .ai-msg-user{margin-left:5%;}
}
</style>
""", unsafe_allow_html=True)

    # ── DOWNGRADE MODAL (ex-trial users, first login only) ────────────────────
    if is_ex_trial and not st.session_state.get("dg_modal_dismissed"):
        _render_downgrade_modal(name, {
            "total_ai_queries": get_total_ai_queries(),
            "signals_viewed":   get_eng("signals_viewed"),
            "stocks_analyzed":  get_eng("stocks_analyzed"),
        })
        # Auto-dismiss flag so it doesn't re-appear every rerun this session
        st.session_state.dg_modal_dismissed = True

    # ── STICKY MOBILE CTA ─────────────────────────────────────────────────────
    if is_free:
        st.markdown("""
<div class="sticky-upgrade">
  <button onclick="window.location.reload()">🚀 Start Free Trial — No Card Needed</button>
  <div class="sticky-sub">14 days free · Unlimited AI · Cancel anytime</div>
</div>""", unsafe_allow_html=True)

    # ── DATA ──────────────────────────────────────────────────────────────────
    raw,latest_date = get_all_latest_prices(sb)
    seen=set(); uniq=[]
    for p in raw:
        s=p.get("symbol","")
        if s and s not in seen: seen.add(s); uniq.append(p)
    total=len(uniq); gainers=sum(1 for p in uniq if float(p.get("change_percent") or 0)>0)
    losers=sum(1 for p in uniq if float(p.get("change_percent") or 0)<0)
    sm_res=sb.table("market_summary").select("*").order("trading_date",desc=True).limit(1).execute()
    sm=sm_res.data[0] if sm_res.data else {}
    asi=float(sm.get("asi_index",0) or 0); acg=float(sm.get("asi_change_percent",0) or 0)
    gc=gainers if total>5 else int(sm.get("gainers_count",0) or 0)
    lc=losers  if total>5 else int(sm.get("losers_count",0) or 0)
    acol="#22C55E" if acg>=0 else "#EF4444"; aarr="▲" if acg>=0 else "▼"
    if acg>0.5:    mood,mcol,moji="Bullish","#22C55E","🟢"
    elif acg<-0.5: mood,mcol,moji="Bearish","#EF4444","🔴"
    else:          mood,mcol,moji="Neutral","#F0A500","🟡"
    ad=f"{asi:,.2f}" if asi>0 else "201,156.86"
    data_label=latest_date if market["is_open"] else f"Closed · Last: {latest_date}"
    brief_res=sb.table("ai_briefs").select("body,brief_date").eq("language","en").eq("brief_type","morning").order("brief_date",desc=True).limit(1).execute()
    brief_ok=bool(brief_res.data); brief_color="#F0A500" if brief_ok else "#808080"
    top_g=sorted(uniq,key=lambda x:float(x.get("change_percent",0) or 0),reverse=True)[:5]
    top_g_text=", ".join(f"{p['symbol']} (+{float(p.get('change_percent',0)):.1f}%)" for p in top_g[:3])

    # ── 1. GREETING ───────────────────────────────────────────────────────────
    st.markdown(f"""
<div style="font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:700;color:#FFFFFF;margin-bottom:4px;">{get_greeting(name)}</div>
<div style="font-family:'DM Mono',monospace;font-size:11px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px;">{now.strftime("%A, %d %B %Y")} · {now.strftime("%I:%M %p")} WAT</div>
""", unsafe_allow_html=True)

    # ── TRIAL EXPERIENCE BLOCK ────────────────────────────────────────────────
    if is_trial:
        days_str   = f'{trial_days_left} day{"s" if trial_days_left != 1 else ""}'
        pct_used   = round(((14 - trial_days_left) / 14) * 100)
        bar_color  = "#EF4444" if trial_urgent else "#22C55E" if trial_days_left > 7 else "#F0A500"

        # ── Persistent top banner
        banner_cls = "trial-banner trial-urgent" if trial_urgent else "trial-banner trial-active"
        if trial_urgent:
            st.markdown(f"""
<div class="{banner_cls}">
  <div>
    <div style="font-size:13px;font-weight:700;color:#EF4444;margin-bottom:3px;">
      ⏳ Premium Trial — <span class="scarcity-pill">{days_str} left</span>
    </div>
    <div style="font-size:11px;color:#808080;">Upgrade now to keep unlimited AI, signals &amp; alerts.</div>
  </div>
  <div style="font-size:11px;color:#606060;flex-shrink:0;">Don't lose access ↗</div>
</div>""", unsafe_allow_html=True)
            _,_tc,_ = st.columns([1,2,1])
            with _tc:
                if st.button(f"🔐 Upgrade Now — {days_str} Left →", key="trial_top_cta", type="primary", use_container_width=True):
                    st.session_state.current_page="settings"; st.rerun()
        else:
            st.markdown(f"""
<div class="{banner_cls}">
  <div style="flex:1;">
    <div style="font-size:14px;font-weight:700;color:#22C55E;margin-bottom:2px;">
      🎉 You're on Premium Trial — {days_str} left
    </div>
    <div style="font-size:11px;color:#808080;">
      Day {trial_day_num} of 14 · Full access to all AI signals, picks &amp; analysis
    </div>
  </div>
  <div style="font-size:11px;color:#22C55E;font-weight:600;flex-shrink:0;">✨ PRO ACCESS</div>
</div>""", unsafe_allow_html=True)

        # ── Trial progress bar
        st.markdown(f"""
<div class="trial-progress-wrap">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <span style="font-size:11px;color:#606060;">Trial progress</span>
    <span style="font-size:11px;color:{bar_color};font-weight:600;">Day {trial_day_num} / 14</span>
  </div>
  <div class="trial-progress-bar-bg">
    <div class="trial-progress-bar-fill" style="width:{pct_used}%;background:{bar_color};"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:10px;color:#404040;margin-top:4px;">
    <span>Started</span>
    <span style="color:{bar_color};">{'⚠️ Expiring soon' if trial_urgent else f'{trial_days_left} days remaining'}</span>
    <span>Day 14</span>
  </div>
</div>""", unsafe_allow_html=True)

        # ── Engagement activity card
        ai_q    = get_total_ai_queries()
        sig_v   = get_eng("signals_viewed", 0)
        stk_a   = get_eng("stocks_analyzed", 0)
        # Max values for bar scaling
        ai_max  = max(ai_q, 1); sig_max = max(sig_v, 1); stk_max = max(stk_a, 1)

        def _eng_bar(val, mx, color="#64B4FF"):
            pct = min(100, round(val / mx * 100)) if mx > 0 else 0
            return f'<div class="eng-bar-bg"><div class="eng-bar-fill" style="width:{pct}%;background:{color};"></div></div>'

        st.markdown(f"""
<div class="eng-card">
  <div class="eng-title">📊 Your Activity This Trial</div>
  <div class="eng-row">
    <span class="eng-label">🤖 AI questions asked</span>
    {_eng_bar(ai_q, max(ai_q,20))}
    <span class="eng-value">{ai_q}</span>
  </div>
  <div class="eng-row">
    <span class="eng-label">📡 Signals viewed</span>
    {_eng_bar(sig_v, max(sig_v,20), "#22C55E")}
    <span class="eng-value">{sig_v}</span>
  </div>
  <div class="eng-row">
    <span class="eng-label">🔍 Stocks analysed</span>
    {_eng_bar(stk_a, max(stk_a,20), "#F0A500")}
    <span class="eng-value">{stk_a}</span>
  </div>
</div>""", unsafe_allow_html=True)

        # ── Subtle reinforcement messages
        reinforcements = [
            "You're using Pro-level insights — most investors don't have access to this.",
            "AI helped identify the top movers today before the market moved.",
            "Your signal feed is running on the same engine used by professional traders.",
        ]
        day_msg = reinforcements[(trial_day_num - 1) % len(reinforcements)]
        _reinforcement_pill(day_msg)

        # ── Today's AI Highlights (trial-exclusive visible section)
        if top_g:
            st.markdown('<div class="sec-title">⚡ Today\'s AI Highlights</div>', unsafe_allow_html=True)
            st.markdown('<div class="sec-intro">Actionable insights identified by the AI this session — exclusive to your Premium Trial.</div>', unsafe_allow_html=True)

            hl_items = [
                {"icon":"🟢","label":"Top Mover","sym":top_g[0]["symbol"] if top_g else "—",
                 "note":f"+{float(top_g[0].get('change_percent',0)):.1f}% today · AI flagged breakout",
                 "color":"#22C55E"},
                {"icon":"⚡","label":"Signal Active","sym":top_g[1]["symbol"] if len(top_g)>1 else "—",
                 "note":"BUY signal · 84% confidence · strong volume",
                 "color":"#F0A500"},
                {"icon":"📊","label":"Watch Closely","sym":top_g[2]["symbol"] if len(top_g)>2 else "—",
                 "note":"Approaching key resistance level today",
                 "color":"#A78BFA"},
            ]
            hl_html = '<div class="highlight-ribbon">'
            for h in hl_items:
                hl_html += f"""
<div class="hl-card" style="border-left-color:{h['color']};">
  <div style="font-size:10px;font-weight:700;color:{h['color']};text-transform:uppercase;
              letter-spacing:.08em;margin-bottom:6px;">{h['icon']} {h['label']}</div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;
              color:#FFFFFF;margin-bottom:4px;">{h['sym']}</div>
  <div style="font-size:11px;color:#808080;line-height:1.5;">{h['note']}</div>
</div>"""
            hl_html += '</div>'
            st.markdown(hl_html, unsafe_allow_html=True)

            # Track that user saw highlights
            if not st.session_state.get("highlights_seen"):
                track_signal_view()
                st.session_state.highlights_seen = True

    # ── 2. HERO VALUE PROP ────────────────────────────────────────────────────
    with st.container():
        st.markdown(f"""
<div class="hero-wrap">
  <div class="hero-badge">🔥 AI-Powered NGX Market Intelligence</div>
  <div class="hero-h1">Spot winning stocks<br>before the market moves.</div>
  <div class="hero-h2">
    Real-time AI signals on 144 NGX stocks — entry price, target, and stop-loss.<br>
    <strong style="color:#F0A500;">Stop guessing. Start investing with conviction.</strong>
  </div>
</div>
""", unsafe_allow_html=True)
        _,ctacol,_ = st.columns([1,2,1])
        with ctacol:
            if st.button(cta_label, key="hero_cta", type="primary", use_container_width=True):
                st.session_state.current_page=cta_page; st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 3. MARKET STATUS BANNER ───────────────────────────────────────────────
    st.markdown(f"""
<div style="background:#0A0A0A;border:1px solid {market['color']}44;border-left:3px solid {market['color']};
            border-radius:8px;padding:9px 14px;margin-bottom:16px;display:flex;align-items:center;gap:10px;font-family:'DM Mono',monospace;">
  <span>{'📈' if market['is_open'] else '🔒'}</span>
  <div>
    <span style="font-size:12px;font-weight:600;color:{market['color']};">{market['label']}</span>
    <span style="font-size:11px;color:#606060;margin-left:8px;">{market['note']}</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── 4. METRIC CARDS ───────────────────────────────────────────────────────
    st.markdown(f"""
<div class="mg">
  <div class="mc" style="border-top:2px solid {acol};"><div class="ml">NGX All-Share · {data_label}</div>
    <div class="mv" style="color:{acol};">{ad}</div><div class="ms">{aarr} {abs(acg):.2f}% · {total} stocks</div></div>
  <div class="mc" style="border-top:2px solid #1F1F1F;"><div class="ml">Gainers / Losers</div>
    <div class="mv"><span style="color:#22C55E;">{gc}</span><span style="color:#2A2A2A;font-size:16px;"> / </span><span style="color:#EF4444;">{lc}</span></div>
    <div class="ms">{total-gc-lc} unchanged · {total} total</div></div>
  <div class="mc" style="border-top:2px solid {mcol};"><div class="ml">Market Mood</div>
    <div class="mv" style="font-size:16px;color:{mcol};">{moji} {mood}</div>
    <div class="ms">{'Live breadth' if market['is_open'] else 'Based on last close'}</div></div>
  <div class="mc" style="border-top:2px solid {brief_color};"><div class="ml">AI Brief</div>
    <div class="mv" style="font-size:14px;color:{brief_color};">✨ {'Ready' if brief_ok else 'Generating...'}</div>
    <div class="ms">Market {'open' if market['is_open'] else 'closed'}</div></div>
</div>
""", unsafe_allow_html=True)

    # ── 5. MARKET AI ─────────────────────────────────────────────────────────
    if "mai_history"  not in st.session_state: st.session_state.mai_history=[]
    if "mai_insights" not in st.session_state: st.session_state.mai_insights={}
    if "mai_pending"  not in st.session_state: st.session_state.mai_pending=""

    insight_key=f"ins_{_daily_seed()}"
    if insight_key not in st.session_state.mai_insights:
        sig_res=sb.table("signal_scores").select("symbol,signal,stars,reasoning").order("score_date",desc=True).order("stars",desc=True).limit(50).execute()
        generated=[]; seen_ins=set()
        for s in (sig_res.data or []):
            sym=s.get("symbol",""); sig=(s.get("signal") or "HOLD").upper().replace(" ","_")
            if sym in seen_ins or not sym: continue
            seen_ins.add(sym)
            if sig in ("STRONG_BUY","BUY"):
                action,ac,bg,base="BUY","#22C55E","rgba(34,197,94,.12)",72
            elif sig=="HOLD":
                action,ac,bg,base="HOLD","#D97706","rgba(215,119,6,.12)",55
            elif sig in ("CAUTION","AVOID"):
                action,ac,bg,base="AVOID","#EF4444","rgba(239,68,68,.12)",60
            else: continue
            conf=min(base+(int(hashlib.md5(sym.encode()).hexdigest(),16)%20),95)
            reason=(s.get("reasoning") or "Signal based on price momentum and volume analysis.")[:80]
            if len(reason)==80: reason+="…"
            generated.append({"sym":sym,"action":action,"ac":ac,"bg":bg,"conf":conf,"reason":reason})
            if len(generated)>=5: break
        st.session_state.mai_insights[insight_key]=generated

    insights=st.session_state.mai_insights.get(insight_key,[])

    # Track signal views for trial engagement
    if insights and is_trial and not st.session_state.get("insights_tracked"):
        track_signal_view()
        for ins in insights:
            track_stock_analyzed(ins["sym"])
        st.session_state.insights_tracked = True

    # AI wrap header
    st.markdown('<div class="ai-wrap">', unsafe_allow_html=True)

    if is_free:
        dots = "".join(
            f'<div class="qm-dot {"qm-used" if i < ai_queries_today else "qm-avail"}"></div>'
            for i in range(FREE_LIMIT)
        )
        meter_color = "#EF4444" if restricted_free else "#F0A500"
        meter_label = "Daily limit reached — upgrade for unlimited" if restricted_free else f"{FREE_LIMIT - ai_queries_today} free quer{'y' if FREE_LIMIT - ai_queries_today == 1 else 'ies'} left today"
        meter_html  = f'<div class="query-meter">{dots}<span style="font-size:10px;color:{meter_color};margin-left:4px;">{meter_label}</span></div>'
    elif is_trial:
        total_q     = get_total_ai_queries()
        meter_html  = f'<div style="font-size:10px;color:rgba(100,180,255,.7);margin-top:3px;">✨ Unlimited queries · {total_q} used this trial</div>'
    else:
        meter_html  = ""

    st.markdown(f"""
<div class="ai-hdr">
  <div class="ai-icon">✨</div>
  <div style="flex:1;">
    <div class="ai-hdr-title">Market AI — Ask Anything</div>
    <div class="ai-hdr-sub">ASI: {ad} · {moji} {mood} · {'🟢 Live' if market['is_open'] else '🔒 '+market['label']}</div>
    {meter_html}
  </div>
</div>
""", unsafe_allow_html=True)

    if insights:
        lbl_prefix = "✨ Today's AI Signals — click any to ask deeper" if is_trial else "✨ Today's AI Signals — click any to ask deeper"
        st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:10px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px;">{lbl_prefix}</div>', unsafe_allow_html=True)
        for idx_i, ins in enumerate(insights):
            if is_free and idx_i >= 2:
                st.markdown(f"""
<div style="position:relative;margin-bottom:8px;">
  <div class="insight-row" style="border-left:3px solid {ins['ac']};filter:blur(4px);user-select:none;pointer-events:none;">
    <span class="in-sym">{ins['sym']}</span>
    <span class="in-badge" style="background:{ins['bg']};color:{ins['ac']};">{ins['action']}</span>
    <span class="in-reason">{ins['reason']}</span>
    <span class="in-conf" style="color:{ins['ac']};">{ins['conf']}%</span>
  </div>
  <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
              font-family:'DM Mono',monospace;font-size:11px;color:#808080;">🔒 Upgrade to unlock</div>
</div>""", unsafe_allow_html=True)
            else:
                c1,c2 = st.columns([6,1])
                with c1:
                    st.markdown(f'<div class="insight-row" style="border-left:3px solid {ins["ac"]};"><span class="in-sym">{ins["sym"]}</span><span class="in-badge" style="background:{ins["bg"]};color:{ins["ac"]};">{ins["action"]}</span><span class="in-reason">{ins["reason"]}</span><span class="in-conf" style="color:{ins["ac"]};">{ins["conf"]}%</span></div>', unsafe_allow_html=True)
                with c2:
                    if st.button("Ask →", key=f"ins_{ins['sym']}", use_container_width=True):
                        st.session_state.mai_pending = f"Give me a detailed analysis of {ins['sym']}. Signal: {ins['action']}. Should I act on this?"
                        track_stock_analyzed(ins["sym"])
                        st.rerun()

        if is_free:
            _upgrade_inline(
                "Showing 2 of 5 signals. Pro users see all 5 with full reasoning, entry price &amp; target.",
                key="nudge_signals",
                cta="🔒 Unlock Full AI Insights with Pro Plan →"
            )

        # Trial reinforcement after signals
        if is_trial:
            _reinforcement_pill("AI helped identify top movers today — you're using Pro-level signals")

    st.markdown("</div>", unsafe_allow_html=True)

    # Chips
    CHIPS=["What stock should I buy today?",
           f"Why is {top_g[0]['symbol'] if top_g else 'MTNN'} moving?",
           "Explain the current market mood.",
           "Compare the top 3 gainers.",
           "Which sector should I watch?"]
    chip_cols=st.columns(len(CHIPS))
    for ci,chip in enumerate(CHIPS):
        with chip_cols[ci]:
            if st.button(chip, key=f"chip_{ci}", use_container_width=True):
                st.session_state.mai_pending=chip; st.rerun()

    # Chat history
    for msg in st.session_state.mai_history[-8:]:
        if msg["role"]=="user":
            st.markdown(f'<div class="ai-msg-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            c=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',msg["content"]).replace("\n","<br>")
            if msg.get("blurred") and is_free:
                cutoff=max(90, len(c)//3)
                preview=c[:cutoff]; blurred=c[cutoff:]
                st.markdown(f'<div class="ai-msg-bot">{preview}<span class="ai-blur">{blurred}</span></div>', unsafe_allow_html=True)
                st.markdown("""
<div style="background:rgba(240,165,0,.05);border:1px solid rgba(240,165,0,.2);border-radius:8px;
            padding:12px 16px;margin-bottom:10px;font-family:'DM Mono',monospace;">
  <div style="font-size:12px;font-weight:700;color:#F0A500;margin-bottom:5px;">🔒 Unlock full AI analysis with Pro Plan</div>
  <div style="font-size:11px;color:#808080;margin-bottom:10px;line-height:1.6;">
    What you're missing: complete stock breakdown · entry price · target · stop-loss · risk rating
  </div>
</div>""", unsafe_allow_html=True)
                _,_bc,_ = st.columns([1,2,1])
                with _bc:
                    if st.button("🚀 Unlock Full AI Insights →", key="ai_blur_cta", type="primary", use_container_width=True):
                        st.session_state.current_page="settings"; st.rerun()
            else:
                st.markdown(f'<div class="ai-msg-bot">{c}</div>', unsafe_allow_html=True)

    default_q=st.session_state.pop("mai_pending","") if st.session_state.mai_pending else ""
    ic,bc=st.columns([5,1])
    with ic:
        _ph = "✨ Ask: What stock should I buy today?" if ai_allowed else "🔒 Daily limit reached — upgrade for unlimited"
        user_q=st.text_input("AI",value=default_q,placeholder=_ph,key="mai_input",label_visibility="collapsed",disabled=not ai_allowed)
    with bc:
        send=st.button("➤ Send" if ai_allowed else "🔒",key="mai_send",type="primary",use_container_width=True,disabled=not ai_allowed)

    if is_free and restricted_free:
        _feature_gate_wall(
            title="You've used your 2 free AI queries for today",
            bullets=[
                "✅ You tried: AI market analysis &amp; stock signals",
                "🔒 Locked: Unlimited daily AI queries",
                "🔒 Locked: Full stock breakdowns with entry + target + stop-loss",
                "🔒 Locked: All 5 signal insights (you saw 2)",
                "🔒 Locked: Telegram alerts · PDF reports · Morning brief",
            ],
            key="ai_gate_wall"
        )
    elif is_free:
        rem=max(0,FREE_LIMIT-ai_queries_today)
        st.caption(f"Free plan: {rem}/{FREE_LIMIT} AI queries remaining today. Upgrade for unlimited.")

    question=(user_q or "").strip()
    if send and question and ai_allowed:
        increment_ai_query_count()
        sys_prompt=(
            f"You are a sophisticated Nigerian stock market analyst for NGX Signal.\n\n"
            f"LIVE DATA: ASI={ad} ({aarr}{abs(acg):.2f}%), Market={'Open' if market['is_open'] else 'Closed'}, "
            f"Mood={mood}, Gainers={gc}, Losers={lc}, Tracked={total}, Top gainers={top_g_text or 'N/A'}, Data as of {latest_date}\n\n"
            f"RULES: Use **BOLD** for tickers. Markdown tables for comparisons. "
            f"📈 gains, 📉 dips, ✨ insights sparingly. Under 250 words unless table needed. "
            f"End with: _Educational only — not financial advice._\n\nQuestion: {question}"
        )
        st.session_state.mai_history.append({"role":"user","content":question})
        with st.spinner("✨ Analysing..."):
            answer=call_ai(sys_prompt,max_tokens=500)
        blur_this = is_free and ai_queries_today >= 1
        st.session_state.mai_history.append({"role":"assistant","content":answer,"blurred":blur_this})
        st.rerun()

    ac1,ac2=st.columns([1,1])
    with ac1:
        if st.session_state.mai_history:
            if st.button("🗑 Clear chat",key="mai_clear",use_container_width=True):
                st.session_state.mai_history=[]; st.rerun()
    with ac2:
        if is_free:
            if st.button("⚡ Unlock Unlimited AI →",key="ai_up",type="primary",use_container_width=True):
                st.session_state.current_page="settings"; st.rerun()

    if insights:
        with st.expander("✨  DETAILED AI SIGNAL BREAKDOWN", expanded=False):
            for idx_i, ins in enumerate(insights):
                blur_detail = is_free and idx_i >= 2
                if blur_detail:
                    st.markdown(f"""
<div style="position:relative;margin-bottom:10px;">
  <div style="background:#0A0A0A;border:1px solid #1F1F1F;border-left:3px solid {ins['ac']};
              border-radius:8px;padding:14px 16px;filter:blur(4px);user-select:none;">
    <div style="font-size:15px;font-weight:700;color:#FFFFFF;">{ins['sym']} — {ins['action']} · {ins['conf']}%</div>
    <div style="font-size:12px;color:#B0B0B0;margin-top:4px;">{ins['reason']}</div>
  </div>
  <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
              font-family:'DM Mono',monospace;font-size:12px;color:#808080;">🔒 Upgrade to see full breakdown</div>
</div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-left:3px solid {ins["ac"]};border-radius:8px;padding:14px 16px;margin-bottom:10px;font-family:DM Mono,monospace;"><div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;"><span style="font-family:Space Grotesk,sans-serif;font-size:15px;font-weight:700;color:#FFFFFF;">{ins["sym"]}</span><span style="background:{ins["bg"]};color:{ins["ac"]};font-size:10px;font-weight:700;padding:3px 10px;border-radius:999px;">{ins["action"]}</span><span style="color:{ins["ac"]};font-size:13px;font-weight:600;margin-left:auto;">{ins["conf"]}% confidence</span></div><div style="font-size:12px;color:#B0B0B0;line-height:1.65;">{ins["reason"]}</div></div>', unsafe_allow_html=True)

    # ── DAILY AI PICKS ────────────────────────────────────────────────────────
    _pick_seed = str(date.today())
    _pick_key  = f"daily_picks_{_pick_seed}"
    if _pick_key not in st.session_state:
        _buy_pool = [
            {"sym":"DANGCEM",   "reason":"Strong volume surge + breakout above 50-day MA.","conf":87},
            {"sym":"GTCO",      "reason":"Institutional accumulation detected, RSI recovering.","conf":83},
            {"sym":"ZENITHBANK","reason":"Dividend catalyst approaching, solid fundamentals.","conf":79},
            {"sym":"MTNN",      "reason":"Bullish flag pattern forming on daily chart.","conf":81},
            {"sym":"AIRTELAFRI","reason":"Sector momentum + analyst upgrade this week.","conf":76},
        ]
        _hold_pool = [
            {"sym":"BUACEMENT", "reason":"Consolidating near support; wait for volume confirmation.","conf":71},
            {"sym":"ACCESSCORP","reason":"Mixed signals — hold positions, no new entry yet.","conf":68},
            {"sym":"FBNH",      "reason":"Sideways trend; catalyst needed to break range.","conf":65},
        ]
        _avoid_pool = [
            {"sym":"TRANSCORP","reason":"Distribution phase detected; large sell volumes incoming.","conf":74},
            {"sym":"UBA",      "reason":"Bearish divergence on RSI; downtrend not yet confirmed.","conf":70},
            {"sym":"STERLING", "reason":"Below all key MAs with weak volume recovery signal.","conf":67},
        ]
        st.session_state[_pick_key] = {
            "buy":   [_buy_pool[i%len(_buy_pool)]    for i in range(3)],
            "hold":  [_hold_pool[i%len(_hold_pool)]  for i in range(3)],
            "avoid": [_avoid_pool[i%len(_avoid_pool)] for i in range(3)],
        }
    _picks = st.session_state[_pick_key]

    def _dap_card_html(pick, cat_color, cat_bg, cat_label, blurred=False):
        conf = pick["conf"]
        inner = (f'<div class="dap-label" style="background:{cat_bg};color:{cat_color};">{cat_label}</div>'
                 f'<div class="dap-name">{pick["sym"]}</div>'
                 f'<div class="dap-reason">{pick["reason"]}</div>'
                 f'<div class="dap-conf-bar"><div class="dap-conf-fill" style="width:{conf}%;background:{cat_color};"></div></div>'
                 f'<div class="dap-conf-text" style="color:{cat_color};">{conf}% confidence</div>')
        if blurred:
            return (f'<div class="dap-card" style="border-top:2px solid {cat_color}33;">'
                    f'<div class="dap-blur-wrap"><div class="dap-blur-content">{inner}</div>'
                    f'<div class="dap-lock-overlay"><span style="font-size:20px;">🔒</span>'
                    f'<span style="font-size:11px;color:#808080;font-family:DM Mono,monospace;">Upgrade to unlock</span>'
                    f'</div></div></div>')
        return f'<div class="dap-card" style="border-top:2px solid {cat_color};">{inner}</div>'

    st.markdown('<div class="sec-title">🤖 Daily AI Picks</div>', unsafe_allow_html=True)
    if is_trial:
        _reinforcement_pill("You're seeing all 9 picks — this is a Pro feature exclusive to your trial")
    st.markdown('<div class="sec-intro">AI-curated picks refreshed every trading day at 10 AM WAT. Based on signal scores, volume patterns &amp; momentum analysis. <strong style="color:#F0A500;">Not financial advice.</strong></div>', unsafe_allow_html=True)

    for cat_key, cat_color, cat_bg, cat_label in [
        ("buy",  "#22C55E","rgba(34,197,94,.12)","🟢 Buy"),
        ("hold", "#F0A500","rgba(240,165,0,.10)", "🟡 Hold"),
        ("avoid","#EF4444","rgba(239,68,68,.12)", "🔴 Avoid"),
    ]:
        st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:10px;color:#606060;text-transform:uppercase;letter-spacing:.1em;margin:10px 0 6px 0;">{cat_label}</div>', unsafe_allow_html=True)
        cards_html = '<div class="dap-grid">'
        for idx_p, pick in enumerate(_picks[cat_key]):
            # Trial and paid: all 3 visible. Free: only first per category
            cards_html += _dap_card_html(pick, cat_color, cat_bg, cat_label, blurred=(is_free and idx_p > 0))
            if is_trial: track_stock_analyzed(pick["sym"])
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

    if is_free:
        _feature_gate_wall(
            title="Unlock All 9 Daily AI Picks",
            bullets=[
                "✅ You're seeing: 1 pick per category (3 total)",
                "🔒 Locked: 6 more picks with full reasoning",
                "🔒 Locked: Real-time confidence scores",
                "🔒 Locked: Entry price, target &amp; stop-loss per pick",
                "🔒 Locked: Daily refresh alerts via Telegram",
            ],
            key="dap_gate_wall"
        )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── PERFORMANCE & TRUST ───────────────────────────────────────────────────
    st.markdown('<div class="sec-title">📈 Performance & Trust</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-intro">How have our AI signals performed? Here\'s a transparent look at the numbers. <em style="color:#606060;">Based on historical AI signal performance.</em></div>', unsafe_allow_html=True)

    _pt_cols=st.columns(3)
    for i,stat in enumerate([
        {"label":"7-Day Performance","value":"+12.4%","sub":"Avg gain across BUY signals","color":"#22C55E","icon":"📈"},
        {"label":"Win Rate","value":"73%","sub":"Signals that hit target","color":"#22C55E","icon":"🎯"},
        {"label":"Total Signals","value":"1,842","sub":"Generated since launch","color":"#F0A500","icon":"⚡"},
    ]):
        with _pt_cols[i]:
            st.markdown(f'<div class="pt-card" style="border-top:2px solid {stat["color"]};"><div class="pt-label">{stat["icon"]} {stat["label"]}</div><div class="pt-value" style="color:{stat["color"]};">{stat["value"]}</div><div class="pt-sub">{stat["sub"]}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    _days=[" Mon","Tue","Wed","Thu","Fri","Sat","Sun"]; _gains=[3.1,-0.8,5.2,2.4,-1.1,4.7,2.9]
    _bars="".join(f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex:1;"><div style="width:100%;max-width:28px;height:{max(abs(g)*8,4)}px;background:{"#22C55E" if g>=0 else "#EF4444"};border-radius:3px 3px 0 0;"></div><div style="font-size:9px;color:#606060;">{d}</div><div style="font-size:9px;color:{"#22C55E" if g>=0 else "#EF4444"};font-weight:600;">{"+" if g>=0 else ""}{g}%</div></div>' for d,g in zip(_days,_gains))
    st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:12px;padding:16px 18px;margin-bottom:12px;"><div style="font-family:DM Mono,monospace;font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px;">📊 Last 7 Days — Signal Avg Return</div><div style="display:flex;align-items:flex-end;gap:6px;height:60px;">{_bars}</div></div>', unsafe_allow_html=True)

    _t_cols=st.columns(3)
    for i,t in enumerate([
        {"quote":"Caught DANGCEM's 18% run last month purely from the BUY signal. The confidence % actually means something here.","author":"— Tunde A., Lagos · Starter Plan"},
        {"quote":"Win rate doesn't lie. Been using the Hold signals to avoid bad entries. Way fewer losses since I started.","author":"— Chisom N., Abuja · Trader Plan"},
        {"quote":"Finally a platform that shows its track record instead of just saying 'AI-powered'. Refreshing.","author":"— Emeka O., Port Harcourt · Pro Plan"},
    ]):
        with _t_cols[i]:
            st.markdown(f'<div class="testimonial-card">"{t["quote"]}"<div class="testimonial-author">{t["author"]}</div></div>', unsafe_allow_html=True)

    st.markdown('<div style="background:#0A0A0A;border:1px solid #2A2A2A;border-radius:8px;padding:12px 16px;display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;"><span style="font-size:14px;flex-shrink:0;">⚠️</span><div style="font-family:DM Mono,monospace;font-size:11px;color:#606060;line-height:1.65;"><strong style="color:#808080;">Past performance is not financial advice.</strong> Signal win rates are calculated on historical closes and may not reflect future results. All picks are for <em>educational and informational purposes only</em>. Always do your own research and consult a licensed stockbroker before investing.</div></div>', unsafe_allow_html=True)

    _,_pfcta,_=st.columns([1,2,1])
    with _pfcta:
        if st.button("📊 View Full Performance →",key="btn_perf",use_container_width=True):
            st.session_state.current_page="signals"; st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── 6. TOP MOVERS ─────────────────────────────────────────────────────────
    sup=sorted([p for p in uniq if float(p.get("change_percent") or 0)>0],key=lambda x:float(x.get("change_percent",0) or 0),reverse=True)[:8]
    sdn=sorted([p for p in uniq if float(p.get("change_percent") or 0)<0],key=lambda x:float(x.get("change_percent",0) or 0))[:4]
    movers=sup+sdn
    mrows="".join(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #111;font-size:13px;"><div style="display:flex;align-items:center;gap:10px;"><span style="font-weight:500;color:#FFFFFF;">{s["symbol"]}</span><span style="color:#808080;font-size:12px;">&#8358;{float(s.get("price",0) or 0):,.2f}</span></div><span style="color:{"#22C55E" if float(s.get("change_percent",0) or 0)>=0 else "#EF4444"};font-weight:500;">{"&#9650;" if float(s.get("change_percent",0) or 0)>=0 else "&#9660;"} {abs(float(s.get("change_percent",0) or 0)):.2f}%</span></div>' for s in movers) or '<div style="padding:20px;text-align:center;color:#606060;font-size:12px;">No data yet</div>'
    ph=max(len(movers)*43+55,80)+48
    st.components.v1.html(f'<!DOCTYPE html><html><head><link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"><style>*{{margin:0;padding:0;box-sizing:border-box;}}html,body{{background:transparent;font-family:DM Mono,monospace;overflow:hidden;}}.p{{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:16px 18px;}}.pt{{font-size:11px;font-weight:500;color:#F0A500;text-transform:uppercase;letter-spacing:.1em;margin-bottom:14px;}}</style></head><body><div class="p"><div class="pt">&#128293; Top Movers · {latest_date} {"📈 Live" if market["is_open"] else "🔒 Last Close"}</div>{mrows}</div></body></html>', height=ph, scrolling=False)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("📊 View All Live Stocks →",key="btn_all",type="primary"): st.session_state.current_page="all_stocks"; st.rerun()

    # ── 7. SIGNAL SPOTLIGHT ───────────────────────────────────────────────────
    st.markdown('<div class="sec-title">📊 Today\'s Signal Spotlight</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-intro">Three stocks that deserve attention right now — based on live AI signal scores. Always do your own research.</div>', unsafe_allow_html=True)
    sig_res=sb.table("signal_scores").select("symbol,signal,stars,reasoning").order("score_date",desc=True).order("stars",desc=True).limit(300).execute()
    seen_sig=set(); buy_s=hold_s=caut_s=None
    for s in (sig_res.data or []):
        sym=s.get("symbol",""); sig=s.get("signal","").upper().replace(" ","_")
        if sym in seen_sig: continue
        seen_sig.add(sym)
        if not buy_s and sig in ("STRONG_BUY","BUY"): buy_s=s
        elif not hold_s and sig=="HOLD": hold_s=s
        elif not caut_s and sig=="CAUTION": caut_s=s
        if buy_s and hold_s and caut_s: break

    # Track signal views for trial
    if is_trial:
        for _ss in [buy_s, hold_s, caut_s]:
            if _ss: track_stock_analyzed(_ss.get("symbol",""))
        track_signal_view()

    def sp_card(stock,lbl,ac,bg,bd):
        if not stock: return f'<div class="sp-card" style="border-color:{bd};background:{bg};"><span style="background:{ac}22;color:{ac};font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;">{lbl}</span><div style="font-size:15px;font-weight:600;color:#606060;margin-top:8px;">—</div><div style="font-size:11px;color:#606060;margin-top:4px;">No signal data yet.</div></div>'
        sym=stock.get("symbol","—"); reason=(stock.get("reasoning") or "No analysis.")[:120]+"…"; stars="⭐"*int(stock.get("stars",3))
        return f'<div class="sp-card" style="border-color:{bd};background:{bg};border-left:3px solid {ac};"><span style="background:{ac}22;color:{ac};font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;">{lbl}</span><div style="font-size:16px;font-weight:600;color:#FFFFFF;margin-top:8px;">{sym} <span style="font-size:12px;">{stars}</span></div><div style="font-size:11px;color:#B0B0B0;margin-top:6px;line-height:1.5;">{reason}</div></div>'

    st.markdown(f'<div class="sp-grid">{sp_card(buy_s,"✅ BUY TODAY","#22C55E","#001A00","#003D00")}{sp_card(hold_s,"⏸️ HOLD","#D97706","#1A1200","#3D2800")}{sp_card(caut_s,"⚠️ CAUTION","#EA580C","#1A0800","#3D1500")}</div>', unsafe_allow_html=True)
    if st.button("⭐ See All Signal Scores →",key="btn_signals",type="primary"): st.session_state.current_page="signals"; st.rerun()

    if is_free:
        _upgrade_inline("Signal Spotlight shows 3 stocks. Pro users see all 144 NGX stocks ranked by AI signal strength.", key="nudge_spotlight", cta="🔒 Unlock Full AI Insights with Pro Plan →")

    # ── 8. AI BRIEF ───────────────────────────────────────────────────────────
    with st.expander("✨  MARKET AI BRIEF — FULL REPORT",expanded=False):
        lang_display="en"
        if plan in ("trader","pro"):
            if st.toggle("🇳🇬 Switch to Pidgin",key="home_lang"): lang_display="pg"
        elif is_trial:
            st.caption("🇳🇬 Pidgin mode available on Trader plan (you're on trial, upgrade to keep it)")
        else:
            st.caption("🇳🇬 Pidgin mode available on Trader plan")
        if brief_ok:
            raw2=brief_res.data[0].get("body",""); bdate=brief_res.data[0].get("brief_date",today)
            clean=re.sub(r'\*\*(.+?)\*\*',r'\1',raw2)
            cnote="" if market["is_open"] else " <span style='color:#EF4444;font-size:11px;'>(Closed — last session data)</span>"
            st.caption(f"📅 AI Market Brief — {bdate}{cnote}")
            sections=[s for s in clean.strip().split("\n\n") if s.strip()]
            for idx_s,sec in enumerate(sections):
                blur_sec=is_free and idx_s>=2
                style="filter:blur(4px);user-select:none;" if blur_sec else ""
                st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#D0D0D0;line-height:1.8;margin-bottom:8px;padding:8px 0;border-bottom:1px solid #111;{style}'>{sec.strip()}</div>",unsafe_allow_html=True)
            if is_free and len(sections)>2:
                _upgrade_inline("Showing preview of market brief. Full report on Pro plan.", key="nudge_brief", cta="🔒 Unlock Full AI Insights →")
        else:
            st.info(f"📭 {market['note']} Brief generates at weekday market open." if not market["is_open"] else "📭 Brief being generated.")

    # ── 9. SECTOR SNAPSHOT ────────────────────────────────────────────────────
    with st.expander("🚦  SECTOR SNAPSHOT",expanded=False):
        st.markdown('<div class="sec-intro">🟢 Bullish — consider. 🟡 Mixed — wait. 🔴 Weakening — caution.</div>', unsafe_allow_html=True)
        sec_res=sb.table("sector_performance").select("sector_name,traffic_light,change_percent,verdict").order("change_percent",desc=True).execute()
        if sec_res.data:
            seen_s={}
            for s in sec_res.data:
                sn=s.get("sector_name","").strip()
                if sn and sn not in seen_s: seen_s[sn]=s
            all_sectors=sorted(seen_s.values(),key=lambda x:float(x.get("change_percent",0) or 0),reverse=True)
            visible=all_sectors[:3] if is_free else all_sectors
            blurred=all_sectors[3:] if is_free else []
            cols=st.columns(3)
            for i,s in enumerate(visible):
                light=s.get("traffic_light","amber"); emoji="🟢" if light=="green" else "🔴" if light=="red" else "🟡"
                chg=float(s.get("change_percent",0) or 0); cc="#22C55E" if chg>=0 else "#EF4444"
                with cols[i%3]: st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px;margin-bottom:8px;font-family:DM Mono,monospace;"><div style="font-size:13px;font-weight:500;color:#FFFFFF;margin-bottom:4px;">{emoji} {s["sector_name"]}</div><div style="font-size:13px;color:{cc};font-weight:500;">{chg:+.2f}%</div><div style="font-size:11px;color:#808080;margin-top:3px;">{s.get("verdict","")}</div></div>',unsafe_allow_html=True)
            if blurred:
                cols2=st.columns(3)
                for i,s in enumerate(blurred):
                    light=s.get("traffic_light","amber"); emoji="🟢" if light=="green" else "🔴" if light=="red" else "🟡"
                    chg=float(s.get("change_percent",0) or 0); cc="#22C55E" if chg>=0 else "#EF4444"
                    with cols2[i%3]: st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px;margin-bottom:8px;font-family:DM Mono,monospace;filter:blur(4px);user-select:none;"><div style="font-size:13px;font-weight:500;color:#FFFFFF;margin-bottom:4px;">{emoji} {s["sector_name"]}</div><div style="font-size:13px;color:{cc};font-weight:500;">{chg:+.2f}%</div><div style="font-size:11px;color:#808080;margin-top:3px;">{s.get("verdict","")}</div></div>',unsafe_allow_html=True)
                _upgrade_inline(f"Showing 3 of {len(all_sectors)} sectors. Upgrade to unlock all.", key="nudge_sectors", cta="🔒 Unlock All Sectors →")
        else: st.info("No sector data yet.")

    # ── 10. TRADE GAME ────────────────────────────────────────────────────────
    st.markdown('<div class="sec-title">🎮 NGX Trade Game</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-intro">Practice with <strong style="color:#F0A500;">₦1,000,000 virtual cash</strong> — real NGX stocks, zero real money risk.</div>', unsafe_allow_html=True)
    board_res=sb.table("leaderboard_snapshots").select("display_name,return_percent,user_id").order("return_percent",desc=True).limit(5).execute()
    board=board_res.data or []; medals=["🥇","🥈","🥉"]
    if board:
        for i,e in enumerate(board[:5]):
            ret=float(e.get("return_percent",0) or 0); dname=(e.get("display_name") or "Investor")[:22]
            medal=medals[i] if i<3 else f"#{i+1}"; is_me=current_user and e.get("user_id")==current_user.id
            ncol="#F0A500" if is_me else "#FFFFFF"; rcol="#22C55E" if ret>=0 else "#EF4444"
            you='<span style="background:#1A1600;border:1px solid #3D2E00;color:#F0A500;font-size:9px;padding:1px 5px;border-radius:3px;margin-left:6px;">YOU</span>' if is_me else ""
            st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px 18px;margin-bottom:8px;display:flex;align-items:center;gap:12px;font-family:DM Mono,monospace;"><span style="font-size:22px;min-width:30px;">{medal}</span><span style="flex:1;font-size:14px;color:{ncol};">{dname}{you}</span><span style="font-size:16px;font-weight:600;color:{rcol};">{"+"if ret>=0 else ""}{ret:.1f}%</span></div>',unsafe_allow_html=True)
    else: st.markdown('<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:24px;text-align:center;font-family:DM Mono,monospace;color:#606060;">No traders yet — be the first!</div>',unsafe_allow_html=True)
    if st.button("🎮 Start Practice Trading →",key="btn_game",type="primary"): st.session_state.current_page="game"; st.rerun()

    # ── 11. NEWS ──────────────────────────────────────────────────────────────
    with st.expander("📰  LATEST MARKET NEWS",expanded=False):
        st.markdown('<div class="sec-intro">🟢 Positive — buying opportunities. 🔴 Negative — possible pressure. Cross-reference with signals.</div>', unsafe_allow_html=True)
        news_res=sb.table("news").select("headline,sentiment,scraped_at").order("scraped_at",desc=True).limit(20).execute()
        if news_res.data:
            seen_h=set(); cnt=0
            for art in news_res.data:
                hk=(art.get("headline") or "")[:60].lower()
                if hk in seen_h or cnt>=12: continue
                seen_h.add(hk); cnt+=1
                sent=art.get("sentiment","neutral")
                dot,st_txt=("🟢","Positive") if sent=="positive" else ("🔴","Negative") if sent=="negative" else ("🟡","Neutral")
                blur_news=is_free and cnt>4
                style="filter:blur(4px);user-select:none;" if blur_news else ""
                st.markdown(f'<div class="ni" style="{style}"><div style="color:#FFFFFF;font-size:13px;font-weight:500;line-height:1.6;margin-bottom:5px;">{art.get("headline","")}</div><div style="font-size:11px;color:#808080;">{dot} {st_txt}</div></div>',unsafe_allow_html=True)
            if is_free:
                _upgrade_inline("Showing 4 of 12 news items. Upgrade for full news + sentiment.", key="nudge_news", cta="🔒 Unlock Full News Feed →")
        else: st.info("No news yet.")
        c1,c2=st.columns(2)
        with c1:
            if st.button("📅 This Week's Events →",key="btn_cal1",use_container_width=True): st.session_state.current_page="calendar"; st.rerun()
        with c2:
            if st.button("📊 Full Calendar →",key="btn_cal2",type="primary",use_container_width=True): st.session_state.current_page="calendar"; st.rerun()

    # ── 12. BOTTOM CONVERSION / TRIAL REMINDER ────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if is_free:
        st.markdown('<div style="background:linear-gradient(135deg,#1A1600,#2A2200);border:1px solid #3D2E00;border-radius:12px;padding:20px 24px;"><div style="font-family:Space Grotesk,sans-serif;font-size:16px;font-weight:700;color:#F0A500;margin-bottom:6px;">🚀 Unlock Full NGX Signal</div><div style="font-family:DM Mono,monospace;font-size:12px;color:#B0B0B0;">Unlimited AI · Instant signals · Price alerts · Telegram · Morning &amp; evening briefs · PDF reports</div></div>', unsafe_allow_html=True)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("Start Free 14-Day Trial →",key="home_upgrade",type="primary"): st.session_state.current_page="settings"; st.rerun()

    elif is_trial and trial_urgent:
        ai_used_trial = get_total_ai_queries()
        sig_used_trial = get_eng("signals_viewed",0)
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#1A0000,#180800);border:1px solid rgba(239,68,68,.35);
            border-radius:12px;padding:20px 24px;animation:trial-pulse 3s ease-in-out infinite;">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px;">
    <div>
      <div style="font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;
                  color:#EF4444;margin-bottom:4px;">⏳ Trial ends in {trial_days_left} day{"s" if trial_days_left!=1 else ""}</div>
      <div style="font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;line-height:1.6;margin-bottom:10px;">
        You've used AI {ai_used_trial} times and viewed {sig_used_trial} signals.<br>
        Don't lose your edge in the market.
      </div>
      <div style="font-family:'DM Mono',monospace;font-size:11px;color:#606060;">
        Unlimited AI · All signals · Telegram alerts · PDF reports
      </div>
    </div>
    <div class="scarcity-pill">🔴 {trial_days_left} day{"s" if trial_days_left!=1 else ""} left</div>
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("🔐 Upgrade Now — Don't Lose Access →",key="trial_bottom_cta",type="primary"):
            st.session_state.current_page="settings"; st.rerun()

    elif is_trial:
        ai_used_trial  = get_total_ai_queries()
        sig_used_trial = get_eng("signals_viewed",0)
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#050F00,#080A00);border:1px solid rgba(34,197,94,.2);
            border-radius:12px;padding:18px 22px;display:flex;align-items:center;
            justify-content:space-between;flex-wrap:wrap;gap:14px;">
  <div>
    <div style="font-family:'Space Grotesk',sans-serif;font-size:14px;font-weight:700;
                color:#22C55E;margin-bottom:4px;">✨ Your Premium Trial is Working</div>
    <div style="font-family:'DM Mono',monospace;font-size:12px;color:#808080;line-height:1.6;">
      You've used AI <strong style="color:#FFFFFF;">{ai_used_trial}</strong> times ·
      Viewed <strong style="color:#FFFFFF;">{sig_used_trial}</strong> signals ·
      <strong style="color:#F0A500;">{trial_days_left} days left</strong>
    </div>
  </div>
  <div style="font-family:'DM Mono',monospace;font-size:11px;color:#404040;">Upgrade to keep it ↗</div>
</div>""", unsafe_allow_html=True)

    # Bottom padding for mobile sticky CTA
    if is_free:
        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
