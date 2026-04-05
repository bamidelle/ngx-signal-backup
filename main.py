"""
NGX Signal — Main Application
================================
Value-First Architecture:
  • Unauthenticated users land on Live Market (all_stocks) — no forced login
  • Auth only triggered when gated features are clicked
  • Gated features: Watchlist, Ask AI, Premium Signals, Alerts, Game, Dividends,
                    Learn, Calc, Calendar, Notifications, Settings
  • Public features: Live Market, Hot Stocks, Signal Scores (read-only), Sectors

Nav rows (post-login: all 15 items):
  Row 1: Home · Live · Hot · Signals · Sectors
  Row 2: Trade · Alerts · Ask AI · Discover · Dividends
  Row 3: Learn · Calc · Calendar · Alerts+ · Settings
"""

import streamlit as st
from app.utils.supabase_client import get_supabase
from app.utils.auth import load_profile
from app.utils.design_system import inject_design_system

# ── MUST be first Streamlit call ─────────────────────────────────────────────
st.set_page_config(
    page_title            = "NGX Signal — Nigerian Stock Market Intelligence",
    page_icon             = "📈",
    layout                = "wide",
    initial_sidebar_state = "collapsed",
)

inject_design_system()
from app.utils.webpushr import inject_webpushr_tracking
inject_webpushr_tracking()

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
  /* ── Hide Streamlit chrome ── */
  #MainMenu{visibility:hidden;}
  footer{visibility:hidden;}
  header{visibility:hidden;}
  [data-testid="stStatusWidget"]{display:none;}
  [data-testid="stDeployButton"]{display:none;}
  [data-testid="stDecoration"]{display:none;}
  [data-testid="stToolbar"]{display:none;}
  [data-testid="stSidebar"]{display:none!important;}
  [data-testid="collapsedControl"]{display:none!important;}
  .stAppDeployButton{display:none;}
  .viewerBadge_container__r5tak{display:none;}

  /* ── Pure black background — every container ── */
  .stApp,.stApp>div,
  [data-testid="stAppViewContainer"],
  [data-testid="stAppViewBlockContainer"],
  [data-testid="stHeader"],
  [data-testid="stVerticalBlock"],
  [data-testid="stVerticalBlockBorderWrapper"],
  [data-testid="stHorizontalBlock"],
  [data-testid="column"],
  [data-testid="stForm"],
  [data-testid="stExpander"],
  section.main,section.main>div,
  div.element-container,
  div.stMarkdown,
  div[data-testid="stMetric"],
  div[class*="block-container"],
  div[class*="main-container"],
  div.reportview-container { background:#000000!important; }
  .block-container {
    padding-top:0!important; padding-bottom:80px!important;
    max-width:1200px!important;
    padding-left:0.75rem!important; padding-right:0.75rem!important;
    background:#000000!important;
  }
  /* Kill any white/light bg that leaks from page files */
  div[style*="background: white"],
  div[style*="background:white"],
  div[style*="background: #fff"],
  div[style*="background:#fff"],
  div[style*="background: #FFF"],
  div[style*="background:#FFF"],
  div[style*="background: rgb(255"],
  div[style*="background-color: white"],
  div[style*="background-color:#fff"],
  div[style*="background-color: #fff"] {
    background:#000000!important;
    background-color:#000000!important;
  }
  /* st.components iframe wrappers */
  .stIFrame { background:#000000!important; }
  /* dataframe / table backgrounds */
  .stDataFrame, .dataframe, table { background:#000000!important; }
  .stDataFrame td, .stDataFrame th { background:#0D0D0D!important; color:#FFFFFF!important; border-color:#1F1F1F!important; }
  /* st.metric */
  [data-testid="stMetric"] { background:#111111!important; border:1px solid #1F1F1F!important; border-radius:10px!important; padding:12px!important; }
  [data-testid="stMetricValue"] { color:#FFFFFF!important; }
  [data-testid="stMetricLabel"] { color:#A0A0A0!important; }
  /* radio + checkbox */
  .stRadio>div, .stCheckbox>div { background:transparent!important; }
  .stRadio label, .stCheckbox label { color:#FFFFFF!important; }
  /* multiselect */
  .stMultiSelect>div>div { background:#0D0D0D!important; border-color:#1F1F1F!important; }
  /* slider */
  .stSlider>div>div { background:transparent!important; }
  .stSlider [data-testid="stTickBarMin"],.stSlider [data-testid="stTickBarMax"] { color:#A0A0A0!important; }
  /* date input */
  .stDateInput>div>div { background:#0D0D0D!important; border-color:#1F1F1F!important; color:#FFFFFF!important; }
  /* progress bar */
  .stProgress>div>div>div { background:#F0A500!important; }
  .stProgress>div>div { background:#1F1F1F!important; }

  /* ── All text white ── */
  .stApp,.stApp * { color:#FFFFFF; }
  p,span,div,li,td,th,label,h1,h2,h3,h4,h5,h6 { color:#FFFFFF; }
  .stMarkdown,.stMarkdown p,.stMarkdown li,.stMarkdown span { color:#FFFFFF!important; }
  [data-testid="stMarkdownContainer"] * { color:#FFFFFF!important; }

  /* ── Keyframe animations ── */
  @keyframes ngx-fadein {
    from{opacity:0;transform:translateY(6px);}
    to{opacity:1;transform:translateY(0);}
  }
  @keyframes ngx-shimmer {
    0%{background-position:-400px 0;}
    100%{background-position:400px 0;}
  }
  @keyframes ngx-pulse {
    0%,100%{box-shadow:0 0 0 rgba(240,165,0,0);}
    50%{box-shadow:0 0 16px rgba(240,165,0,0.2);}
  }
  @keyframes ngx-glow-green {
    0%,100%{box-shadow:0 0 0 rgba(34,197,94,0);}
    50%{box-shadow:0 0 14px rgba(34,197,94,0.18);}
  }

  /* ── TOP BAR ── */
  .ngx-topbar {
    background:#080808; border-bottom:1px solid #1A1A1A;
    margin:0 -0.75rem 0 -0.75rem; padding:0 16px;
    display:flex; align-items:center; justify-content:space-between;
    height:52px; position:sticky; top:0; z-index:999;
    box-shadow:0 1px 0 #1A1A1A,0 2px 20px rgba(240,165,0,0.06);
  }
  .ngx-logo-ngx    {font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:800;color:#FFFFFF;letter-spacing:-0.5px;}
  .ngx-logo-signal {font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:800;color:#F0A500;letter-spacing:-0.5px;text-shadow:0 0 12px rgba(240,165,0,0.5);}
  .ngx-tagline     {font-family:'DM Mono',monospace;font-size:10px;color:#303030;letter-spacing:.15em;text-transform:uppercase;margin-left:10px;}
  .ngx-right       {display:flex;align-items:center;gap:8px;}
  .ngx-username    {font-family:'DM Mono',monospace;font-size:12px;color:#808080;}
  .ngx-badge       {font-family:'DM Mono',monospace;font-size:10px;font-weight:700;padding:3px 10px;border-radius:4px;text-transform:uppercase;letter-spacing:.05em;color:#000000;}

  /* ═══════════════════════════════════════
     PRIMARY NAV BAR — 5 tabs, sticky
     ═══════════════════════════════════════ */
  .ngx-nav-bar {
    background:#050505;
    border-bottom:1px solid #1A1A1A;
    margin:0 -0.75rem 0 -0.75rem;
    padding:0 4px;
    display:flex;
    align-items:stretch;
    height:50px;
    position:sticky;
    top:52px;
    z-index:998;
  }
  .ngx-nav-bar .stButton>button {
    background:transparent!important;
    border:none!important;
    border-bottom:3px solid transparent!important;
    border-radius:0!important;
    font-family:'DM Mono',monospace!important;
    font-size:12px!important;
    font-weight:500!important;
    color:#606060!important;
    padding:0 6px!important;
    height:50px!important;
    width:100%!important;
    white-space:nowrap!important;
    line-height:1.2!important;
    letter-spacing:.01em!important;
    transition:color 0.15s ease,border-color 0.15s ease!important;
    transform:none!important;
  }
  .ngx-nav-bar .stButton>button:hover {
    color:#FFFFFF!important;
    background:rgba(255,255,255,0.03)!important;
    transform:none!important;
  }
  .ngx-nav-bar .stButton>button[kind="primary"] {
    color:#F0A500!important;
    border-bottom-color:#F0A500!important;
    background:rgba(240,165,0,0.05)!important;
    font-weight:700!important;
  }

  /* ═══════════════════════════════════════
     SUBMENU DRAWER
     ═══════════════════════════════════════ */
  .ngx-submenu {
    background:#060606;
    border-bottom:1px solid #1A1A1A;
    margin:0 -0.75rem 1.2rem -0.75rem;
    padding:8px 12px 12px 12px;
    animation:ngx-submenu-open 0.16s ease forwards;
  }
  @keyframes ngx-submenu-open {
    from{opacity:0;transform:translateY(-5px);}
    to{opacity:1;transform:translateY(0);}
  }
  .ngx-submenu-section-label {
    font-family:'DM Mono',monospace;
    font-size:9px;
    font-weight:700;
    color:#3A3A3A;
    text-transform:uppercase;
    letter-spacing:.15em;
    padding:8px 2px 4px 2px;
  }
  .ngx-submenu-section-label:first-child{padding-top:2px;}
  .ngx-submenu .stButton>button {
    background:#0D0D0D!important;
    border:1px solid #1E1E1E!important;
    border-radius:8px!important;
    font-family:'DM Mono',monospace!important;
    font-size:11px!important;
    font-weight:500!important;
    color:#909090!important;
    padding:6px 4px!important;
    width:100%!important;
    height:38px!important;
    white-space:nowrap!important;
    transition:all 0.15s ease!important;
    transform:none!important;
  }
  .ngx-submenu .stButton>button:hover {
    color:#F0A500!important;
    border-color:rgba(240,165,0,0.4)!important;
    background:#120D00!important;
    transform:none!important;
  }
  .ngx-submenu .stButton>button[kind="primary"] {
    background:#150F00!important;
    border-color:#F0A500!important;
    color:#F0A500!important;
    font-weight:700!important;
  }
  /* No submenu shown — still need content spacing */
  .ngx-nav-spacer{height:1.2rem;}

  /* ── METRIC CARDS ── */
  .ngx-metric-card {
    background:#111111; border:1px solid #222222;
    border-radius:12px; padding:16px 14px;
    text-align:center; animation:ngx-fadein 0.4s ease both;
    transition:border-color 0.2s ease,box-shadow 0.2s ease;
  }
  .ngx-metric-card:hover {
    border-color:#333333;
    box-shadow:0 4px 20px rgba(0,0,0,0.5);
  }
  .ngx-metric-val  {font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:800;line-height:1.1;margin-bottom:4px;}
  .ngx-metric-lbl  {font-family:'DM Mono',monospace;font-size:10px;color:#666666;text-transform:uppercase;letter-spacing:.1em;}

  /* ── GATE CARD ── */
  .ngx-gate-card {
    background:linear-gradient(135deg,#0A0800,#150F00);
    border:1px solid #3D2800; border-radius:14px;
    padding:28px 24px; text-align:center;
    animation:ngx-fadein 0.35s ease,ngx-pulse 3s ease infinite;
    max-width:520px; margin:40px auto;
  }

  /* ── FORM INPUTS ── */
  .stTextInput>div>div>input {
    background:#0D0D0D!important; border:1px solid #1F1F1F!important;
    border-radius:8px!important; color:#FFFFFF!important;
  }
  .stTextInput>div>div>input:focus {
    border-color:#F0A500!important;
    box-shadow:0 0 0 2px rgba(240,165,0,0.20),0 0 12px rgba(240,165,0,0.10)!important;
  }
  .stTextInput>div>div>input::placeholder{color:#404040!important;}
  .stSelectbox>div>div{background:#0D0D0D!important;border:1px solid #1F1F1F!important;color:#FFFFFF!important;}
  .stNumberInput>div>div>input{background:#0D0D0D!important;border:1px solid #1F1F1F!important;color:#FFFFFF!important;}

  /* ── TABS ── */
  .stTabs [data-baseweb="tab-list"]{background:transparent!important;gap:4px!important;border-bottom:1px solid #1F1F1F!important;}
  .stTabs [data-baseweb="tab"]{font-size:12px!important;color:#808080!important;background:transparent!important;padding:8px 16px!important;}
  .stTabs [aria-selected="true"]{color:#F0A500!important;border-bottom:2px solid #F0A500!important;}

  /* ── EXPANDER ── */
  .streamlit-expanderHeader {
    background:#0A0A0A!important; border:1px solid #1F1F1F!important;
    border-radius:8px!important; color:#FFFFFF!important;
    font-family:'DM Mono',monospace!important; font-size:12px!important;
    transition:border-color 0.25s ease,box-shadow 0.25s ease!important;
  }
  .streamlit-expanderHeader:hover {
    border-color:rgba(240,165,0,0.45)!important;
    box-shadow:0 0 14px rgba(240,165,0,0.14)!important;
    color:#F0A500!important;
  }
  .streamlit-expanderContent {
    background:#040404!important; border:1px solid #1F1F1F!important;
    border-top:none!important; color:#FFFFFF!important;
  }

  /* ── BUTTONS ── */
  .stButton>button {
    font-family:'DM Mono',monospace!important;
    font-size:11px!important; border-radius:8px!important;
    transition:all 0.2s ease!important;
  }
  .stButton>button[kind="primary"]{font-weight:600!important;}
  .stButton>button:hover{transform:translateY(-1px)!important;}
  .stButton>button:active{transform:scale(0.97)!important;}

  /* ── MISC ── */
  .stAlert{background:#0D0D0D!important;border:1px solid #1F1F1F!important;color:#FFFFFF!important;}
  hr{border-color:#1F1F1F!important;}

  /* ── FOOTER ── */
  .ngx-footer {
    background:#080808; border-top:1px solid #1A1A1A;
    margin:24px -0.75rem -0.75rem -0.75rem; padding:16px 20px;
    font-family:'DM Mono',monospace;
  }
  .ngx-footer-disclaimer{font-size:10px;color:#505050;line-height:1.6;text-align:center;max-width:900px;margin:0 auto;}
  .ngx-footer-sources{font-size:10px;color:#505050;text-align:center;margin-top:6px;}
  .ngx-footer-sources span{color:#808080;}

  /* ── MOBILE ── */
  @media(max-width:768px){
    .ngx-topbar{padding:0 10px;height:48px;}
    .ngx-logo-ngx,.ngx-logo-signal{font-size:17px;}
    .block-container{padding-left:0.4rem!important;padding-right:0.4rem!important;}
    .ngx-nav-bar .stButton>button{font-size:10px!important;padding:0 4px!important;}
    .ngx-submenu .stButton>button{font-size:10px!important;height:34px!important;}
    .ngx-metric-val{font-size:22px!important;}
    .ngx-gate-card{padding:22px 16px;margin:24px auto;}
  }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ══════════════════════════════════════════════════════════════════════════════
if "user"          not in st.session_state: st.session_state.user          = None
if "profile"       not in st.session_state: st.session_state.profile       = {}
if "current_page"  not in st.session_state: st.session_state.current_page  = "all_stocks"
if "show_auth"     not in st.session_state: st.session_state.show_auth     = False
if "auth_reason"   not in st.session_state: st.session_state.auth_reason   = ""


def navigate(page: str):
    st.session_state.current_page = page
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SILENT SESSION RESTORE  (no forced redirect)
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.user is None:
    try:
        sb   = get_supabase()
        sess = sb.auth.get_session()
        if sess and sess.user:
            st.session_state.user = sess.user
            load_profile(sess.user.id)
    except Exception:
        pass   # silent — visitor stays on public page

# ══════════════════════════════════════════════════════════════════════════════
# GATE HELPER — call before rendering any protected feature
# ══════════════════════════════════════════════════════════════════════════════

# Pages that require login
GATED_PAGES = {
    "home", "game", "dividends",
    "learn", "calculator", "calendar", "notifications",
    "settings", "reports", "admin",
}

def require_auth(reason: str = "") -> bool:
    """
    Returns True if user is authenticated.
    If not, shows a stylish gate card and the auth form inline.
    Call at the top of any gated page render function.
    """
    if st.session_state.user:
        return True

    # Show gate card
    st.markdown(f"""
    <div class="ngx-gate-card">
      <div style="font-size:40px;margin-bottom:14px;">🔒</div>
      <div style="font-family:'Space Grotesk',sans-serif;font-size:20px;
                  font-weight:800;color:#F0A500;margin-bottom:10px;">
        You've found a Premium Feature!
      </div>
      <div style="font-family:'DM Mono',monospace;font-size:13px;
                  color:#FFFFFF;line-height:1.7;margin-bottom:6px;">
        {"<em style='color:#A0A0A0;'>" + reason + "</em><br><br>" if reason else ""}
        Create a <strong style="color:#F0A500;">free account</strong> to unlock
        personal watchlists, AI-powered signals, price alerts, and more.
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        if st.button("🚀 Create Free Account  →", key="gate_signup",
                     type="primary", use_container_width=True):
            st.session_state.show_auth = True
            st.rerun()
        st.markdown(
            "<div style='text-align:center;font-family:DM Mono,monospace;"
            "font-size:11px;color:#505050;margin-top:8px;'>Already have an account? "
            "<span style='color:#F0A500;cursor:pointer;' onclick=\"\">Sign in below</span></div>",
            unsafe_allow_html=True
        )

    if st.session_state.show_auth:
        from app.views import auth as auth_view
        auth_view.render()

    return False


# ══════════════════════════════════════════════════════════════════════════════
# USER / PLAN STATE
# ══════════════════════════════════════════════════════════════════════════════
user         = st.session_state.user
profile      = st.session_state.profile
plan         = profile.get("plan", "free") if user else "visitor"
_full_name   = (profile.get("full_name") or "").strip()
name         = _full_name.split()[0] if (_full_name and user) else (user.email.split("@")[0] if user else "")
current_page = st.session_state.current_page

plan_colors = {
    "free":    "#404040",
    "starter": "#2563EB",
    "trader":  "#7C3AED",
    "pro":     "#F0A500",
    "visitor": "#1A1A1A",
}
plan_color = plan_colors.get(plan, "#404040")

# ══════════════════════════════════════════════════════════════════════════════
# TOP BAR
# ══════════════════════════════════════════════════════════════════════════════
if user:
    right_html = (
        f"<span class='ngx-username'>{name}</span>"
        f"<span class='ngx-badge' style='background:{plan_color};'>{plan.upper()}</span>"
    )
else:
    right_html = (
        "<span style='font-family:DM Mono,monospace;font-size:11px;"
        "color:#505050;margin-right:4px;'>Free access</span>"
    )

st.markdown(f"""
<div class="ngx-topbar">
  <div style="display:flex;align-items:center;">
    <span class="ngx-logo-ngx">NGX</span>
    <span class="ngx-logo-signal">Signal</span>
    <span class="ngx-tagline">Smart Investing</span>
  </div>
  <div class="ngx-right">{right_html}</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# NAV — 5-tab primary bar + grouped submenu drawer
# ══════════════════════════════════════════════════════════════════════════════

# ── Session state for submenu ─────────────────────────────────────────────────
if "submenu_open" not in st.session_state:
    st.session_state.submenu_open = False

def _nav_btn(icon: str, label: str, page_key: str, key_prefix: str = "nav") -> bool:
    """Render one nav button; returns True if clicked."""
    lock = " 🔒" if (page_key in GATED_PAGES and not user) else ""
    clicked = st.button(
        f"{icon}\n{label}{lock}",
        key=f"{key_prefix}_{page_key}",
        use_container_width=True,
        type="primary" if current_page == page_key else "secondary",
    )
    return clicked

# ── Primary nav bar (5 items always visible) ─────────────────────────────────
#   📊 Live  |  ⭐ Signals  |  🔥 Hot  |  🏠 Home  |  ☰ More
PRIMARY = [
    ("all_stocks", "📊", "Live"),
    ("signals",    "⭐", "Signals"),
    ("home",       "🤖", "Market AI"),
]
MORE_ACTIVE = current_page not in [p for p, _, _ in PRIMARY]

st.markdown('<div class="ngx-nav-bar">', unsafe_allow_html=True)
nav_cols = st.columns(4)

for idx, (page_key, icon, label) in enumerate(PRIMARY):
    with nav_cols[idx]:
        if _nav_btn(icon, label, page_key):
            st.session_state.submenu_open = False
            navigate(page_key)

with nav_cols[3]:
    more_type = "primary" if MORE_ACTIVE or st.session_state.submenu_open else "secondary"
    more_icon = "✕" if st.session_state.submenu_open else "☰"
    if st.button(
        f"{more_icon}\nMore",
        key="nav_more_toggle",
        use_container_width=True,
        type=more_type,
    ):
        st.session_state.submenu_open = not st.session_state.submenu_open
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# ── Submenu drawer — shown when More is toggled ───────────────────────────────
if st.session_state.submenu_open:
    st.markdown('<div class="ngx-submenu">', unsafe_allow_html=True)

    # Section: Market Tools
    st.markdown('<div class="ngx-submenu-section-label">📡 Market</div>',
                unsafe_allow_html=True)
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1:
        if _nav_btn("💸", "Dividends", "dividends", "sub"):
            st.session_state.submenu_open = False; navigate("dividends")
    with r1c2:
        if _nav_btn("📅", "Calendar",  "calendar",  "sub"):
            st.session_state.submenu_open = False; navigate("calendar")
    with r1c3:
        if _nav_btn("📄", "Reports",   "reports",   "sub"):
            st.session_state.submenu_open = False; navigate("reports")
    with r1c4:
        if _nav_btn("🎮", "Trade",     "game",      "sub"):
            st.session_state.submenu_open = False; navigate("game")

    # Section: Tools & Account
    st.markdown('<div class="ngx-submenu-section-label">🛠 Tools &amp; Account</div>',
                unsafe_allow_html=True)
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        if _nav_btn("📚", "Learn",    "learn",       "sub"):
            st.session_state.submenu_open = False; navigate("learn")
    with r2c2:
        if _nav_btn("🧮", "Calc",     "calculator",  "sub"):
            st.session_state.submenu_open = False; navigate("calculator")
    with r2c3:
        if _nav_btn("⚙️", "Settings", "settings",    "sub"):
            st.session_state.submenu_open = False; navigate("settings")
    with r2c4:
        if user and profile.get("email") == "aybamibello@gmail.com":
            if _nav_btn("👑", "Admin", "admin", "sub"):
                st.session_state.submenu_open = False; navigate("admin")
        else:
            st.empty()

    st.markdown('</div>', unsafe_allow_html=True)

else:
    # No submenu — just add spacing so content doesn't jump to nav bar
    st.markdown('<div class="ngx-nav-spacer"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LIVE MARKET PAGE  — public value-first landing (defined before router)
# ══════════════════════════════════════════════════════════════════════════════
def _render_live_market():
    """
    Public landing page.
    Shows metric cards, live stock table, TradingView chart, and AI summary.
    No login required. Fully SEO-indexable.
    """
    from datetime import date, timedelta
    sb = get_supabase()

    # ── Fetch data ────────────────────────────────────
    date_res = sb.table("stock_prices").select("trading_date") \
        .order("trading_date", desc=True).limit(1).execute()
    latest_date = date_res.data[0]["trading_date"] if date_res.data else str(date.today())

    prices_res = sb.table("stock_prices") \
        .select("symbol, price, change_percent, volume, trading_date") \
        .eq("trading_date", latest_date).limit(500).execute()
    today_prices = prices_res.data or []

    # Sparse fallback
    if len(today_prices) < 30:
        broad = sb.table("stock_prices") \
            .select("symbol, price, change_percent, volume, trading_date") \
            .order("trading_date", desc=True).limit(6000).execute()
        sym_map = {}
        for p in (broad.data or []):
            s = p.get("symbol","")
            if s and s not in sym_map:
                sym_map[s] = p
        today_prices = list(sym_map.values())

    meta_res = sb.table("stocks").select("symbol, company_name, sector").limit(500).execute()
    meta_map = {s["symbol"]: s for s in (meta_res.data or [])}

    stocks = []
    seen: set = set()
    for p in today_prices:
        sym = p.get("symbol","")
        if not sym or sym in seen: continue
        seen.add(sym)
        meta = meta_map.get(sym, {})
        stocks.append({
            "symbol":         sym,
            "price":          float(p.get("price",0) or 0),
            "change_percent": float(p.get("change_percent",0) or 0),
            "volume":         int(p.get("volume",0) or 0),
            "company_name":   meta.get("company_name", sym),
            "sector":         meta.get("sector","Other"),
            "data_date":      p.get("trading_date",""),
        })

    total   = len(stocks)
    gainers = sum(1 for s in stocks if s["change_percent"] > 0)
    losers  = sum(1 for s in stocks if s["change_percent"] < 0)

    # ── Page header ───────────────────────────────────
    st.markdown("""
    <div style='animation:ngx-fadein 0.3s ease;margin-bottom:18px;'>
      <div style='font-family:"Space Grotesk",sans-serif;font-size:22px;
                  font-weight:800;color:#FFFFFF;margin-bottom:3px;'>
        📊 All Live NGX Stocks
      </div>
      <div style='font-family:"DM Mono",monospace;font-size:11px;
                  color:#A0A0A0;text-transform:uppercase;letter-spacing:.1em;'>
        TradingView charts · AI analysis · Real-time NGX data
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Metric cards (3 columns) ──────────────────────
    m1, m2, m3 = st.columns(3)

    with m1:
        st.markdown(
            "<div class='ngx-metric-card' style='border-top:3px solid #F0A500;"
            "animation-delay:0s;'>"
            "<div class='ngx-metric-val' style='color:#F0A500;'>144</div>"
            "<div class='ngx-metric-lbl'>Stocks Tracked</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with m2:
        st.markdown(
            f"<div class='ngx-metric-card' style='border-top:3px solid #22C55E;"
            f"animation-delay:0.08s;'>"
            f"<div class='ngx-metric-val' style='color:#22C55E;'>🔥 {gainers}</div>"
            f"<div class='ngx-metric-lbl'>Gainers Today</div>"
            f"</div>",
            unsafe_allow_html=True
        )
    with m3:
        st.markdown(
            f"<div class='ngx-metric-card' style='border-top:3px solid #EF4444;"
            f"animation-delay:0.16s;'>"
            f"<div class='ngx-metric-val' style='color:#EF4444;'>📉 {losers}</div>"
            f"<div class='ngx-metric-lbl'>Losers Today</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ── Search + filter row ───────────────────────────
    sf1, sf2, sf3 = st.columns([3, 2, 2])
    with sf1:
        search = st.text_input(
            "Search", placeholder="Symbol or company…",
            key="lm_search", label_visibility="collapsed"
        ).upper().strip()
    with sf2:
        sort_by = st.selectbox(
            "Sort", ["Best gainers","Biggest losers","Highest volume","Symbol A-Z"],
            key="lm_sort", label_visibility="collapsed"
        )
    with sf3:
        sector_opts = ["All sectors"] + sorted({
            s["sector"] for s in stocks
            if s.get("sector") and s["sector"] not in ("Other","")
        })
        sector_filter = st.selectbox(
            "Sector", sector_opts, key="lm_sector", label_visibility="collapsed"
        )

    # ── Apply filters ─────────────────────────────────
    filtered = stocks[:]
    if search:
        filtered = [s for s in filtered
                    if search in s["symbol"]
                    or search in (s.get("company_name","")).upper()]
    if sector_filter != "All sectors":
        filtered = [s for s in filtered if s.get("sector") == sector_filter]
    if sort_by == "Best gainers":
        filtered = sorted(filtered, key=lambda x: x["change_percent"], reverse=True)
    elif sort_by == "Biggest losers":
        filtered = sorted(filtered, key=lambda x: x["change_percent"])
    elif sort_by == "Highest volume":
        filtered = sorted(filtered, key=lambda x: x["volume"], reverse=True)
    else:
        filtered = sorted(filtered, key=lambda x: x["symbol"])

    # ── Pagination ────────────────────────────────────
    PAGE_SIZE = 20
    total_filtered = len(filtered)
    total_pages    = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)

    fkey = f"{search}|{sort_by}|{sector_filter}"
    if st.session_state.get("lm_fkey") != fkey:
        st.session_state.lm_fkey = fkey
        st.session_state.lm_page = 1
    if "lm_page" not in st.session_state:
        st.session_state.lm_page = 1

    page_num    = st.session_state.lm_page
    page_stocks = filtered[(page_num-1)*PAGE_SIZE : page_num*PAGE_SIZE]

    st.markdown(
        f"<div style='font-family:DM Mono,monospace;font-size:12px;"
        f"color:#666666;margin-bottom:10px;'>"
        f"Showing <strong style='color:#F0A500;'>{len(page_stocks)}</strong> of "
        f"<strong style='color:#FFFFFF;'>{total_filtered}</strong> stocks"
        f" · Page <strong style='color:#F0A500;'>{page_num}</strong> of {total_pages}"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── Stock cards ───────────────────────────────────
    # Average volume for ratio calc
    since = str(date.today() - timedelta(days=30))
    try:
        hist_res = sb.table("stock_prices") \
            .select("symbol, volume, trading_date") \
            .gte("trading_date", since) \
            .limit(10000).execute()
        vol_acc: dict = {}
        for h in (hist_res.data or []):
            s = h.get("symbol","")
            v = int(h.get("volume",0) or 0)
            if s and v:
                if s not in vol_acc: vol_acc[s] = []
                vol_acc[s].append(v)
        avg_vol_map = {s: sum(vs)/len(vs) for s, vs in vol_acc.items()}
    except Exception:
        avg_vol_map = {}

    # ── Build 30-day history map for charts ─────────────
    from datetime import timedelta
    hist_start = str(date.today() - timedelta(days=35))
    try:
        hist_res2 = sb.table("stock_prices")             .select("symbol, price, trading_date")             .gte("trading_date", hist_start)             .order("trading_date", desc=False)             .limit(20000).execute()
        history_map: dict = {}
        for h in (hist_res2.data or []):
            s = h.get("symbol", "")
            if s:
                if s not in history_map:
                    history_map[s] = []
                history_map[s].append(h)
    except Exception:
        history_map = {}

    for i, stock in enumerate(page_stocks):
        _render_stock_card(stock, avg_vol_map, i, history_map)

    # ── Pagination controls ───────────────────────────
    if total_pages > 1:
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if page_num > 1 and st.button("‹ Prev", key="lm_prev",
                                          use_container_width=True):
                st.session_state.lm_page -= 1; st.rerun()
        with pc2:
            st.markdown(
                f"<div style='text-align:center;font-family:DM Mono,monospace;"
                f"font-size:12px;color:#666666;padding:8px 0;'>"
                f"Page <strong style='color:#F0A500;'>{page_num}</strong>"
                f" of <strong style='color:#FFFFFF;'>{total_pages}</strong></div>",
                unsafe_allow_html=True
            )
        with pc3:
            if page_num < total_pages and st.button("Next ›", key="lm_next",
                                                    type="primary",
                                                    use_container_width=True):
                st.session_state.lm_page += 1; st.rerun()

    # ── Unauthenticated CTA banner ────────────────────
    if not user:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background:linear-gradient(135deg,#0A0800,#180E00);
                    border:1px solid #3D2800;border-radius:14px;
                    padding:24px;text-align:center;
                    animation:ngx-fadein 0.4s ease,ngx-pulse 4s ease infinite;'>
          <div style='font-family:"Space Grotesk",sans-serif;font-size:18px;
                      font-weight:800;color:#F0A500;margin-bottom:8px;'>
            🚀 Want AI-powered signals with entry, target &amp; stop-loss?
          </div>
          <div style='font-family:"DM Mono",monospace;font-size:13px;
                      color:#FFFFFF;line-height:1.7;margin-bottom:16px;'>
            Premium members get instant BUY/SELL signals, price alerts via Telegram,
            and a personalised morning brief every trading day.
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        cta_l, cta_m, cta_r = st.columns([1, 2, 1])
        with cta_m:
            if st.button("🚀 Get Free Access →", key="lm_cta_signup",
                         type="primary", use_container_width=True):
                st.session_state.show_auth = True
                navigate("home")


def _render_stock_card(stock: dict, avg_vol_map: dict, idx: int,
                       history_map: dict = None):
    """Render one expandable stock card — delegates to all_stocks.render_stock_card."""
    from app.views.all_stocks import render_stock_card
    render_stock_card(
        stock=stock,
        history_map=history_map or {},
        avg_vol_map=avg_vol_map,
        index=idx,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ROUTER  (functions defined above, router executes here)
# ══════════════════════════════════════════════════════════════════════════════
page = st.session_state.current_page

# ── PUBLIC PAGES ─────────────────────────────────────────────────────────────
if page == "all_stocks":
    _render_live_market()

elif page == "signals":
    from app.views.signals import render; render()

# Legacy routes still accessible
elif page == "hot":
    from app.views.hot import render; render()
elif page == "sectors":
    from app.views.sectors import render; render()
elif page == "discover":
    from app.views.discover import render; render()
elif page == "ask_ai":
    from app.views.ask_ai import render; render()
elif page == "alerts":
    from app.views.alerts import render; render()

# ── GATED PAGES ──────────────────────────────────────────────────────────────
elif page == "home":
    if require_auth("Access your AI market briefs, personalised dashboard and morning signals."):
        from app.views.home import render; render()

elif page == "game":
    if require_auth("Practice trading with ₦1M virtual cash on the NGX."):
        from app.views.game import render; render()

elif page == "dividends":
    if require_auth("Track dividend announcements and calculate your income."):
        from app.views.dividends import render; render()

elif page == "learn":
    if require_auth("Access our full NGX stock market learning library."):
        from app.views.learn import render; render()

elif page == "calculator":
    if require_auth("Model investment returns and risk with our calculator."):
        from app.views.calculator import render; render()

elif page == "calendar":
    if require_auth("Upcoming earnings, AGMs, and dividend dates for NGX stocks."):
        from app.views.earnings_calendar import render; render()

elif page == "reports":
    if require_auth("Download AI-generated PDF intelligence reports."):
        from app.views.reports import render; render()

elif page == "notifications":
    if require_auth("Manage push, Telegram, and email notification settings."):
        from app.views.notification_settings import render; render()

elif page == "settings":
    if require_auth("Manage your account, plan, and profile."):
        from app.views.settings_hub import render; render()

elif page == "admin":
    if require_auth("Admin dashboard — manage users and plans."):
        from app.views.admin import render; render()

else:
    _render_live_market()



st.markdown("""
<div class="ngx-footer">
  <div class="ngx-footer-disclaimer">
    ⚠️ <strong style="color:#808080;">Disclaimer:</strong>
    NGX Signal is an independent market intelligence platform and is not affiliated with
    or endorsed by the Nigerian Exchange Group (NGX) or the Securities and Exchange
    Commission (SEC) Nigeria. All data, signals, and analysis are for
    <strong style="color:#808080;">educational and informational purposes only</strong>
    and do not constitute financial advice. Always consult a licensed stockbroker
    before making investment decisions.
  </div>
  <div class="ngx-footer-sources">
    <span>Data sources:</span>
    NGX Pulse · TradingView Screener · AFX Kwayisi · Nairametrics · BusinessDay · TechCabal · Vanguard Nigeria
  </div>
  <div style="text-align:center;font-size:10px;color:#303030;margin-top:8px;">
    © 2026 NGX Signal · All market data from the Nigerian Exchange (NGX)
  </div>
</div>
""", unsafe_allow_html=True)
