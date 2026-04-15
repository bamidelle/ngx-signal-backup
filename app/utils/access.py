"""
NGX Signal — Access Level System
===================================
Single source of truth for feature gating across the entire app.

TIER HIERARCHY
──────────────
visitor   — no account. Sees landing page, live prices (no details), signal labels only
free      — registered, trial expired. Basic access, persistent upgrade nudges
trial     — registered, within 14-day trial. Full premium access, trial countdown
starter   — paid ₦3,500/mo. Full signals + alerts + Telegram
trader    — paid ₦8,000/mo. Everything + Ask AI unlimited
pro       — paid ₦18,000/mo. Everything + PDF reports + admin tools

CHESS.COM ANALOGY
──────────────────
visitor → play online without account (see board, can't use analysis)
free    → logged in, trial expired (see premium but locked with upgrade prompt)
trial   → logged in, within free trial (full experience, countdown banner)
starter → member (unlocked core features)
trader  → diamond member (all features)
pro     → diamond + coaching (everything + extras)

USAGE
──────
from app.utils.access import get_access, can, ACCESS

access = get_access()          # reads from st.session_state
if can("signals_detail"):      # check a specific feature
    show_entry_target_stoploss()
else:
    show_upgrade_prompt("signals_detail")

SUPABASE COLUMN REQUIRED
─────────────────────────
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS trial_expires_at timestamptz;

Set on signup via auth.py:
  trial_expires_at = now() + interval '14 days'
"""

import streamlit as st
from datetime import datetime, timezone


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE → MINIMUM TIER MAP
# Lower index = more restricted. Order: visitor(0) < free(1) < trial(2) < starter(3) < trader(4) < pro(5)
# ══════════════════════════════════════════════════════════════════════════════
TIER_RANK = {
    "visitor": 0,
    "free":    1,
    "trial":   2,
    "starter": 3,
    "trader":  4,
    "pro":     5,
}

# feature_key → minimum tier required to access it
FEATURE_TIERS: dict[str, str] = {
    # ── Visible to everyone ──────────────────────────────────────────
    "live_prices":          "visitor",   # stock list with price & % change
    "signal_labels":        "visitor",   # BUY / HOLD / AVOID label visible
    "market_ai_page":       "visitor",   # Market AI landing page (limited)
    "market_ai_queries":    "visitor",   # AI chat (3 queries/day for visitors)

    # ── Requires registration (free or trial) ────────────────────────
    "signals_detail":       "free",      # entry/target/stop-loss on signals
    "score_breakdown":      "free",      # momentum/volume/composite bars
    "rich_narrative":       "free",      # full AI narrative on signals
    "morning_brief":        "free",      # morning brief content (limited)
    "price_alerts_view":    "free",      # see alert page (can't set alerts)
    "watchlist":            "free",      # personal watchlist
    "trade_game":           "free",      # paper trading simulator
    "learn_hub":            "free",      # learning modules
    "calculator":           "free",      # investment calculator
    "dividends":            "free",      # dividend tracker
    "calendar":             "free",      # earnings calendar
    "settings":             "free",      # account settings
    "notifications":        "free",      # notification settings

    # ── Requires active trial OR paid plan ───────────────────────────
    "price_alerts_set":     "trial",     # actually set a price alert
    "telegram_join":        "trial",     # join Telegram channel
    "push_notifications":   "trial",     # push notification delivery
    "ai_queries_unlimited": "trial",     # unlimited AI chat queries
    "evening_brief":        "trial",     # evening close brief

    # ── Starter+ ─────────────────────────────────────────────────────
    "instant_signals":      "starter",   # signals without 3-min delay
    "signal_full_detail":   "starter",   # entry/target/stop on ALL signals
    "price_alerts_5":       "starter",   # up to 5 alerts/month
    "telegram_private":     "starter",   # private premium Telegram channel
    "weekly_digest":        "starter",   # weekly email digest

    # ── Trader+ ──────────────────────────────────────────────────────
    "ask_ai_full":          "trader",    # full Ask AI (30 queries/mo)
    "price_alerts_unlimited":"trader",   # unlimited price alerts
    "pidgin_briefs":        "trader",    # Pidgin English briefs
    "watchlist_30":         "trader",    # up to 30 watchlist stocks

    # ── Pro only ─────────────────────────────────────────────────────
    "pdf_reports":          "pro",       # PDF intelligence reports
    "evening_brief_full":   "pro",       # full evening close brief
    "ask_ai_unlimited":     "pro",       # unlimited Ask AI queries
    "admin_dashboard":      "pro",       # admin tools (+ is_admin flag)
    "early_access":         "pro",       # early access to new features
}


# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTION — call this everywhere
# ══════════════════════════════════════════════════════════════════════════════

def get_access() -> str:
    """
    Compute the current user's access tier from session state.
    Returns one of: 'visitor' | 'free' | 'trial' | 'starter' | 'trader' | 'pro'

    Call this once per page render and cache in a local variable:
        access = get_access()
    """
    user    = st.session_state.get("user")
    profile = st.session_state.get("profile", {})

    if not user:
        return "visitor"

    plan = (profile.get("plan") or "free").lower().strip()

    # Paid plans take priority — return immediately
    if plan in ("starter", "trader", "pro"):
        return plan

    # Free or unknown plan — check trial status
    trial_expires = profile.get("trial_expires_at")
    if trial_expires:
        try:
            # Parse ISO string; handle both with and without timezone
            if isinstance(trial_expires, str):
                exp = datetime.fromisoformat(
                    trial_expires.replace("Z", "+00:00")
                )
            else:
                exp = trial_expires
            # Ensure timezone aware
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < exp:
                return "trial"
        except Exception:
            pass

    return "free"


def can(feature: str, access: str = None) -> bool:
    """
    Returns True if the given access tier can use the feature.

    access: pass the result of get_access() to avoid re-computing.
            If None, calls get_access() automatically.

    Example:
        access = get_access()
        if can("signals_detail", access):
            show_full_signal()
    """
    if access is None:
        access = get_access()
    min_tier  = FEATURE_TIERS.get(feature, "pro")   # unknown features default to pro
    return TIER_RANK.get(access, 0) >= TIER_RANK.get(min_tier, 5)


def trial_days_remaining(profile: dict = None) -> int:
    """Returns days left in trial, or 0 if trial expired/not started."""
    if profile is None:
        profile = st.session_state.get("profile", {})
    trial_expires = profile.get("trial_expires_at")
    if not trial_expires:
        return 0
    try:
        if isinstance(trial_expires, str):
            exp = datetime.fromisoformat(trial_expires.replace("Z", "+00:00"))
        else:
            exp = trial_expires
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        delta = exp - datetime.now(timezone.utc)
        return max(0, delta.days)
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# UPGRADE PROMPT COMPONENTS — contextual, conversion-optimised
# ══════════════════════════════════════════════════════════════════════════════

# Context → copy mapping
_UPGRADE_COPY = {
    "signals_detail": {
        "hook":    "🔒 Entry price, target & stop-loss are Premium",
        "body":    "You can see the signal. Premium members also see exactly where to enter, their target, and where to cut losses.",
        "cta":     "Unlock Full Signal →",
        "urgency": "Start free 14-day trial",
    },
    "ai_queries": {
        "hook":    "✨ You've used your 3 free AI queries today",
        "body":    "Premium members get unlimited AI market analysis — ask about any NGX stock, sector, or market event.",
        "cta":     "Unlock Unlimited AI →",
        "urgency": "From ₦3,500/mo",
    },
    "price_alerts_set": {
        "hook":    "🔔 Price alerts are a Premium feature",
        "body":    "Get notified instantly via Telegram + push the moment a stock hits your target price.",
        "cta":     "Unlock Price Alerts →",
        "urgency": "Start free 14-day trial",
    },
    "telegram": {
        "hook":    "✈️ Private Telegram Channel is Premium",
        "body":    "Premium members receive instant signals with entry/target/stop-loss directly in Telegram.",
        "cta":     "Join Premium Channel →",
        "urgency": "From ₦3,500/mo",
    },
    "morning_brief": {
        "hook":    "🌅 Full Morning Brief is Premium",
        "body":    "Free users see a summary. Premium members get the complete analysis with sector breakdown and top picks.",
        "cta":     "Unlock Full Brief →",
        "urgency": "Start free 14-day trial",
    },
    "pdf_reports": {
        "hook":    "📄 PDF Reports are Pro-only",
        "body":    "Weekly deep-dive reports covering sector trends, top movers, and missed signals — formatted as professional PDFs.",
        "cta":     "Upgrade to Pro →",
        "urgency": "₦18,000/mo · Cancel anytime",
    },
    "default": {
        "hook":    "🔒 This is a Premium Feature",
        "body":    "Create a free account to start your 14-day trial and unlock full access to NGX Signal.",
        "cta":     "Start Free Trial →",
        "urgency": "No credit card required · 14 days free",
    },
}


