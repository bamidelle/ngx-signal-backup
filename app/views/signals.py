"""
NGX Signal — Signal Scores View
================================
Hybrid monetisation: Always show DATA, restrict INTELLIGENCE by tier.

Tier signal access matrix:
  visitor  → 3 signals, label + price only, no details, no expander
  free     → 5/day cap, 3-min delay badge, no entry/exit/target, no reasoning
  trial    → full access, all signals
  starter  → real-time, entry/exit shown, reasoning shown, no portfolio advice
  trader   → priority signals first, all details
  pro      → all details + advanced AI narrative + strategy context
"""

import streamlit as st
from datetime import datetime, timedelta
from app.utils.supabase_client import get_supabase
from app.components.inline_alert_widget import (
    load_user_alerts, render_alert_widget, _bell_label,
)
from app.utils.webpushr import maybe_push_signal

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL DISPLAY CONFIG
# ══════════════════════════════════════════════════════════════════════════════

SIGNAL_CONFIG = {
    "STRONG_BUY":     ("#16A34A", "⭐⭐⭐⭐⭐", "STRONG BUY"),
    "BUY":            ("#22C55E", "⭐⭐⭐⭐",   "BUY"),
    "BREAKOUT_WATCH": ("#3B82F6", "⭐⭐⭐⭐",   "BREAKOUT WATCH"),
    "HOLD":           ("#D97706", "⭐⭐⭐",     "HOLD"),
    "CAUTION":        ("#EA580C", "⭐⭐",       "CAUTION"),
    "AVOID":          ("#DC2626", "⭐",         "AVOID"),
}
DEFAULT_CONFIG = ("#6B7280", "⭐⭐⭐", "HOLD")

# Signal priority ordering for trader tier
SIGNAL_PRIORITY = ["STRONG_BUY", "BUY", "BREAKOUT_WATCH", "HOLD", "CAUTION", "AVOID"]

# ══════════════════════════════════════════════════════════════════════════════
# TIER SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

TIER_ORDER  = ["visitor", "free", "trial", "starter", "trader", "pro"]
PAID_TIERS  = {"starter", "trader", "pro"}
TRIAL_TIERS = {"trial"}

# ── Feature minimum tier requirements ────────────────────────────────────────
_FEATURE_MIN_TIER: dict[str, str] = {
    # Signal list access
    "signals_full_list":      "free",      # see more than 3 signals
    "signals_realtime":       "starter",   # no 3-min delay label
    "signals_priority_sort":  "trader",    # priority queue ordering
    # Card detail levels
    "card_reasoning_short":   "starter",   # short DB reasoning text
    "card_entry_exit":        "starter",   # entry / target / stop-loss grid
    "card_score_bars":        "free",      # momentum/volume/composite bars
    "card_full_narrative":    "starter",   # rich multi-paragraph narrative
    "card_pro_narrative":     "pro",       # advanced AI analysis + strategy
    # Alert widget
    "alert_widget":           "starter",
}

# ── Daily signal view limits ──────────────────────────────────────────────────
_DAILY_SIGNAL_LIMITS: dict[str, int | None] = {
    "visitor": 3,   # hard cap, no counter needed
    "free":    5,   # per-day, tracked in session
    "trial":   None,
    "starter": None,
    "trader":  None,
    "pro":     None,
}

# ── Lock copy registry ────────────────────────────────────────────────────────
_LOCK_COPY: dict[str, dict] = {
    "signals_full_list": {
        "title":   "Create a Free Account to See All Signals",
        "bullets": ["✅ Visitors see 3 sample signals",
                    "🔒 Free accounts: 5 signals/day",
                    "🔒 Trial/Paid: all 144 NGX stocks"],
        "cta":     "Create Free Account →",
    },
    "free_daily_cap": {
        "title":   "Daily Signal Limit Reached",
        "bullets": ["✅ You've seen your 5 free signals today",
                    "🔒 Trial: all signals, real-time",
                    "🔒 Starter+: unlimited + entry/exit/target",
                    "🔒 Pro: advanced AI narrative & strategy"],
        "cta":     "Start Free 14-Day Trial →",
    },
    "card_entry_exit": {
        "title":   "🔒 Unlock Entry / Target / Stop-Loss",
        "bullets": ["✅ You can see signal direction & score",
                    "🔒 Entry price, target & stop-loss on Starter+",
                    "🔒 Real-time signals, no 3-min delay"],
        "cta":     "Start Free Trial →",
    },
    "card_full_narrative": {
        "title":   "🔒 Unlock Full AI Reasoning",
        "bullets": ["✅ You can see price & score bars",
                    "🔒 Complete signal analysis on Starter+",
                    "🔒 Advanced AI narrative on Pro"],
        "cta":     "Unlock Full AI Reasoning →",
    },
    "card_pro_narrative": {
        "title":   "⭐ Pro: Advanced Signal Analysis",
        "bullets": ["🔒 Strategy context & sector rotation",
                    "🔒 Portfolio-level positioning advice",
                    "🔒 Risk/reward ratios & position sizing"],
        "cta":     "Upgrade to Pro →",
    },
}


def get_user_tier() -> str:
    """
    Derive canonical tier from session state.
    Returns one of: visitor | free | trial | starter | trader | pro
    """
    user    = st.session_state.get("user")
    profile = st.session_state.get("profile", {})
    if not user:
        return "visitor"
    plan = (profile.get("plan") or "free").lower().strip()
    return plan if plan in ("free","trial","starter","trader","pro") else "free"


def _tier_rank(tier: str) -> int:
    try:    return TIER_ORDER.index(tier)
    except: return 0


def can_access(feature: str, tier: str | None = None) -> bool:
    """Return True if the tier can access the given feature."""
    t   = tier or get_user_tier()
    req = _FEATURE_MIN_TIER.get(feature, "visitor")
    return _tier_rank(t) >= _tier_rank(req)


