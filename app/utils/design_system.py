"""
NGX Signal — Design System v2
Pure black background · Pure white text · Animated glow cards
"""

NGX_DESIGN_SYSTEM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

/* ══════════════════════════════════════════════════════
   CSS CUSTOM PROPERTIES — Pure Black Theme
   ══════════════════════════════════════════════════════ */
:root {
  --ngx-font-primary:   'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  --ngx-font-secondary: 'Space Grotesk', 'Inter', -apple-system, sans-serif;
  --ngx-font-mono:      'DM Mono', 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;

  /* ── Sizes ── */
  --ngx-sz-2xl: 36px;
  --ngx-sz-xl:  28px;
  --ngx-sz-lg:  22px;
  --ngx-sz-md:  17px;
  --ngx-sz-base:15px;
  --ngx-sz-sm:  13px;
  --ngx-sz-xs:  11px;

  /* ── PURE BLACK PALETTE ── */
  --ngx-bg:        #000000;   /* pure black app background */
  --ngx-surface:   #0D0D0D;   /* card surface — barely lifted */
  --ngx-surface2:  #111111;   /* nested surfaces */
  --ngx-border:    #1F1F1F;   /* default border */
  --ngx-border2:   #2A2A2A;   /* hover border */

  /* ── PURE WHITE TEXT ── */
  --ngx-text:      #FFFFFF;   /* pure white — all main text */
  --ngx-text-sub:  #E0E0E0;   /* subheadings, descriptions */
  --ngx-text-dim:  #A0A0A0;   /* captions, metadata */
  --ngx-text-muted:#606060;   /* placeholders, disabled */

  /* ── BRAND COLOURS ── */
  --ngx-gold:      #F0A500;
  --ngx-gold-dim:  #D4911A;
  --ngx-gold-dk:   #B87D00;
  --ngx-green:     #22C55E;
  --ngx-red:       #EF4444;
  --ngx-amber:     #D97706;
  --ngx-orange:    #EA580C;
  --ngx-blue:      #3B82F6;
  --ngx-cyan:      #22D3EE;
  --ngx-purple:    #A78BFA;

  /* ── GLOW COLOURS ── */
  --glow-gold:   rgba(240, 165,  0, 0.18);
  --glow-green:  rgba( 34, 197, 94, 0.18);
  --glow-red:    rgba(239,  68, 68, 0.18);
  --glow-blue:   rgba( 59, 130,246, 0.18);
  --glow-purple: rgba(167, 139,250, 0.18);
  --glow-cyan:   rgba( 34, 211,238, 0.18);

  /* ── BUTTONS ── */
  --ngx-pill:  999px;
  --ngx-h-sm:  30px;
  --ngx-h-md:  36px;
  --ngx-h-lg:  44px;
}

/* ══════════════════════════════════════════════════════
   GLOBAL ANIMATIONS
   ══════════════════════════════════════════════════════ */
@keyframes ngx-glow-gold {
  0%, 100% { box-shadow: 0 0 8px var(--glow-gold), 0 0 20px var(--glow-gold); }
  50%       { box-shadow: 0 0 16px var(--glow-gold), 0 0 40px var(--glow-gold), 0 0 60px rgba(240,165,0,0.08); }
}
@keyframes ngx-glow-green {
  0%, 100% { box-shadow: 0 0 8px var(--glow-green), 0 0 20px var(--glow-green); }
  50%       { box-shadow: 0 0 16px var(--glow-green), 0 0 40px var(--glow-green); }
}
@keyframes ngx-glow-blue {
  0%, 100% { box-shadow: 0 0 8px var(--glow-blue), 0 0 20px var(--glow-blue); }
  50%       { box-shadow: 0 0 16px var(--glow-blue), 0 0 40px var(--glow-blue); }
}
@keyframes ngx-glow-purple {
  0%, 100% { box-shadow: 0 0 8px var(--glow-purple), 0 0 20px var(--glow-purple); }
  50%       { box-shadow: 0 0 16px var(--glow-purple), 0 0 40px var(--glow-purple); }
}
@keyframes ngx-pulse-border {
  0%, 100% { border-color: rgba(240,165,0,0.3); }
  50%       { border-color: rgba(240,165,0,0.8); }
}
@keyframes ngx-fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes ngx-shimmer {
  0%   { background-position: -200% center; }
  100% { background-position:  200% center; }
}

