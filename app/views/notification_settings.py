import os
import streamlit as st
from app.utils.supabase_client import get_supabase

TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_USERNAME", "NGXSignalBot")
PAID_PLANS   = {"starter", "trader", "pro"}


# ── Shared UI helpers ─────────────────────────────────────────────────────────

def _badge(on: bool) -> str:
    if on:
        return ("<span style='display:inline-block;font-size:10px;font-weight:700;"
                "padding:2px 10px;border-radius:999px;text-transform:uppercase;"
                "letter-spacing:.05em;background:rgba(34,197,94,.12);color:#22C55E;"
                "border:1px solid rgba(34,197,94,.25);margin-left:8px;'>Active</span>")
    return ("<span style='display:inline-block;font-size:10px;font-weight:700;"
            "padding:2px 10px;border-radius:999px;text-transform:uppercase;"
            "letter-spacing:.05em;background:rgba(107,114,128,.12);color:#6B7280;"
            "border:1px solid rgba(107,114,128,.25);margin-left:8px;'>Off</span>")


def _card(html: str, accent: str = "#1E2229") -> str:
    return (f"<div style='background:#10131A;border:1px solid #1E2229;"
            f"border-left:3px solid {accent};border-radius:12px;"
            f"padding:16px 18px;margin-bottom:10px;"
            f"font-family:DM Mono,monospace;'>{html}</div>")