def render_upgrade_prompt(
    context:    str  = "default",
    compact:    bool = False,
    nav_key:    str  = "",
) -> None:
    """
    Render a contextual upgrade prompt.

    context:  key from _UPGRADE_COPY above
    compact:  True = small inline banner, False = full card
    nav_key:  unique suffix for button key to avoid duplicate widget keys

    Example:
        render_upgrade_prompt("signals_detail", compact=True, nav_key="sig_01")
    """
    copy   = _UPGRADE_COPY.get(context, _UPGRADE_COPY["default"])
    suffix = nav_key or context

    if compact:
        # ── Inline banner (used inside cards) ────────────────────────────────
        st.markdown(
            f"<div style='background:#0A0800;border:1px solid #3D2800;"
            f"border-radius:8px;padding:10px 14px;margin:8px 0;"
            f"display:flex;align-items:center;justify-content:space-between;"
            f"flex-wrap:wrap;gap:8px;'>"
            f"<div style='font-family:DM Mono,monospace;font-size:12px;"
            f"color:#F0A500;'>{copy['hook']}</div>"
            f"<div style='font-family:DM Mono,monospace;font-size:11px;"
            f"color:#A0A0A0;'>{copy['urgency']}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        if st.button(copy["cta"], key=f"upg_compact_{suffix}",
                     type="primary", use_container_width=True):
            navigate_to_upgrade()

    else:
        # ── Full gate card ────────────────────────────────────────────────────
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#0A0800,#150F00);"
            f"border:1px solid #3D2800;border-radius:14px;"
            f"padding:28px 24px;text-align:center;max-width:520px;margin:24px auto;"
            f"box-shadow:0 0 30px rgba(240,165,0,0.08);'>"
            f"<div style='font-size:36px;margin-bottom:10px;'>🔒</div>"
            f"<div style='font-family:Space Grotesk,sans-serif;font-size:18px;"
            f"font-weight:800;color:#F0A500;margin-bottom:10px;'>{copy['hook']}</div>"
            f"<div style='font-family:DM Mono,monospace;font-size:13px;"
            f"color:#FFFFFF;line-height:1.7;margin-bottom:6px;'>{copy['body']}</div>"
            f"<div style='font-family:DM Mono,monospace;font-size:11px;"
            f"color:#666666;margin-top:8px;'>{copy['urgency']}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        c1, c2 = st.columns([3, 2])
        with c1:
            if st.button(copy["cta"], key=f"upg_full_{suffix}",
                         type="primary", use_container_width=True):
                navigate_to_upgrade()
        with c2:
            if st.button("Sign in instead", key=f"upg_signin_{suffix}",
                         use_container_width=True):
                st.session_state.show_auth = True
                st.rerun()


def render_trial_banner(days_left: int) -> None:
    """
    Show a sticky trial countdown banner for trial-tier users.
    Call at the top of every page for trial users.
    """
    if days_left <= 0:
        return
    urgency_color = "#EF4444" if days_left <= 3 else \
                    "#F0A500" if days_left <= 7 else "#22C55E"
    st.markdown(
        f"<div style='background:#0A0800;border:1px solid {urgency_color}44;"
        f"border-left:3px solid {urgency_color};border-radius:8px;"
        f"padding:10px 16px;margin-bottom:12px;"
        f"display:flex;align-items:center;justify-content:space-between;"
        f"flex-wrap:wrap;gap:8px;'>"
        f"<div style='font-family:DM Mono,monospace;font-size:12px;color:{urgency_color};'>"
        f"⏳ Free trial — <strong>{days_left} day{'s' if days_left != 1 else ''} remaining</strong>"
        f"</div>"
        f"<div style='font-family:DM Mono,monospace;font-size:11px;color:#666666;'>"
        f"Upgrade to keep full access after trial ends</div>"
        f"</div>",
        unsafe_allow_html=True
    )


def navigate_to_upgrade() -> None:
    """Navigate to the settings/upgrade page."""
    st.session_state.current_page = "settings"
    st.session_state.submenu_open = False
    st.rerun()