/* ══════════════════════════════════════════════════════
   A. HEADING SCALE — pure white
   ══════════════════════════════════════════════════════ */
.ngx-h1 { font-family:var(--ngx-font-secondary); font-size:36px; font-weight:700; line-height:1.10; letter-spacing:-0.03em; color:#FFFFFF; margin:0; }
.ngx-h2 { font-family:var(--ngx-font-secondary); font-size:28px; font-weight:600; line-height:1.20; letter-spacing:-0.02em; color:#FFFFFF; margin:0; }
.ngx-h3 { font-family:var(--ngx-font-secondary); font-size:22px; font-weight:600; line-height:1.30; letter-spacing:-0.01em; color:#FFFFFF; margin:0; }
.ngx-h4 { font-family:var(--ngx-font-secondary); font-size:17px; font-weight:600; line-height:1.40; letter-spacing:0;     color:#FFFFFF; margin:0; }
.ngx-h5 { font-family:var(--ngx-font-primary);   font-size:15px; font-weight:600; line-height:1.40; letter-spacing:0;     color:#FFFFFF; margin:0; }

/* ══════════════════════════════════════════════════════
   B. BODY / UI TEXT — white hierarchy
   ══════════════════════════════════════════════════════ */
.ngx-body    { font-family:var(--ngx-font-primary); font-size:15px; font-weight:400; line-height:1.65; color:#FFFFFF; }
.ngx-body-sub{ font-family:var(--ngx-font-primary); font-size:15px; font-weight:400; line-height:1.65; color:#E0E0E0; }
.ngx-small   { font-family:var(--ngx-font-primary); font-size:13px; font-weight:400; line-height:1.50; color:#E0E0E0; }
.ngx-caption { font-family:var(--ngx-font-primary); font-size:11px; font-weight:400; line-height:1.45; letter-spacing:0.01em; color:#A0A0A0; }
.ngx-label   { font-family:var(--ngx-font-primary); font-size:11px; font-weight:500; line-height:1.40; letter-spacing:0.08em; text-transform:uppercase; color:#A0A0A0; }
.ngx-nav        { font-family:var(--ngx-font-primary); font-size:13px; font-weight:500; color:#A0A0A0; }
.ngx-nav-active { font-family:var(--ngx-font-primary); font-size:13px; font-weight:600; color:var(--ngx-gold); }

/* ══════════════════════════════════════════════════════
   C. DATA TYPOGRAPHY
   ══════════════════════════════════════════════════════ */
.ngx-ticker    { font-family:var(--ngx-font-secondary); font-size:15px; font-weight:600; letter-spacing:0.04em;  text-transform:uppercase; color:#FFFFFF; }
.ngx-ticker-sm { font-family:var(--ngx-font-secondary); font-size:13px; font-weight:600; letter-spacing:0.04em;  text-transform:uppercase; color:#FFFFFF; }
.ngx-ticker-lg { font-family:var(--ngx-font-secondary); font-size:22px; font-weight:700; letter-spacing:-0.01em; text-transform:uppercase; color:#FFFFFF; }
.ngx-price     { font-family:var(--ngx-font-mono); font-size:22px; font-weight:500; letter-spacing:-0.02em; color:#FFFFFF; }
.ngx-price-sm  { font-family:var(--ngx-font-mono); font-size:15px; font-weight:500; letter-spacing:-0.01em; color:#FFFFFF; }
.ngx-price-xl  { font-family:var(--ngx-font-mono); font-size:36px; font-weight:500; letter-spacing:-0.03em; color:#FFFFFF; }
.ngx-pct       { font-family:var(--ngx-font-mono); font-size:13px; font-weight:500; }
.ngx-pct-up    { color:var(--ngx-green); }
.ngx-pct-dn    { color:var(--ngx-red);   }
.ngx-pct-flat  { color:#A0A0A0; }
.ngx-th        { font-family:var(--ngx-font-primary); font-size:11px; font-weight:600; letter-spacing:0.07em; text-transform:uppercase; color:#A0A0A0; }
.ngx-td        { font-family:var(--ngx-font-primary); font-size:13px; font-weight:400; color:#FFFFFF; }
.ngx-stat      { font-family:var(--ngx-font-mono); font-size:28px; font-weight:500; letter-spacing:-0.02em; color:#FFFFFF; }
.ngx-stat-sm   { font-family:var(--ngx-font-mono); font-size:22px; font-weight:500; letter-spacing:-0.01em; color:#FFFFFF; }

/* ══════════════════════════════════════════════════════
   D. SIGNAL BADGES
   ══════════════════════════════════════════════════════ */
.ngx-signal-badge {
  display:inline-flex; align-items:center;
  padding:3px 10px; border-radius:var(--ngx-pill);
  font-family:var(--ngx-font-secondary); font-size:11px;
  font-weight:700; letter-spacing:0.07em;
  text-transform:uppercase; white-space:nowrap; line-height:1.5;
  border:1px solid transparent;
}
.ngx-badge-strong-buy { background:rgba(34,197,94,0.15);  color:#22C55E;  border-color:rgba(34,197,94,0.35);
                         animation: ngx-glow-green 3s ease-in-out infinite; }
.ngx-badge-buy        { background:rgba(34,197,94,0.10);  color:#22C55E;  border-color:rgba(34,197,94,0.25); }
.ngx-badge-breakout   { background:rgba(59,130,246,0.12); color:#3B82F6;  border-color:rgba(59,130,246,0.30);
                         animation: ngx-glow-blue 3s ease-in-out infinite; }
.ngx-badge-hold       { background:rgba(215,119,6,0.12);  color:#D97706;  border-color:rgba(215,119,6,0.30); }
.ngx-badge-caution    { background:rgba(234,88,12,0.12);  color:#EA580C;  border-color:rgba(234,88,12,0.30); }
.ngx-badge-avoid      { background:rgba(239,68,68,0.12);  color:#EF4444;  border-color:rgba(239,68,68,0.30); }

/* ══════════════════════════════════════════════════════
   E. ANIMATED GLOW CARDS
   ══════════════════════════════════════════════════════ */

/* Base glow card — all cards get animation + fade-in */
.ngx-card {
  background: var(--ngx-surface);
  border: 1px solid var(--ngx-border);
  border-radius: 12px;
  padding: 16px 18px;
  position: relative;
  overflow: hidden;
  animation: ngx-fade-in 0.4s ease both;
  transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.2s ease;
}
.ngx-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, rgba(240,165,0,0.04) 0%, transparent 60%);
  pointer-events: none;
}
.ngx-card:hover {
  border-color: rgba(240,165,0,0.35);
  box-shadow: 0 0 20px rgba(240,165,0,0.12), 0 4px 24px rgba(0,0,0,0.6);
  transform: translateY(-2px);
}

/* Gold glow card — KPI metrics, main stats */
.ngx-card-gold {
  background: var(--ngx-surface);
  border: 1px solid rgba(240,165,0,0.25);
  border-radius: 12px;
  padding: 16px 18px;
  animation: ngx-fade-in 0.4s ease both, ngx-glow-gold 4s ease-in-out infinite;
  transition: transform 0.2s ease;
}
.ngx-card-gold:hover { transform: translateY(-2px) scale(1.01); }

/* Green glow card — BUY signals, gainers */
.ngx-card-green {
  background: rgba(0, 20, 0, 0.8);
  border: 1px solid rgba(34,197,94,0.30);
  border-radius: 12px;
  padding: 16px 18px;
  animation: ngx-fade-in 0.4s ease both, ngx-glow-green 4s ease-in-out infinite;
  transition: transform 0.2s ease;
}
.ngx-card-green:hover { transform: translateY(-2px); }

/* Red glow card — AVOID signals, losers */
.ngx-card-red {
  background: rgba(20, 0, 0, 0.8);
  border: 1px solid rgba(239,68,68,0.30);
  border-radius: 12px;
  padding: 16px 18px;
  animation: ngx-fade-in 0.4s ease both;
  transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.2s ease;
}
.ngx-card-red:hover {
  border-color: rgba(239,68,68,0.6);
  box-shadow: 0 0 20px rgba(239,68,68,0.15);
  transform: translateY(-2px);
}

/* Blue glow card — breakout watch, info */
.ngx-card-blue {
  background: rgba(0, 5, 20, 0.8);
  border: 1px solid rgba(59,130,246,0.30);
  border-radius: 12px;
  padding: 16px 18px;
  animation: ngx-fade-in 0.4s ease both, ngx-glow-blue 4s ease-in-out infinite;
  transition: transform 0.2s ease;
}
.ngx-card-blue:hover { transform: translateY(-2px); }

/* Purple glow card — premium/AI features */
.ngx-card-purple {
  background: rgba(10, 0, 20, 0.8);
  border: 1px solid rgba(167,139,250,0.30);
  border-radius: 12px;
  padding: 16px 18px;
  animation: ngx-fade-in 0.4s ease both, ngx-glow-purple 4s ease-in-out infinite;
  transition: transform 0.2s ease;
}
.ngx-card-purple:hover { transform: translateY(-2px); }

/* Shimmer card — for loading / CTA highlights */
.ngx-card-shimmer {
  background: linear-gradient(90deg,
    var(--ngx-surface) 0%,
    rgba(240,165,0,0.08) 50%,
    var(--ngx-surface) 100%);
  background-size: 200% 100%;
  border: 1px solid rgba(240,165,0,0.20);
  border-radius: 12px;
  padding: 16px 18px;
  animation: ngx-shimmer 3s linear infinite;
}

/* Metric card — tight, centered, for stat numbers */
.ngx-metric {
  background: var(--ngx-surface);
  border: 1px solid var(--ngx-border);
  border-radius: 10px;
  padding: 14px 16px;
  text-align: center;
  animation: ngx-fade-in 0.5s ease both;
  transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.2s ease;
}
.ngx-metric:hover {
  border-color: rgba(240,165,0,0.4);
  box-shadow: 0 0 18px rgba(240,165,0,0.14);
  transform: translateY(-2px);
}
.ngx-metric-label { font-family:var(--ngx-font-primary); font-size:10px; font-weight:500; letter-spacing:0.09em; text-transform:uppercase; color:#A0A0A0; margin-bottom:8px; }
.ngx-metric-value { font-family:var(--ngx-font-mono);    font-size:24px; font-weight:500; letter-spacing:-0.02em; color:#FFFFFF; line-height:1; margin-bottom:4px; }
.ngx-metric-sub   { font-family:var(--ngx-font-mono);    font-size:11px; color:#A0A0A0; }

/* ══════════════════════════════════════════════════════
   F. BUTTON SYSTEM
   ══════════════════════════════════════════════════════ */
.ngx-btn {
  display:inline-flex; align-items:center; justify-content:center;
  gap:6px; border-radius:var(--ngx-pill);
  font-family:var(--ngx-font-primary); font-weight:500;
  font-size:13px; line-height:1; white-space:nowrap;
  cursor:pointer; text-decoration:none;
  border:1px solid transparent; outline:none;
  padding:0 18px; height:var(--ngx-h-md); min-width:80px;
  -webkit-font-smoothing:antialiased;
  transition: all 0.2s ease;
  position:relative; overflow:hidden; user-select:none;
}
.ngx-btn:focus-visible { box-shadow:0 0 0 3px rgba(240,165,0,0.4); }
.ngx-btn:disabled { opacity:0.38; cursor:not-allowed; pointer-events:none; }

/* Sizes */
.ngx-btn-sm { font-size:11px; height:var(--ngx-h-sm); padding:0 14px; min-width:60px; }
.ngx-btn-md { font-size:13px; height:var(--ngx-h-md); padding:0 18px; }
.ngx-btn-lg { font-size:15px; font-weight:600; height:var(--ngx-h-lg); padding:0 24px; min-width:120px; }
.ngx-btn-full { width:100%; }

/* Primary */
.ngx-btn-primary { background:var(--ngx-gold); border-color:var(--ngx-gold); color:#000000; font-weight:600; }
.ngx-btn-primary:hover:not(:disabled) {
  background:var(--ngx-gold-dim); border-color:var(--ngx-gold-dim);
  transform:translateY(-1px);
  box-shadow:0 0 16px rgba(240,165,0,0.40);
}
.ngx-btn-primary:active:not(:disabled) { transform:scale(0.97); }

/* Outline */
.ngx-btn-outline { background:transparent; border-color:var(--ngx-gold); color:var(--ngx-gold); }
.ngx-btn-outline:hover:not(:disabled) {
  background:rgba(240,165,0,0.12); transform:translateY(-1px);
  box-shadow:0 0 12px rgba(240,165,0,0.25);
}

/* Ghost */
.ngx-btn-ghost { background:transparent; border-color:transparent; color:#A0A0A0; }
.ngx-btn-ghost:hover:not(:disabled) { background:rgba(255,255,255,0.06); color:#FFFFFF; transform:translateY(-1px); }

/* CTA — largest, strongest glow */
.ngx-btn-cta {
  background:var(--ngx-gold); border-color:var(--ngx-gold);
  color:#000000; font-weight:700; font-size:15px;
  height:var(--ngx-h-lg); padding:0 28px; min-width:140px;
  animation: ngx-glow-gold 3s ease-in-out infinite;
}
.ngx-btn-cta:hover:not(:disabled) {
  background:var(--ngx-gold-dim);
  transform:translateY(-2px);
  box-shadow:0 0 0 4px rgba(240,165,0,0.25), 0 6px 20px rgba(240,165,0,0.35);
}

/* Danger */
.ngx-btn-danger { background:rgba(239,68,68,0.12); border-color:rgba(239,68,68,0.30); color:var(--ngx-red); }
.ngx-btn-danger:hover:not(:disabled) { background:rgba(239,68,68,0.22); box-shadow:0 0 12px rgba(239,68,68,0.25); transform:translateY(-1px); }

/* Surface */
.ngx-btn-surface { background:#111111; border-color:#1F1F1F; color:#FFFFFF; }
.ngx-btn-surface:hover:not(:disabled) { background:#1A1A1A; border-color:#2A2A2A; transform:translateY(-1px); }

/* ══════════════════════════════════════════════════════
   G. SECTION HELPERS
   ══════════════════════════════════════════════════════ */
.ngx-section-title {
  font-family:var(--ngx-font-secondary); font-size:18px; font-weight:700;
  color:#FFFFFF; margin:24px 0 8px 0;
  animation: ngx-fade-in 0.4s ease both;
}
.ngx-section-intro {
  font-family:var(--ngx-font-primary); font-size:13px; color:#E0E0E0;
  line-height:1.7; margin-bottom:14px;
  background:#0D0D0D; border:1px solid #1F1F1F; border-radius:8px;
  padding:14px 16px;
  animation: ngx-fade-in 0.5s ease both;
}
.ngx-divider { border:none; border-top:1px solid #1F1F1F; margin:16px 0; }

/* ══════════════════════════════════════════════════════
   H. MOBILE OVERRIDES
   ══════════════════════════════════════════════════════ */
@media (max-width:768px) {
  .ngx-h1    { font-size:26px; }
  .ngx-h2    { font-size:22px; }
  .ngx-h3    { font-size:18px; }
  .ngx-h4    { font-size:15px; }
  .ngx-price-xl { font-size:28px; }
  .ngx-price    { font-size:18px; }
  .ngx-stat     { font-size:22px; }
  .ngx-btn-responsive { width:100%; height:var(--ngx-h-lg); }
}

/* ══════════════════════════════════════════════════════
   I. STREAMLIT OVERRIDES — pure black + white text
   ══════════════════════════════════════════════════════ */

/* All Streamlit text → white */
.stApp, .stApp * {
  color: #FFFFFF;
}

/* Markdown text inside app */
.stMarkdown p, .stMarkdown li, .stMarkdown span,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
  color: #FFFFFF !important;
}

/* Buttons — keep font system */
.stButton > button {
  font-family: var(--ngx-font-primary) !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  border-radius: var(--ngx-pill) !important;
  transition: all 0.2s ease !important;
  -webkit-font-smoothing: antialiased !important;
  color: #A0A0A0 !important;
}
.stButton > button[kind="primary"] {
  font-weight: 600 !important;
  color: #000000 !important;
}
.stButton > button:hover { transform: translateY(-1px) !important; }
.stButton > button:active { transform: scale(0.97) !important; }

/* Inputs */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea textarea {
  font-family: var(--ngx-font-primary) !important;
  font-size: 13px !important;
  background: #0D0D0D !important;
  border: 1px solid #1F1F1F !important;
  color: #FFFFFF !important;
}
.stTextInput > div > div > input::placeholder { color: #606060 !important; }
.stTextInput > div > div > input:focus {
  border-color: var(--ngx-gold) !important;
  box-shadow: 0 0 0 2px rgba(240,165,0,0.20) !important;
}

/* Select */
.stSelectbox > div > div {
  font-family: var(--ngx-font-primary) !important;
  font-size: 13px !important;
  background: #0D0D0D !important;
  border: 1px solid #1F1F1F !important;
  color: #FFFFFF !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  gap: 4px !important;
  border-bottom: 1px solid #1F1F1F !important;
}
.stTabs [data-baseweb="tab"] {
  font-size: 12px !important;
  color: #A0A0A0 !important;
  background: transparent !important;
  padding: 8px 16px !important;
}
.stTabs [aria-selected="true"] {
  color: var(--ngx-gold) !important;
  border-bottom: 2px solid var(--ngx-gold) !important;
}

/* Expander */
.streamlit-expanderHeader {
  background: #0D0D0D !important;
  border: 1px solid #1F1F1F !important;
  border-radius: 8px !important;
  color: #FFFFFF !important;
  font-family: var(--ngx-font-primary) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.streamlit-expanderHeader:hover {
  border-color: rgba(240,165,0,0.4) !important;
  box-shadow: 0 0 12px rgba(240,165,0,0.12) !important;
}
.streamlit-expanderContent {
  background: #050505 !important;
  border: 1px solid #1F1F1F !important;
  border-top: none !important;
}

/* Toggle */
.stToggle label, .stCheckbox label, .stRadio label {
  color: #FFFFFF !important;
  font-family: var(--ngx-font-primary) !important;
}

/* Caption */
.stCaption, [data-testid="stCaptionContainer"] {
  color: #A0A0A0 !important;
  font-family: var(--ngx-font-primary) !important;
  font-size: 11px !important;
}

/* Alert / info boxes */
.stAlert { background: #0D0D0D !important; border: 1px solid #1F1F1F !important; color: #FFFFFF !important; }

/* Metric widget */
[data-testid="metric-container"] label {
  font-family: var(--ngx-font-primary) !important;
  font-size: 11px !important;
  font-weight: 500 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: #A0A0A0 !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
  font-family: var(--ngx-font-mono) !important;
  font-size: 28px !important;
  font-weight: 500 !important;
  letter-spacing: -0.02em !important;
  color: #FFFFFF !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
  font-family: var(--ngx-font-mono) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #000000; }
::-webkit-scrollbar-thumb { background: #1F1F1F; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--ngx-gold); box-shadow: 0 0 6px rgba(240,165,0,0.5); }

/* hr */
hr { border-color: #1F1F1F !important; }
</style>
"""


# Extra CSS to nuke legacy blue-black colours on all pages
_COLOUR_PATCH_CSS = """
<style>
/* ── Patch old blue-black card colours to pure black ── */
[style*="background:#10131A"],[style*="background: #10131A"],
[style*="background:#0A0C0F"],[style*="background: #0A0C0F"],
[style*="background:#0D0D0D"],[style*="background: #0D0D0D"],
[style*="background-color:#10131A"],[style*="background-color: #10131A"],
[style*="background-color:#0A0C0F"],[style*="background-color: #0A0C0F"] {
  background-color: #0A0A0A !important;
}
/* ── Old muted text → white hierarchy ── */
[style*="color:#E8E2D4"] { color: #FFFFFF !important; }
[style*="color:#9CA3AF"] { color: #D0D0D0 !important; }
[style*="color:#6B7280"] { color: #B0B0B0 !important; }
[style*="color:#4B5563"] { color: #A0A0A0 !important; }
[style*="color:#374151"] { color: #808080 !important; }
[style*="color:#2D3139"] { color: #606060 !important; }
/* ── Old borders ── */
[style*="border:1px solid #1E2229"] { border-color: #1F1F1F !important; }
[style*="border-color:#1E2229"]     { border-color: #1F1F1F !important; }
/* ── Empty element boxes (white squares) ── */
[data-testid="stEmpty"] > div { background: transparent !important; }
[data-testid="column"] > div > div[style=""] { background: transparent !important; }
/* ── st.metric ── */
[data-testid="stMetricValue"] { color: #FFFFFF !important; }
[data-testid="stMetricLabel"] { color: #A0A0A0 !important; }
/* ── Select dropdown ── */
[data-baseweb="menu"] li { background: #0D0D0D !important; color: #FFFFFF !important; }
[data-baseweb="menu"] li:hover { background: #1A1A1A !important; }
/* ── Toggle / checkbox / radio ── */
.stToggle label, .stCheckbox label, .stRadio label { color: #FFFFFF !important; }
/* ── Progress bar ── */
.stProgress > div > div { background: #1F1F1F !important; }
/* ── Alert box ── */
.stAlert { background: #0A0A0A !important; color: #FFFFFF !important; }
/* ── Table ── */
.stDataFrame td, .stDataFrame th { background: #0A0A0A !important; color: #FFFFFF !important; border-color: #1F1F1F !important; }
/* ── Form background ── */
.stForm { background: #0A0A0A !important; }
/* ── All column containers ── */
[data-testid="column"] { background: transparent !important; }
</style>
"""


def inject_design_system() -> None:
    import streamlit as st
    st.markdown(NGX_DESIGN_SYSTEM_CSS, unsafe_allow_html=True)
    st.markdown(_COLOUR_PATCH_CSS, unsafe_allow_html=True)


# ── Helper functions ──────────────────────────────────

def glow_card(content: str, variant: str = "default", extra_style: str = "") -> str:
    """Return an animated glow card HTML string."""
    classes = {
        "default": "ngx-card",
        "gold":    "ngx-card-gold",
        "green":   "ngx-card-green",
        "red":     "ngx-card-red",
        "blue":    "ngx-card-blue",
        "purple":  "ngx-card-purple",
        "shimmer": "ngx-card-shimmer",
    }
    cls = classes.get(variant, "ngx-card")
    return f'<div class="{cls}" style="{extra_style}">{content}</div>'


def metric_card(label: str, value: str, sub: str = "",
                glow_color: str = "gold") -> str:
    """Return an animated metric card HTML string."""
    anim = {
        "gold":   "ngx-glow-gold",
        "green":  "ngx-glow-green",
        "red":    "",
        "blue":   "ngx-glow-blue",
    }.get(glow_color, "ngx-glow-gold")
    extra = f"animation:{anim} 4s ease-in-out infinite;" if anim else ""
    return (
        f'<div class="ngx-metric" style="{extra}">'
        f'<div class="ngx-metric-label">{label}</div>'
        f'<div class="ngx-metric-value">{value}</div>'
        f'{"<div class=\"ngx-metric-sub\">" + sub + "</div>" if sub else ""}'
        f'</div>'
    )


def signal_badge(signal_code: str, size: str = "md") -> str:
    cfg = {
        "STRONG_BUY":     ("ngx-badge-strong-buy", "Strong Buy"),
        "BUY":            ("ngx-badge-buy",         "Buy"),
        "BREAKOUT_WATCH": ("ngx-badge-breakout",    "Breakout Watch"),
        "HOLD":           ("ngx-badge-hold",        "Hold"),
        "CAUTION":        ("ngx-badge-caution",     "Caution"),
        "AVOID":          ("ngx-badge-avoid",       "Avoid"),
        "SELL":           ("ngx-badge-avoid",       "Sell"),
    }
    cls, label = cfg.get(signal_code.upper().replace(" ", "_"),
                         ("ngx-badge-hold", signal_code))
    fs = "10px" if size == "sm" else "11px"
    return f'<span class="ngx-signal-badge {cls}" style="font-size:{fs};">{label}</span>'


def price_html(price: float, change_pct: float, show_change: bool = True) -> str:
    arrow = "▲" if change_pct >= 0 else "▼"
    cls   = "ngx-pct ngx-pct-up" if change_pct >= 0 else "ngx-pct ngx-pct-dn"
    out   = f'<span class="ngx-price">₦{price:,.2f}</span>'
    if show_change:
        out += f' <span class="{cls}" style="font-size:13px;">{arrow} {abs(change_pct):.2f}%</span>'
    return out


def ticker_html(symbol: str, size: str = "md") -> str:
    cls = {"sm": "ngx-ticker-sm", "md": "ngx-ticker", "lg": "ngx-ticker-lg"}.get(size, "ngx-ticker")
    return f'<span class="{cls}">{symbol.upper()}</span>'