def _section_label(text: str) -> str:
    return (f"<div style='font-family:DM Mono,monospace;font-size:10px;"
            f"font-weight:700;color:#6B7280;text-transform:uppercase;"
            f"letter-spacing:.1em;margin:18px 0 8px 0;'>{text}</div>")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render():
    sb      = get_supabase()
    profile = st.session_state.get("profile", {})
    user    = st.session_state.get("user")
    plan    = profile.get("plan", "free")
    uid     = profile.get("id", "")
    is_paid = plan in PAID_PLANS

    # ── Font import ───────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
    </style>
    """, unsafe_allow_html=True)

    # ── Page header ───────────────────────────────────
    st.markdown("""
    <div style='font-family:Syne,sans-serif;font-size:22px;font-weight:800;
                color:#E8E2D4;margin-bottom:4px;'>⚙️ Settings</div>
    <div style='font-family:DM Mono,monospace;font-size:11px;color:#6B7280;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:20px;'>
        Manage your account and preferences
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["👤 Profile", "💳 Plan", "🔔 Notifications"])

    # ══════════════════════════════════════════════════
    # TAB 1 — PROFILE
    # ══════════════════════════════════════════════════
    with tab1:
        st.markdown(_section_label("Personal Details"), unsafe_allow_html=True)

        full_name = st.text_input(
            "Full name",
            value=profile.get("full_name", "") or "",
            key="set_name"
        )
        st.text_input(
            "Email address",
            value=user.email if user else "",
            disabled=True,
            key="set_email"
        )
        phone = st.text_input(
            "Phone number",
            value=profile.get("phone_whatsapp", "") or "",
            placeholder="+2348012345678",
            key="set_phone"
        )

        current_lang = profile.get("brief_language", "en") or "en"
        use_pidgin = st.toggle(
            "🇳🇬 Receive briefs in Pidgin English",
            value=(current_lang == "pg"),
            key="set_pidgin"
        )

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        if st.button("Save Profile", key="save_profile", type="primary",
                     use_container_width=True):
            try:
                sb.table("profiles").update({
                    "full_name":      full_name,
                    "phone_whatsapp": phone,
                    "brief_language": "pg" if use_pidgin else "en",
                }).eq("id", uid).execute()
                st.session_state.profile["full_name"]      = full_name
                st.session_state.profile["phone_whatsapp"] = phone
                st.session_state.profile["brief_language"] = "pg" if use_pidgin else "en"
                st.success("✅ Profile updated!")
            except Exception as e:
                st.error(f"Could not update profile: {e}")

    # ══════════════════════════════════════════════════
    # TAB 2 — PLAN
    # ══════════════════════════════════════════════════
    with tab2:
        plan_colors = {
            "free":    "#6B7280",
            "starter": "#2563EB",
            "trader":  "#7C3AED",
            "pro":     "#F0A500",
        }
        plan_color = plan_colors.get(plan, "#6B7280")

        # Current plan card
        st.markdown(
            f"<div style='background:#10131A;border:2px solid {plan_color};"
            f"border-radius:14px;padding:20px 22px;margin-bottom:18px;'>"
            f"<div style='font-family:DM Mono,monospace;font-size:10px;"
            f"color:#6B7280;text-transform:uppercase;letter-spacing:.08em;'>"
            f"Current plan</div>"
            f"<div style='font-family:Syne,sans-serif;font-size:26px;"
            f"font-weight:800;color:{plan_color};text-transform:uppercase;"
            f"margin:4px 0 6px 0;'>{plan}</div>"
            f"<div style='font-family:DM Mono,monospace;font-size:12px;color:#9CA3AF;'>"
            f"{'Upgrade to unlock instant signals and more features.' if plan == 'free' else 'Thank you for being a subscriber!'}"
            f"</div></div>",
            unsafe_allow_html=True
        )

        if plan == "free":
            plans_data = [
                ("Starter", "₦3,500/mo", "#2563EB", [
                    "Daily AI morning brief",
                    "10 watchlist stocks",
                    "5 price alerts/month",
                    "Investment simulator",
                    "Telegram brief delivery",
                ]),
                ("Trader", "₦8,000/mo", "#7C3AED", [
                    "30 stocks watchlist",
                    "Unlimited price alerts",
                    "Ask AI (30 queries/month)",
                    "Pidgin English briefs",
                    "Priority Telegram delivery",
                ]),
                ("Pro", "₦18,000/mo", "#F0A500", [
                    "Unlimited everything",
                    "PDF intelligence reports",
                    "Unlimited Ask AI",
                    "Evening market close brief",
                    "Early access to new features",
                ]),
            ]
            for pname, price, pcolor, features in plans_data:
                feats_html = "".join(
                    f"<div style='font-family:DM Mono,monospace;font-size:12px;"
                    f"color:#E8E2D4;padding:3px 0;'>"
                    f"<span style='color:{pcolor};margin-right:6px;'>✓</span>{f}</div>"
                    for f in features
                )
                st.markdown(
                    f"<div style='background:#10131A;border:1px solid {pcolor}33;"
                    f"border-top:3px solid {pcolor};border-radius:12px;"
                    f"padding:16px 18px;margin-bottom:10px;'>"
                    f"<div style='display:flex;justify-content:space-between;"
                    f"align-items:center;margin-bottom:10px;'>"
                    f"<span style='font-family:Syne,sans-serif;font-weight:800;"
                    f"font-size:16px;color:{pcolor};'>{pname}</span>"
                    f"<span style='font-family:DM Mono,monospace;font-weight:500;"
                    f"font-size:15px;color:#E8E2D4;'>{price}</span>"
                    f"</div>{feats_html}</div>",
                    unsafe_allow_html=True
                )

            st.markdown(
                "<div style='background:#10131A;border:1px solid #3D2800;"
                "border-left:3px solid #F0A500;border-radius:10px;"
                "padding:14px 16px;font-family:DM Mono,monospace;"
                "font-size:12px;color:#D97706;line-height:1.6;'>"
                "💳 Paystack integration coming soon. "
                "Contact us on Telegram to upgrade manually for now."
                "</div>",
                unsafe_allow_html=True
            )

    # ══════════════════════════════════════════════════
    # TAB 3 — NOTIFICATIONS & ALERTS
    # ══════════════════════════════════════════════════
    with tab3:

        push_on   = bool(profile.get("push_alerts_enabled",  True))
        email_on  = bool(profile.get("email_alerts_enabled", False))
        tg_joined = bool(profile.get("telegram_joined",      False))
        tg_handle = profile.get("telegram_username") or profile.get("telegram_user_id")

        st.markdown(
            "<div style='font-family:DM Mono,monospace;font-size:11px;color:#6B7280;"
            "text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px;'>"
            "Manage how NGX Signal reaches you</div>",
            unsafe_allow_html=True
        )

        # ── PUSH ─────────────────────────────────────
        st.markdown(_card(
            f"<div style='font-family:Syne,sans-serif;font-size:15px;"
            f"font-weight:700;color:#E8E2D4;margin-bottom:5px;'>"
            f"Push Notifications{_badge(push_on)}</div>"
            f"<div style='font-size:12px;color:#E8E2D4;line-height:1.6;'>"
            f"Browser push alerts for every new signal. "
            f"{'Instant delivery on your premium plan.' if is_paid else '3-minute delay on free plan.'}"
            f"</div>",
            accent="#F0A500"
        ), unsafe_allow_html=True)

        new_push = st.toggle("Enable push notifications", value=push_on, key="tog_push")
        if new_push != push_on:
            try:
                sb.table("profiles").update({"push_alerts_enabled": new_push}).eq("id", uid).execute()
                st.session_state.profile["push_alerts_enabled"] = new_push
                st.success(f"Push notifications {'enabled' if new_push else 'disabled'}")
                st.rerun()
            except Exception as e:
                st.error(f"Save error: {e}")

        # ── TELEGRAM ─────────────────────────────────
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        tg_link = (
            f"https://t.me/{TELEGRAM_BOT}?start=premium_{uid}"
            if is_paid else
            f"https://t.me/{TELEGRAM_BOT}?start=free"
        )
        st.markdown(_card(
            f"<div style='font-family:Syne,sans-serif;font-size:15px;"
            f"font-weight:700;color:#E8E2D4;margin-bottom:5px;'>"
            f"Telegram Channel{_badge(tg_joined)}</div>"
            f"<div style='font-size:12px;color:#E8E2D4;line-height:1.6;'>"
            f"{'Private premium channel — instant signals with entry/target/stop-loss.' if is_paid else 'Free public channel — delayed signals. Upgrade for the private premium channel.'}"
            f"</div>",
            accent="#229ED9"
        ), unsafe_allow_html=True)

        tg_c1, tg_c2 = st.columns(2)
        with tg_c1:
            btn_label = "Join Private Channel" if is_paid else "Join Free Channel"
            if st.button(btn_label, key="tg_join", type="primary",
                         use_container_width=True):
                try:
                    sb.table("profiles").update(
                        {"telegram_joined": True}
                    ).eq("id", uid).execute()
                    st.session_state.profile["telegram_joined"] = True
                except Exception:
                    pass
                st.success(f"[Open Telegram]({tg_link})")

        with tg_c2:
            if tg_handle:
                st.markdown(
                    f"<div style='font-family:DM Mono,monospace;font-size:12px;"
                    f"color:#22C55E;padding:10px 0;'>"
                    f"@{str(tg_handle).lstrip('@')} linked ✅</div>",
                    unsafe_allow_html=True
                )
            else:
                inp = st.text_input(
                    "Your Telegram username",
                    placeholder="@yourusername",
                    key="tg_id_inp"
                )
                if st.button("Link Account", key="tg_link_btn"):
                    raw = (inp or "").strip().lstrip("@")
                    if raw:
                        try:
                            sb.table("profiles").update({
                                "telegram_username": raw,
                                "telegram_joined":   True,
                            }).eq("id", uid).execute()
                            st.session_state.profile["telegram_username"] = raw
                            st.session_state.profile["telegram_joined"]   = True
                            st.success("Telegram linked!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("Enter your Telegram username (e.g. @johntrader)")

        # ── EMAIL DIGEST ─────────────────────────────
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        st.markdown(_card(
            f"<div style='font-family:Syne,sans-serif;font-size:15px;"
            f"font-weight:700;color:#E8E2D4;margin-bottom:5px;'>"
            f"Email Digest{_badge(email_on)}</div>"
            f"<div style='font-size:12px;color:#E8E2D4;line-height:1.6;'>"
            f"Weekly market summary every Monday 8AM WAT — "
            f"top movers, sectors, and missed signals.</div>",
            accent="#374151"
        ), unsafe_allow_html=True)

        new_email = st.toggle("Enable email digest", value=email_on, key="tog_email")
        if new_email != email_on:
            try:
                sb.table("profiles").update(
                    {"email_alerts_enabled": new_email}
                ).eq("id", uid).execute()
                st.session_state.profile["email_alerts_enabled"] = new_email
                st.success(f"Email digest {'enabled' if new_email else 'disabled'}")
                st.rerun()
            except Exception as e:
                st.error(f"Save error: {e}")

        # ── PRICE ALERTS ─────────────────────────────
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        st.markdown(_card(
            f"<div style='font-family:Syne,sans-serif;font-size:15px;"
            f"font-weight:700;color:#E8E2D4;margin-bottom:5px;'>"
            f"Price Alerts{_badge(is_paid)}</div>"
            f"<div style='font-size:12px;color:#E8E2D4;line-height:1.6;'>"
            f"{'Get notified via Telegram + push the moment any stock hits your target price.' if is_paid else 'Set target prices and get instant alerts when stocks move. Starter plan and above.'}"
            f"</div>",
            accent="#22C55E"
        ), unsafe_allow_html=True)

        if is_paid:
            try:
                alert_res = sb.table("price_alerts") \
                    .select("id", count="exact") \
                    .eq("user_id", uid) \
                    .eq("is_active", True) \
                    .execute()
                alert_count = alert_res.count or 0
            except Exception:
                alert_count = 0

            st.markdown(
                f"<div style='font-family:DM Mono,monospace;font-size:12px;"
                f"color:#22C55E;padding:4px 0 8px 0;'>"
                f"🔔 {alert_count} active alert{'s' if alert_count != 1 else ''} — "
                f"set and manage them from Signal Scores or All Live Stocks.</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("Upgrade to Enable Price Alerts →",
                         key="alert_upgrade_tab", use_container_width=True):
                st.info("👆 See the Plan tab above to view upgrade options.")

        # ── ALERT DELIVERY SCHEDULE ───────────────────
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        with st.expander("📅 Alert Delivery Schedule", expanded=False):
            st.markdown(
                "<div style='font-family:DM Mono,monospace;font-size:12px;"
                "color:#E8E2D4;line-height:2.1;'>"
                "<strong style='color:#9CA3AF;'>Free</strong>"
                " — 3-min delay · public Telegram · no trade levels<br>"
                "<strong style='color:#F0A500;'>Premium</strong>"
                " — instant · private Telegram · entry / target / stop · push<br>"
                "<strong style='color:#22C55E;'>Price Alerts</strong>"
                " — fired immediately via Telegram DM + push<br>"
                "<strong style='color:#E8E2D4;'>Weekly Digest</strong>"
                " — Monday 8AM WAT · email + Telegram"
                "</div>",
                unsafe_allow_html=True
            )

        # ── UPGRADE NUDGE (free users only) ──────────
        if not is_paid:
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            st.markdown(
                "<div style='background:linear-gradient(135deg,#1A1600,#2A2200);"
                "border:1px solid #4D3800;border-radius:12px;"
                "padding:18px 22px;text-align:center;'>"
                "<div style='font-family:Syne,sans-serif;font-size:17px;"
                "font-weight:700;color:#F0A500;margin-bottom:8px;'>"
                "Never Miss Another Trade</div>"
                "<div style='font-family:DM Mono,monospace;font-size:12px;"
                "color:#E8E2D4;line-height:1.65;'>"
                "Premium users receive signals instantly with full entry, target, and stop-loss. "
                "Free users wait 3 minutes and receive no trade details."
                "</div></div>",
                unsafe_allow_html=True
            )
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.button(
                "Upgrade for Instant Alerts — from ₦3,500/mo",
                key="notif_upgrade",
                type="primary",
                use_container_width=True
            ):
                st.info("👆 Head to the Plan tab above to see all upgrade options.")

    # ══════════════════════════════════════════════════
    # SIGN OUT
    # ══════════════════════════════════════════════════
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<hr style='border:none;border-top:1px solid #1E2229;margin-bottom:14px;'>",
        unsafe_allow_html=True
    )
    if st.button("🚪 Sign Out", key="settings_signout", use_container_width=True):
        sb.auth.sign_out()
        st.session_state.user          = None
        st.session_state.profile       = {}
        st.session_state.current_page  = "home"
        st.rerun()