def get_usage_limit(feature: str = "signals", tier: str | None = None) -> int | None:
    """Return daily usage limit. None = unlimited. 0 = no access."""
    t = tier or get_user_tier()
    if feature == "signals":
        return _DAILY_SIGNAL_LIMITS.get(t, 0)
    return None


def render_locked_content(
    feature: str,
    key: str,
    upgrade_page: str = "settings",
    compact: bool = False,
) -> None:
    """
    Render the standard feature gate. compact=True for inline card use.
    """
    copy  = _LOCK_COPY.get(feature, {"title":"🔒 Upgrade Required",
                                      "bullets":["Higher plan required."],
                                      "cta":"Upgrade →"})
    tier  = get_user_tier()
    req   = _FEATURE_MIN_TIER.get(feature, "starter")

    if compact:
        st.markdown(f"""
<div style="background:rgba(240,165,0,.05);border:1px solid rgba(240,165,0,.18);
            border-left:3px solid #F0A500;border-radius:8px;padding:10px 14px;
            margin:8px 0;font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;">
  🔒 {copy['title']}
</div>""", unsafe_allow_html=True)
        if st.button(copy["cta"], key=key, type="primary"):
            st.session_state.current_page = upgrade_page; st.rerun()
        return

    items_html = "".join(f'<li style="margin-bottom:5px;">{b}</li>' for b in copy["bullets"])
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0C0C00,#100A00);
            border:1px solid rgba(240,165,0,.3);border-radius:12px;
            padding:20px 22px;margin:16px 0;text-align:center;">
  <div style="font-size:22px;margin-bottom:8px;">🔒</div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:700;
              color:#F0A500;margin-bottom:10px;">{copy['title']}</div>
  <ul style="font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;text-align:left;
             display:inline-block;margin-bottom:14px;list-style:none;padding:0;">{items_html}</ul>
  <div style="font-family:'DM Mono',monospace;font-size:10px;color:#404040;margin-top:2px;">
    Your plan: <strong style="color:#808080;">{tier.upper()}</strong>
    &nbsp;·&nbsp; Required: <strong style="color:#F0A500;">{req.upper()}+</strong>
  </div>
