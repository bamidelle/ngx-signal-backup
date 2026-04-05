"""
NGX Signal — Inline Alert Widget
─────────────────────────────────
Drop-in helper used by both all_stocks.py and signals.py.

Usage
-----
1. At the top of render():
        from app.components.inline_alert_widget import load_user_alerts, render_alert_widget
        alerts_by_symbol = load_user_alerts(sb, user)

2. Inside each stock expander, after the chart/signal content:
        render_alert_widget(sb, user, plan, symbol, current_price, alerts_by_symbol)

The function mutates `alerts_by_symbol` on save so the bell badge
updates immediately without a full page rerun.
"""

import streamlit as st
from app.utils.supabase_client import get_supabase   # noqa – imported by callers

PAID_PLANS = {"starter", "trader", "pro"}


# ── HELPERS ──────────────────────────────────────────────────────────────

def _bell_label(symbol: str, alerts_by_symbol: dict) -> str:
    """Return a bell emoji with optional count badge for expander labels."""
    count = len(alerts_by_symbol.get(symbol, []))
    if count == 0:
        return "🔔"
    return f"🔔 {count}"


def load_user_alerts(sb, user) -> dict:
    """
    Fetch all active alerts for the current user and return a dict:
        { symbol: [ alert_row, ... ] }
    Returns an empty dict if user is None.
    """
    if not user:
        return {}
    try:
        res = sb.table("price_alerts") \
            .select("*") \
            .eq("user_id", user.id) \
            .eq("is_active", True) \
            .execute()
        by_sym: dict = {}
        for row in (res.data or []):
            sym = row.get("symbol", "")
            by_sym.setdefault(sym, []).append(row)
        return by_sym
    except Exception:
        return {}


# ── MAIN WIDGET ──────────────────────────────────────────────────────────

def render_alert_widget(
    sb,
    user,
    plan: str,
    symbol: str,
    current_price: float,
    alerts_by_symbol: dict,
):
    """
    Renders the inline alert panel at the bottom of a stock expander.

    • Paid users  → see existing alerts + a compact set-new-alert form
    • Free users  → see a short upgrade nudge (no form)
    • Logged-out  → nothing shown
    """
    is_paid = plan in PAID_PLANS
    existing = alerts_by_symbol.get(symbol, [])
    count    = len(existing)
    uid      = user.id if user else None

    # Divider
    st.markdown(
        "<div style='border-top:1px solid #1E2229;margin:16px 0 12px 0;'></div>",
        unsafe_allow_html=True,
    )

    # ── Bell header ──────────────────────────────────
    bell_html = (
        "<div style='display:flex;align-items:center;gap:10px;margin-bottom:10px;'>"
        "<span style='font-size:16px;'>🔔</span>"
        "<span style='font-family:Syne,sans-serif;font-size:14px;font-weight:700;"
        "color:#E8E2D4;'>Price Alerts</span>"
    )
    if count:
        bell_html += (
            f"<span style='background:#F0A500;color:#000;font-size:10px;"
            f"font-weight:700;padding:2px 8px;border-radius:999px;"
            f"margin-left:4px;'>{count} active</span>"
        )
    bell_html += "</div>"
    st.markdown(bell_html, unsafe_allow_html=True)

    # ── Free plan gate ───────────────────────────────
    if not is_paid:
        st.markdown(
            "<div style='background:#1A1000;border:1px solid #3D2800;"
            "border-radius:8px;padding:12px 14px;font-family:DM Mono,monospace;"
            "font-size:12px;color:#D97706;line-height:1.6;'>"
            "⚡ <strong style='color:#F0A500;'>Price alerts are a Starter+ feature.</strong><br>"
            "Upgrade to get notified instantly via Telegram when any stock hits your target."
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "Upgrade for Price Alerts →",
            key=f"alert_upgrade_{symbol}",
            use_container_width=True,
        ):
            st.session_state.current_page = "settings"
            st.rerun()
        return

    if not uid:
        return

    # ── Existing alerts for this stock ───────────────
    if existing:
        for alert in existing:
            tp   = float(alert.get("target_price", 0))
            atyp = alert.get("alert_type", "above")
            arrow = "↑" if atyp == "above" else "↓"
            diff  = abs(current_price - tp)
            dist_pct = (diff / current_price * 100) if current_price > 0 else 0
            aid  = alert.get("id")

            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(
                    f"<div style='font-family:DM Mono,monospace;font-size:12px;"
                    f"color:#E8E2D4;padding:6px 0;'>"
                    f"Alert when <strong style='color:#F0A500;'>{arrow} ₦{tp:,.2f}</strong>"
                    f" &nbsp;·&nbsp; <span style='color:#6B7280;'>"
                    f"₦{diff:,.2f} away ({dist_pct:.1f}%)</span></div>",
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("✕", key=f"del_alert_{symbol}_{aid}", help="Remove alert"):
                    try:
                        sb.table("price_alerts") \
                            .update({"is_active": False}) \
                            .eq("id", aid).execute()
                        alerts_by_symbol[symbol] = [
                            a for a in existing if a.get("id") != aid
                        ]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not remove alert: {e}")

    # ── Set new alert form ────────────────────────────
    with st.expander("＋ Set new alert", expanded=(count == 0)):
        fc1, fc2, fc3 = st.columns([2, 2, 1])
        with fc1:
            direction = st.selectbox(
                "Direction",
                ["goes above ↑", "goes below ↓"],
                key=f"adir_{symbol}",
                label_visibility="collapsed",
            )
        with fc2:
            default_tp = (
                round(current_price * 1.05, 2)
                if "above" in direction
                else round(current_price * 0.95, 2)
            ) if current_price > 0 else 1.0
            target = st.number_input(
                "Target (₦)",
                min_value=0.01,
                value=default_tp,
                format="%.2f",
                key=f"atp_{symbol}",
                label_visibility="collapsed",
            )
        with fc3:
            if st.button("Set 🔔", key=f"set_alert_{symbol}", type="primary",
                         use_container_width=True):
                try:
                    sb.table("price_alerts").insert({
                        "user_id":      uid,
                        "symbol":       symbol,
                        "target_price": target,
                        "alert_type":   "above" if "above" in direction else "below",
                        "is_active":    True,
                    }).execute()
                    # Refresh local cache so bell badge updates immediately
                    new_alerts = load_user_alerts(sb, user)
                    alerts_by_symbol.update(new_alerts)
                    st.success(
                        f"🔔 Alert set: {symbol} {direction} ₦{target:,.2f}"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not set alert: {e}")

        if current_price > 0:
            st.markdown(
                f"<div style='font-family:DM Mono,monospace;font-size:10px;"
                f"color:#4B5563;margin-top:4px;'>Current price: ₦{current_price:,.2f}</div>",
                unsafe_allow_html=True,
            )