</div>""", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        if st.button(copy["cta"], key=key, type="primary", use_container_width=True):
            st.session_state.current_page = upgrade_page; st.rerun()


def _tier_badge(tier: str) -> str:
    colors = {"visitor":"#606060","free":"#808080","trial":"#22C55E",
              "starter":"#3B82F6","trader":"#A78BFA","pro":"#F0A500"}
    c = colors.get(tier, "#606060")
    return (f'<span style="background:{c}1A;border:1px solid {c}55;border-radius:4px;'
            f'padding:2px 7px;font-family:DM Mono,monospace;font-size:9px;font-weight:700;'
            f'color:{c};text-transform:uppercase;letter-spacing:.08em;">{tier}</span>')


# ── Session-based daily signal view counter (free users) ─────────────────────

def _get_signals_viewed_today() -> int:
    return st.session_state.get(f"sig_viewed_{str(__import__('datetime').date.today())}", 0)

def _increment_signals_viewed():
    k = f"sig_viewed_{str(__import__('datetime').date.today())}"
    st.session_state[k] = st.session_state.get(k, 0) + 1

def _signals_remaining(tier: str) -> tuple[int | None, bool]:
    """(remaining, is_capped). remaining=None means unlimited."""
    limit = get_usage_limit("signals", tier)
    if limit is None: return None, False
    used  = _get_signals_viewed_today()
    rem   = max(0, limit - used)
    return rem, rem == 0


# ══════════════════════════════════════════════════════════════════════════════
# NARRATIVE GENERATOR  (unchanged from original — pure data, no tier logic)
# ══════════════════════════════════════════════════════════════════════════════

def generate_signal_narrative(
    symbol: str,
    signal_code: str,
    stars: int,
    price: float,
    chg: float,
    volume: int,
    momentum: float,
    vol_score: float,
    composite: float,
    db_reasoning: str = "",
) -> str:
    if db_reasoning and len(db_reasoning.strip()) > 120:
        return db_reasoning.strip()

    if price <= 0:
        return (
            f"No price data has been recorded for {symbol} yet. "
            f"This stock exists on the NGX but the scraper has not yet "
            f"collected its pricing data — this typically happens for "
            f"low-liquidity or recently listed equities. "
            f"It will appear with full analysis on the next successful market data run."
        )

    abs_chg   = abs(chg)
    is_gain   = chg >= 0
    arrow     = "▲" if is_gain else "▼"
    chg_str   = "{:+.2f}".format(chg)
    price_str = "₦{:,.2f}".format(price)
    m_pct     = int(min(momentum,  1.0) * 100)
    v_pct     = int(min(vol_score, 1.0) * 100)
    c_pct     = int(min(composite, 1.0) * 100)
    vol_str   = "{:,}".format(volume) if volume > 0 else "N/A"

    if m_pct >= 75:
        mom_line = (f"Momentum is strong at {m_pct}% — buyers have been in control "
                    f"across recent sessions, with consistent upward pressure on the price.")
    elif m_pct >= 50:
        mom_line = (f"Momentum reads {m_pct}% — solidly positive. "
                    f"The stock has been trending in the right direction, "
                    f"with more up-days than down-days in recent trading.")
    elif m_pct >= 30:
        mom_line = (f"Momentum is moderate at {m_pct}%. "
                    f"Price action has been mixed — some sessions up, some flat, "
                    f"suggesting the market is still forming a view on {symbol}.")
    else:
        mom_line = (f"Momentum is weak at {m_pct}%. "
                    f"Recent sessions have shown little upward conviction, "
                    f"and price has been drifting or declining.")

    if v_pct >= 75:
        vol_line = (f"Volume is significantly above average ({v_pct}% score) — "
                    f"{vol_str} shares changed hands today. "
                    f"When volume surges like this, it usually means real money is moving, "
                    f"not just noise.")
    elif v_pct >= 50:
        vol_line = (f"Trading volume is above average ({v_pct}% score, {vol_str} shares). "
                    f"More participants than usual are engaging with {symbol} today, "
                    f"which adds weight to the current price move.")
    elif v_pct >= 25:
        vol_line = (f"Volume is around average ({v_pct}% score, {vol_str} shares). "
                    f"A normal crowd — enough for the move to be real, "
                    f"but not a standout conviction day.")
    else:
        vol_line = (f"Volume is thin ({v_pct}% score, {vol_str} shares). "
                    f"Few participants traded {symbol} today. "
                    f"Moves on low volume are easier to reverse — treat with caution.")

    if abs_chg >= 9.5 and is_gain:
        move_line = (f"{symbol} hit the NGX daily ceiling today, surging {chg_str}% to {price_str}. "
                     f"Buyers so dominated that the exchange had to cap the move. "
                     f"Something significant — news, earnings, or a large order — triggered this.")
    elif abs_chg >= 9.5 and not is_gain:
        move_line = (f"{symbol} hit the NGX daily floor, falling {chg_str}% to {price_str}. "
                     f"Sellers flooded out and the exchange's circuit breaker kicked in. "
                     f"Watch for the catalyst — this level of selling rarely happens without cause.")
    elif abs_chg >= 5 and is_gain:
        move_line = (f"{symbol} gained {chg_str}% today to close at {price_str} — "
                     f"a strong single-session move. "
                     f"This kind of gain on the NGX reflects real conviction, not just routine trading.")
    elif abs_chg >= 5 and not is_gain:
        move_line = (f"{symbol} fell {chg_str}% to {price_str} — a sharp pull-back. "
                     f"Sellers have taken control and the stock is giving back recent gains. "
                     f"The question is whether this is profit-taking or a shift in sentiment.")
    elif abs_chg >= 2 and is_gain:
        move_line = (f"{symbol} moved up {chg_str}% to {price_str}. "
                     f"A meaningful but measured gain — the kind that suggests steady "
                     f"buyer interest rather than speculative excitement.")
    elif abs_chg >= 2 and not is_gain:
        move_line = (f"{symbol} slipped {chg_str}% to {price_str}. "
                     f"A moderate dip — sellers nudging the price lower to attract buyers. "
                     f"Not a crisis, but worth watching for follow-through.")
    else:
        move_line = (f"{symbol} barely moved today ({chg_str}%) and is currently priced at {price_str}. "
                     f"The market is taking a breath — no strong push in either direction.")

    if signal_code == "STRONG_BUY":
        verdict = (f"With {stars} stars and a composite score of {c_pct}%, "
                   f"this is one of the highest-conviction signals on the NGX today. "
                   f"All three scoring dimensions — momentum, volume, and composite — "
                   f"are aligned. The risk/reward at current levels is favourable for "
                   f"investors with a medium-term horizon.")
    elif signal_code == "BUY":
        verdict = (f"This is a BUY signal with {stars} stars and a composite score of {c_pct}%. "
                   f"The setup is positive: momentum is building and volume is supporting the move. "
                   f"Wait for the market to open and confirm the trend before entering.")
    elif signal_code == "BREAKOUT_WATCH":
        verdict = (f"A BREAKOUT WATCH signal with {stars} stars — the stock is approaching "
                   f"a level where a decisive move is likely. "
                   f"Composite score sits at {c_pct}%. "
                   f"Watch for volume expansion as confirmation: if the next session "
                   f"brings higher volume alongside a price push, that is your green light.")
    elif signal_code == "HOLD":
        verdict = (f"The signal is HOLD ({stars} stars, composite {c_pct}%). "
                   f"There is no urgent reason to buy or sell — "
                   f"the stock is in a neutral zone. "
                   f"Existing holders should stay patient; new buyers should wait "
                   f"for a cleaner entry or stronger signal.")
    elif signal_code == "CAUTION":
        verdict = (f"CAUTION is warranted here ({stars} stars, composite {c_pct}%). "
                   f"The data shows deteriorating conditions — weakening momentum "
                   f"or declining volume behind recent moves. "
                   f"Tighten stop-losses if you hold, and avoid new positions until "
                   f"conditions improve.")
    elif signal_code == "AVOID":
        verdict = (f"This stock is rated AVOID ({stars} star, composite {c_pct}%). "
                   f"All scoring dimensions point negative. "
                   f"There is no technical case for a new position at this time. "
                   f"Let the stock stabilise and build a new base before reconsidering.")
    else:
        verdict = (f"Composite score: {c_pct}%. "
                   f"Review the score breakdown below before making any decision.")

    lead = ""
    if db_reasoning and len(db_reasoning.strip()) > 10:
        lead = db_reasoning.strip().rstrip(".") + ". "

    return lead + move_line + " " + mom_line + " " + vol_line + " " + verdict


def _generate_pro_addendum(
    symbol: str,
    signal_code: str,
    price: float,
    entry_price: float | None,
    target_price: float | None,
    stop_loss: float | None,
    momentum: float,
    vol_score: float,
    composite: float,
) -> str:
    """
    Pro-exclusive addendum: strategy context, sector positioning, risk/reward framing.
    Only called when tier == 'pro'.
    """
    m_pct = int(min(momentum, 1.0) * 100)
    c_pct = int(min(composite, 1.0) * 100)

    rr_text = ""
    if entry_price and target_price and stop_loss and entry_price > 0:
        reward = target_price - entry_price
        risk   = entry_price - stop_loss
        rr     = round(reward / risk, 2) if risk > 0 else 0
        rr_text = (f"Risk/Reward: {rr}:1 — "
                   f"{'favourable setup' if rr >= 2 else 'moderate setup' if rr >= 1.5 else 'tight setup'}. ")

    if signal_code in ("STRONG_BUY", "BUY"):
        strategy = (f"Portfolio context: {symbol} fits a momentum-led position. "
                    f"Composite alignment at {c_pct}% suggests institutional interest. "
                    f"Consider sizing up to 3–5% of portfolio if the sector is also trending positively. "
                    f"{rr_text}"
                    f"Momentum at {m_pct}% — confirm on the open before committing full size.")
    elif signal_code == "BREAKOUT_WATCH":
        strategy = (f"Breakout setup: {symbol} is at a technical inflection point. "
                    f"A staged entry — partial on the break, remainder on confirmed volume — "
                    f"limits risk if the breakout fails. "
                    f"{rr_text}"
                    f"Set alerts at the breakout level. Composite {c_pct}% supports the thesis.")
    elif signal_code == "HOLD":
        strategy = (f"Portfolio management: {symbol} is range-bound with composite at {c_pct}%. "
                    f"No urgency to act. If held, maintain position and review on next scoring cycle. "
                    f"If watching from the sidelines, wait for a cleaner signal before entry.")
    else:  # CAUTION / AVOID
        strategy = (f"Risk management: {symbol} shows deteriorating composite at {c_pct}%. "
                    f"If holding, consider reducing exposure or tightening stop-losses. "
                    f"Avoid new positions until conditions stabilise. "
                    f"Momentum at {m_pct}% confirms the cautious stance.")

    return strategy


# ══════════════════════════════════════════════════════════════════════════════
# TIER-AWARE SIGNAL CARD RENDERER
# ══════════════════════════════════════════════════════════════════════════════

def _render_signal_card(
    *,
    s: dict,
    price_map: dict,
    tier: str,
    alerts_by_symbol: dict,
    sb,
    user,
    plan: str,
    card_index: int,
) -> None:
    """
    Renders one signal card with tier-appropriate detail level.
    Visitor → label-only row (no expander).
    Free     → expander with score bars only, no entry/exit, no reasoning.
    Starter+ → full card with entry/exit and reasoning.
    Pro      → full card + pro strategy addendum.
    """
    symbol     = s.get("symbol", "")
    stars_num  = int(s.get("stars", 3))
    signal_raw = s.get("signal", "HOLD")
    reasoning  = s.get("reasoning", "") or ""
    score_date = s.get("score_date", "")

    signal_code = signal_raw.upper().replace(" ", "_")
    cfg = SIGNAL_CONFIG.get(signal_code, DEFAULT_CONFIG)
    accent, stars_display, label = cfg

    price_data = price_map.get(symbol, {})
    price  = float(price_data.get("price", 0) or 0)
    chg    = float(price_data.get("change_percent", 0) or 0)
    volume = int(price_data.get("volume", 0) or 0)
    chg_color = "#22C55E" if chg >= 0 else "#EF4444"
    arrow     = "▲" if chg >= 0 else "▼"

    momentum  = float(s.get("momentum_score", 0) or 0)
    vol_score = float(s.get("volume_score", 0) or 0)
    composite = float(s.get("news_score", 0) or 0)

    m_pct = int(min(momentum,  1.0) * 100)
    v_pct = int(min(vol_score, 1.0) * 100)
    c_pct = int(min(composite, 1.0) * 100)

    price_display = f"₦{price:,.2f}" if price > 0 else "No price data"
    vol_display   = f"Vol: {volume:,}" if volume > 0 else ""

    db_short = reasoning.strip()
    db_short_display = db_short if len(db_short) <= 140 else db_short[:137] + "…"

    # Entry / Target / Stop Loss — only calculated if tier can show them
    entry_price = target_price = stop_loss = potential = None
    if can_access("card_entry_exit", tier) and signal_code in ("STRONG_BUY", "BUY", "BREAKOUT_WATCH") and price > 0:
        entry_price  = round(price * 1.002, 2)
        multiplier   = 1.12 if stars_num >= 5 else 1.08 if stars_num >= 4 else 1.06
        target_price = round(price * multiplier, 2)
        stop_loss    = round(price * 0.95, 2)
        potential    = round(((target_price - entry_price) / entry_price) * 100, 1)

    # Rich narrative — only for starter+
    rich_narrative = ""
    if can_access("card_full_narrative", tier):
        rich_narrative = generate_signal_narrative(
            symbol=symbol, signal_code=signal_code, stars=stars_num,
            price=price, chg=chg, volume=volume,
            momentum=momentum, vol_score=vol_score, composite=composite,
            db_reasoning=db_short,
        )

    # Pro addendum
    pro_narrative = ""
    if can_access("card_pro_narrative", tier):
        pro_narrative = _generate_pro_addendum(
            symbol=symbol, signal_code=signal_code, price=price,
            entry_price=entry_price, target_price=target_price,
            stop_loss=stop_loss, momentum=momentum,
            vol_score=vol_score, composite=composite,
        )

    # Push notification (runs regardless of tier, deduplicated internally)
    maybe_push_signal(symbol=symbol, signal_code=signal_code,
                      narrative=rich_narrative or db_short or label,
                      price=price, chg=chg)

    # ── VISITOR: minimal row only, no expander ────────────────────────────────
    if tier == "visitor":
        st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;
            padding:10px 14px;margin-bottom:6px;font-family:'DM Mono',monospace;">
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="font-family:'Space Grotesk',sans-serif;font-size:14px;
                 font-weight:700;color:#FFFFFF;">{symbol}</span>
    <span style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:12px;
                 background:{accent}22;color:{accent};text-transform:uppercase;">{label}</span>
    <span style="font-size:11px;color:#4B5563;">{stars_display}</span>
  </div>
  <div style="display:flex;align-items:center;gap:12px;">
    <span style="font-size:12px;font-weight:600;color:{chg_color};">{arrow} {abs(chg):.2f}%</span>
    <span style="font-size:12px;color:#808080;">{price_display}</span>
  </div>
</div>""", unsafe_allow_html=True)
        return

    # ── FREE: expander with score bars, no entry/exit/reasoning ──────────────
    # ── STARTER+: full expander ───────────────────────────────────────────────

    # 3-min delay badge for free users
    delay_badge = ""
    if tier == "free":
        delay_badge = ' <span style="font-size:9px;background:#1A1200;border:1px solid #3D2E00;color:#F0A500;padding:1px 6px;border-radius:3px;margin-left:6px;">⏱ ~3 min delay</span>'

    with st.expander(
        f"{stars_display}  {symbol}  —  {label}  ·  {price_display}"
        f"  {_bell_label(symbol, alerts_by_symbol)}",
        expanded=False
    ):
        # ── Height estimation ─────────────────────────────────────────────
        CHARS_PER_LINE = 55
        def est_height(text: str, font_px: int = 11, lh: float = 1.75) -> int:
            if not text: return 0
            lines = max(1, len(text) // CHARS_PER_LINE + text.count("\n"))
            return int(lines * font_px * lh) + 10

        h_badge     = 30
        h_delay     = 20 if tier == "free" else 0
        h_db_short  = est_height(db_short_display, 11, 1.55) if (db_short_display and can_access("card_reasoning_short", tier)) else 0
        h_action    = 90 if entry_price else 0
        h_scores    = 70
        h_narrative = est_height(rich_narrative, 11, 1.75) if rich_narrative else 0
        h_pro       = est_height(pro_narrative, 11, 1.65) + 30 if pro_narrative else 0
        h_lock_cta  = 80 if not can_access("card_full_narrative", tier) else 0
        h_disclaimer = 24
        h_padding   = 40

        card_height = (h_badge + h_delay + h_db_short + h_action +
                       h_scores + h_narrative + h_pro + h_lock_cta +
                       h_disclaimer + h_padding)
        card_height = max(280, min(card_height, 1400))

        # ── Action grid HTML (shown only for starter+) ────────────────────
        action_grid_html = ""
        if entry_price and target_price and stop_loss:
            action_grid_html = f"""
<div class="action-grid">
  <div class="action-cell" style="background:#001A00;border:1px solid #003D00;">
    <div class="action-lbl">&#10003; Entry</div>
    <div class="action-val" style="color:#22C55E;">&#8358;{entry_price:,.2f}</div>
  </div>
  <div class="action-cell" style="background:#001A1A;border:1px solid #003D3D;">
    <div class="action-lbl">&#127919; Target</div>
    <div class="action-val" style="color:#22D3EE;">&#8358;{target_price:,.2f}</div>
    <div class="action-sub" style="color:#22D3EE;">+{potential}%</div>
  </div>
  <div class="action-cell" style="background:#1A0000;border:1px solid #3D0000;">
    <div class="action-lbl">&#128721; Stop Loss</div>
    <div class="action-val" style="color:#EF4444;">&#8358;{stop_loss:,.2f}</div>
  </div>
</div>"""

        # ── Locked entry/exit placeholder for free ────────────────────────
        locked_action_html = ""
        if tier == "free" and signal_code in ("STRONG_BUY", "BUY", "BREAKOUT_WATCH") and price > 0:
            locked_action_html = f"""
<div style="background:#0C0800;border:1px solid rgba(240,165,0,.2);border-radius:7px;
            padding:10px 12px;margin:8px 0;text-align:center;font-family:DM Mono,monospace;font-size:11px;color:#606060;">
  🔒 Entry · Target · Stop-Loss — <span style="color:#F0A500;">Starter plan or above</span>
</div>"""

        # ── Narrative HTML ────────────────────────────────────────────────
        narrative_html = ""
        if rich_narrative:
            narrative_html = f'<div class="narrative">{rich_narrative}</div>'
        elif tier == "free":
            narrative_html = f"""
<div style="background:#0A0C0F;border:1px solid #1E2229;border-left:3px solid #F0A500;
            border-radius:7px;padding:10px 12px;margin-top:8px;font-family:DM Mono,monospace;
            font-size:11px;color:#4B5563;">
  🔒 Full AI reasoning — <span style="color:#F0A500;">Start a free trial to unlock complete analysis</span>
</div>"""

        # ── Pro addendum HTML ─────────────────────────────────────────────
        pro_html = ""
        if pro_narrative:
            pro_html = f"""
<div style="background:linear-gradient(135deg,#0A0800,#080A00);
            border:1px solid rgba(240,165,0,.25);border-left:3px solid #F0A500;
            border-radius:7px;padding:10px 12px;margin-top:8px;
            font-family:DM Mono,monospace;font-size:11px;color:#D0C090;line-height:1.7;">
  <div style="font-size:9px;color:#F0A500;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px;">
    ⭐ PRO · Strategy Context
  </div>
  {pro_narrative}
</div>"""

        # ── DB short text HTML ────────────────────────────────────────────
        db_html = ""
        if db_short_display and can_access("card_reasoning_short", tier):
            db_html = f'<div class="db-text">{db_short_display}</div>'

        # ── Delay badge HTML ──────────────────────────────────────────────
        delay_html = f'<div style="font-family:DM Mono,monospace;font-size:10px;color:#F0A500;background:#1A1200;border:1px solid #3D2E00;border-radius:4px;padding:3px 8px;margin-bottom:8px;display:inline-block;">⏱ Showing ~3-minute delayed data · Upgrade for real-time</div>' if tier == "free" else ""

        st.components.v1.html(f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
  html {{ font-size:13px; }}
  body {{
    background:transparent;
    font-family:'DM Mono',monospace;
    color:#E8E2D4;
    overflow-x:hidden;
    overflow-y:visible;
    padding:4px 0 10px 0;
  }}
  .badge-row {{ display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px; }}
  .signal-badge {{ font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:0.05em;color:#fff;background:{accent}; }}
  .chg-val {{ font-size:12px;font-weight:600;color:{chg_color}; }}
  .vol-val {{ font-size:10px;color:#4B5563; }}
  .date-val {{ font-size:10px;color:#374151;margin-left:auto; }}
  .db-text {{ font-size:11px;color:#9CA3AF;line-height:1.55;margin-bottom:8px; }}
  .action-grid {{ display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:8px 0; }}
  .action-cell {{ border-radius:7px;padding:9px 6px;text-align:center; }}
  .action-lbl {{ font-size:9px;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px;color:#4B5563; }}
  .action-val {{ font-size:15px;font-weight:500; }}
  .action-sub {{ font-size:10px;margin-top:2px; }}
  .scores {{ margin:8px 0 0 0;padding-top:8px;border-top:1px solid #1E2229; }}
  .scores-title {{ font-size:9px;color:#4B5563;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:7px; }}
  .scores-grid {{ display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px; }}
  .score-lbl {{ font-size:9px;color:#4B5563;margin-bottom:4px; }}
  .bar-track {{ background:#1A1D24;border-radius:4px;height:4px;margin-bottom:2px; }}
  .bar-fill {{ border-radius:4px;height:4px; }}
  .score-num {{ font-size:10px; }}
  .narrative {{ background:#0A0C0F;border:1px solid #1E2229;border-left:3px solid {accent};border-radius:7px;padding:10px 12px;font-size:11px;color:#E8E2D4;line-height:1.75;margin-top:8px; }}
  .disclaimer {{ font-size:9px;color:#374151;margin-top:8px;padding-top:6px;border-top:1px solid #1A1D24; }}
  @media(max-width:400px) {{ html {{ font-size:12px; }} .action-val {{ font-size:13px; }} }}
</style>
<script>
  function resize() {{
    var h = document.body.scrollHeight + 16;
    window.parent.postMessage({{type:'streamlit:setFrameHeight',height:h}},'*');
  }}
  window.addEventListener('load', function(){{ resize(); setTimeout(resize,600); }});
  new MutationObserver(resize).observe(document.body,{{subtree:true,childList:true}});
</script>
</head>
<body>

  <!-- Badge row -->
  <div class="badge-row">
    <span class="signal-badge">{label}</span>
    <span class="chg-val">{arrow} {abs(chg):.2f}% today</span>
    {'<span class="vol-val">' + vol_display + '</span>' if vol_display else ''}
    <span class="date-val">{score_date}</span>
  </div>

  <!-- Delay badge (free only) -->
  {delay_html}

  <!-- Short DB reasoning (starter+) -->
  {db_html}

  <!-- Entry / Target / Stop Loss (starter+) -->
  {action_grid_html}

  <!-- Locked placeholder (free, bullish signals only) -->
  {locked_action_html}

  <!-- Score bars (free+) -->
  {'<div class="scores"><div class="scores-title">Score Breakdown</div><div class="scores-grid"><div><div class="score-lbl">Momentum</div><div class="bar-track"><div class="bar-fill" style="background:#F0A500;width:' + str(m_pct) + '%;"></div></div><div class="score-num" style="color:#F0A500;">' + str(m_pct) + '%</div></div><div><div class="score-lbl">Volume</div><div class="bar-track"><div class="bar-fill" style="background:#22D3EE;width:' + str(v_pct) + '%;"></div></div><div class="score-num" style="color:#22D3EE;">' + str(v_pct) + '%</div></div><div><div class="score-lbl">Composite</div><div class="bar-track"><div class="bar-fill" style="background:#A78BFA;width:' + str(c_pct) + '%;"></div></div><div class="score-num" style="color:#A78BFA;">' + str(c_pct) + '%</div></div></div></div>' if can_access("card_score_bars", tier) else ''}

  <!-- Full narrative (starter+) or locked notice (free) -->
  {narrative_html}

  <!-- Pro strategy addendum -->
  {pro_html}

  <!-- Disclaimer -->
  <div class="disclaimer">
    &#9888;&#65039; Signal scores are educational only — not financial advice. Always do your own research.
  </div>

</body>
</html>
""", height=card_height, scrolling=True)

        # ── Inline upgrade CTAs inside expander ───────────────────────────
        if tier == "free":
            st.markdown("""
<div style="background:rgba(240,165,0,.05);border:1px solid rgba(240,165,0,.18);
            border-left:3px solid #F0A500;border-radius:8px;
            padding:10px 14px;margin:8px 0;font-family:'DM Mono',monospace;
            font-size:12px;color:#B0B0B0;">
  🔒 <strong style="color:#F0A500;">Unlock full AI reasoning</strong>
  — entry price, target, stop-loss, and complete analysis.
  Start a free 14-day trial.
</div>""", unsafe_allow_html=True)
            if st.button("🚀 Unlock Full AI Reasoning →",
                         key=f"unlock_reasoning_{symbol}_{card_index}",
                         type="primary", use_container_width=True):
                st.session_state.current_page = "settings"; st.rerun()

        elif not can_access("card_entry_exit", tier):
            # trial user (has narrative but not necessarily entry/exit — trial has it)
            pass

        # Alert widget (starter+)
        if can_access("alert_widget", tier):
            render_alert_widget(sb, user, plan, symbol, price, alerts_by_symbol)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render():
    sb   = get_supabase()
    tier = get_user_tier()

    profile          = st.session_state.get("profile", {})
    plan             = profile.get("plan", "free")
    user             = st.session_state.get("user")
    alerts_by_symbol = load_user_alerts(sb, user)

    # ── PAGE CSS ──────────────────────────────────────────────────────────────
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700;800&display=swap');
.sig-header{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:800;color:#E8E2D4;margin-bottom:4px;}
.sig-sub{font-family:'DM Mono',monospace;font-size:11px;color:#4B5563;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:20px;}
.sig-count{font-family:'DM Mono',monospace;font-size:12px;color:#6B7280;margin-bottom:12px;}
.tier-info-bar{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:10px 16px;
               margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;
               font-family:'DM Mono',monospace;font-size:12px;gap:12px;flex-wrap:wrap;}
</style>
""", unsafe_allow_html=True)

    # ── HEADER ────────────────────────────────────────────────────────────────
    st.markdown(f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:4px;">
  <div>
    <div class="sig-header">⭐ Signal Scores</div>
    <div class="sig-sub">AI-powered buy/sell/hold ratings — all NGX stocks</div>
  </div>
  <div style="padding-top:4px;">{_tier_badge(tier)}</div>
</div>
""", unsafe_allow_html=True)

    # ── TIER STATUS BAR ────────────────────────────────────────────────────────
    _rem, _capped = _signals_remaining(tier)
    if tier == "visitor":
        bar_msg  = "👁 Visitor preview — showing 3 sample signals. Create a free account for more."
        bar_cta  = ("Create Free Account →", "settings")
    elif tier == "free" and not _capped:
        bar_msg  = f"Free plan — {_rem} of 5 signal views remaining today · 3-min delay · No entry/exit data"
        bar_cta  = ("Start Free Trial for Full Access →", "settings")
    elif tier == "free" and _capped:
        bar_msg  = "Free plan — daily signal limit reached. Upgrade for unlimited access."
        bar_cta  = ("Start Free Trial →", "settings")
    elif tier == "trial":
        bar_msg  = "✨ Trial — full access · Real-time signals · Entry/exit/target included"
        bar_cta  = None
    elif tier == "starter":
        bar_msg  = "Starter — Real-time · Entry/exit/target · Full reasoning"
        bar_cta  = ("Upgrade to Trader for Priority Signals →", "settings")
    elif tier == "trader":
        bar_msg  = "Trader — Priority signals · Unlimited · All details"
        bar_cta  = ("Upgrade to Pro for Advanced Analysis →", "settings")
    else:  # pro
        bar_msg  = "⭐ Pro — Priority signals · Advanced AI narrative · Strategy context"
        bar_cta  = None

    cta_html = ""
    if bar_cta:
        cta_html = f'<span style="color:#F0A500;font-size:11px;white-space:nowrap;">{bar_cta[0]}</span>'

    st.markdown(f"""
<div class="tier-info-bar">
  <span style="color:#9CA3AF;">{bar_msg}</span>
  {cta_html}
</div>
""", unsafe_allow_html=True)

    if bar_cta:
        # Invisible button wired to the CTA text above
        if st.button(bar_cta[0], key="tier_bar_cta", type="secondary"):
            st.session_state.current_page = bar_cta[1]; st.rerun()

    # ── FILTERS (all tiers see filters — data is always shown) ────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_signal = st.selectbox(
            "Filter by signal",
            ["All","STRONG BUY","BUY","BREAKOUT WATCH","HOLD","CAUTION","AVOID"],
            key="sig_filter"
        )
    with col2:
        _sort_options = ["Signal strength ↓","Best % gain today",
                         "Worst % loss today","Highest volume","Symbol A–Z"]
        if tier in ("trader","pro"):
            _sort_options = ["Priority signals ↓"] + _sort_options
        sort_by = st.selectbox("Sort by", _sort_options, key="sig_sort")
    with col3:
        search = st.text_input(
            "Search symbol", placeholder="e.g. GTCO", key="sig_search"
        ).upper().strip()

    # ── FETCH DATA ────────────────────────────────────────────────────────────
    scores_res = sb.table("signal_scores")\
        .select("*")\
        .order("score_date", desc=True)\
        .order("stars", desc=True)\
        .limit(500).execute()

    prices_res = sb.table("stock_prices")\
        .select("symbol,price,change_percent,volume")\
        .order("trading_date", desc=True)\
        .limit(500).execute()

    price_map = {}
    for p in (prices_res.data or []):
        if p["symbol"] not in price_map:
            price_map[p["symbol"]] = p

    seen = set(); all_scores = []
    for s in (scores_res.data or []):
        if s["symbol"] not in seen:
            seen.add(s["symbol"]); all_scores.append(s)

    label_to_code = {
        "STRONG BUY":"STRONG_BUY","BUY":"BUY","BREAKOUT WATCH":"BREAKOUT_WATCH",
        "HOLD":"HOLD","CAUTION":"CAUTION","AVOID":"AVOID",
    }

    # ── APPLY FILTERS ─────────────────────────────────────────────────────────
    filtered = all_scores[:]
    if filter_signal != "All":
        code = label_to_code.get(filter_signal, filter_signal)
        filtered = [s for s in filtered
                    if s.get("signal","").upper().replace(" ","_") == code
                    or s.get("signal","") == filter_signal]
    if search:
        filtered = [s for s in filtered if search in s.get("symbol","")]

    # ── SORT ─────────────────────────────────────────────────────────────────
    if sort_by == "Priority signals ↓":
        # Trader/Pro: sort by SIGNAL_PRIORITY rank, then stars desc
        def _priority_key(x):
            sc = x.get("signal","HOLD").upper().replace(" ","_")
            rank = SIGNAL_PRIORITY.index(sc) if sc in SIGNAL_PRIORITY else 99
            return (rank, -int(x.get("stars",3)))
        filtered = sorted(filtered, key=_priority_key)
    elif sort_by == "Best % gain today":
        filtered = sorted(filtered, key=lambda x:float(price_map.get(x["symbol"],{}).get("change_percent",0) or 0), reverse=True)
    elif sort_by == "Worst % loss today":
        filtered = sorted(filtered, key=lambda x:float(price_map.get(x["symbol"],{}).get("change_percent",0) or 0))
    elif sort_by == "Highest volume":
        filtered = sorted(filtered, key=lambda x:int(price_map.get(x["symbol"],{}).get("volume",0) or 0), reverse=True)
    elif sort_by == "Symbol A–Z":
        filtered = sorted(filtered, key=lambda x:x.get("symbol",""))

    # ── DISTRIBUTION BAR (data always shown) ──────────────────────────────────
    if all_scores:
        color_map = {
            "STRONG_BUY":"#16A34A","STRONG BUY":"#16A34A","BUY":"#22C55E",
            "BREAKOUT_WATCH":"#3B82F6","BREAKOUT WATCH":"#3B82F6",
            "HOLD":"#D97706","CAUTION":"#EA580C","AVOID":"#DC2626",
        }
        dist = {}
        for s in all_scores:
            sig = s.get("signal","HOLD"); dist[sig] = dist.get(sig,0) + 1
        parts = []
        for sig,cnt in sorted(dist.items(), key=lambda x:-x[1]):
            c = color_map.get(sig,"#6B7280")
            parts.append(f"<span style='color:{c};font-weight:600;'>{sig}</span>"
                         f" <span style='color:#4B5563;'>{cnt}</span>")
        st.markdown(
            "<div style='font-family:DM Mono,monospace;font-size:12px;margin-bottom:16px;"
            "display:flex;gap:16px;flex-wrap:wrap;'>"
            + " &nbsp;·&nbsp; ".join(parts) + "</div>",
            unsafe_allow_html=True
        )

    # ── APPLY TIER LIMIT TO LIST LENGTH ───────────────────────────────────────
    limit      = get_usage_limit("signals", tier)
    is_visitor = tier == "visitor"

    # Visitor always sees max 3, regardless of filter
    if is_visitor:
        display_list = filtered[:3]
        show_limit_wall = len(filtered) > 3
    elif tier == "free":
        # Free: cap at daily remaining
        rem, capped = _signals_remaining(tier)
        if capped:
            display_list     = []
            show_limit_wall  = True
        else:
            display_list    = filtered[:rem] if rem is not None else filtered
            show_limit_wall = len(filtered) > (rem or 0)
    else:
        display_list    = filtered
        show_limit_wall = False

    # Signal count line
    if is_visitor:
        count_note = f"Showing <strong style='color:#F0A500;'>3</strong> of {len(filtered)} signals (visitor preview)"
    elif tier == "free":
        _r,_c = _signals_remaining(tier)
        if _c:
            count_note = "Daily limit reached — <strong style='color:#EF4444;'>0</strong> signals remaining"
        else:
            count_note = (f"Showing <strong style='color:#F0A500;'>{len(display_list)}</strong> signals "
                          f"— <strong style='color:#808080;'>{_r}</strong> remaining today (free plan)")
    else:
        count_note = f"Showing <strong style='color:#F0A500;'>{len(display_list)}</strong> stocks"

    st.markdown(f"<div class='sig-count'>{count_note}</div>", unsafe_allow_html=True)

    if not filtered:
        st.info("No signals match your filter.")
        return

    # ── RENDER SIGNAL CARDS ───────────────────────────────────────────────────
    for card_idx, s in enumerate(display_list):
        # Increment free user counter on each card render
        if tier == "free":
            _increment_signals_viewed()

        _render_signal_card(
            s=s,
            price_map=price_map,
            tier=tier,
            alerts_by_symbol=alerts_by_symbol,
            sb=sb,
            user=user,
            plan=plan,
            card_index=card_idx,
        )

    # ── GATE WALL (after exhausting free/visitor allowance) ───────────────────
    if show_limit_wall:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if is_visitor:
            render_locked_content("signals_full_list", "lock_signals_visitor")
        else:
            render_locked_content("free_daily_cap", "lock_signals_free")

    # ── UPGRADE CTA BAR (bottom of page, for lower tiers) ─────────────────────
    if tier in ("visitor","free"):
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("""
<div style="background:linear-gradient(135deg,#1A1600,#2A2200);border:1px solid #3D2E00;
            border-radius:12px;padding:20px 24px;">
  <div style="font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;
              color:#F0A500;margin-bottom:8px;">🔒 Unlock Full AI Reasoning</div>
  <div style="font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;line-height:1.7;">
    Start a free 14-day trial and instantly unlock:
    entry price · target · stop-loss · complete AI narrative · real-time signals · all 144 NGX stocks
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        lbl = "Create Free Account →" if is_visitor else "Start Free 14-Day Trial →"
        if st.button(lbl, key="signals_bottom_cta", type="primary"):
            st.session_state.current_page = "settings"; st.rerun()

    elif tier == "starter":
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown("""
<div style="background:#0A0A0A;border:1px solid rgba(167,139,250,.2);border-radius:10px;
            padding:14px 18px;font-family:'DM Mono',monospace;font-size:12px;color:#808080;">
  📈 <strong style="color:#A78BFA;">Trader plan</strong> — unlock priority signals, 
  pre-market alerts &amp; Telegram notifications.
  &nbsp; <strong style="color:#F0A500;">Pro plan</strong> — adds advanced AI strategy context &amp; portfolio-level recommendations.
</div>""", unsafe_allow_html=True)
