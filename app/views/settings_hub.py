"""
NGX Signal — Settings Hub
Unified settings: Account, Notifications, Plan, Admin access.
Replaces the separate notifications and old settings pages.
"""
import os
import streamlit as st
from app.utils.supabase_client import get_supabase

TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_USERNAME", "NGXSignalBot")
PAID_PLANS   = {"starter", "trader", "pro"}
ADMIN_EMAIL  = os.environ.get("ADMIN_EMAIL", "aybamibello@gmail.com")


def _card(content, accent="#1F1F1F"):
    return (f"<div style='background:#0A0A0A;border:1px solid {accent};"
            f"border-radius:12px;padding:18px 20px;margin-bottom:12px;"
            f"font-family:DM Mono,monospace;animation:ngx-fade-in .4s ease both;'>"
            f"{content}</div>")


def _section(title, icon):
    st.markdown(
        f"<div style='font-family:Space Grotesk,sans-serif;font-size:16px;"
        f"font-weight:700;color:#FFFFFF;margin:24px 0 12px;'>"
        f"{icon} {title}</div>",
        unsafe_allow_html=True
    )


def render():
    sb      = get_supabase()
    profile = st.session_state.get("profile", {})
    user    = st.session_state.get("user")
    plan    = profile.get("plan", "free")
    uid     = profile.get("id", "")
    email   = profile.get("email", "")
    is_paid = plan in PAID_PLANS
    is_admin= email == ADMIN_EMAIL

    st.markdown("""
    <div style='font-family:Space Grotesk,sans-serif;font-size:22px;font-weight:800;
                color:#FFFFFF;margin-bottom:4px;'>⚙️ Settings</div>
    <div style='font-family:DM Mono,monospace;font-size:11px;color:#808080;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:24px;'>
        Account · Notifications · Plan · Alerts
    </div>
    """, unsafe_allow_html=True)

    # ── TABS ──────────────────────────────────────────
    tabs = st.tabs(["👤 Account", "🔔 Notifications", "💳 Plan", "🔔 Price Alerts"])

    # ══════════════════════════════════════════════════
    # TAB 1 — ACCOUNT
    # ══════════════════════════════════════════════════
    with tabs[0]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(_card(
            f"<div style='font-size:13px;color:#FFFFFF;'>"
            f"<strong>Name:</strong> {profile.get('full_name','—')}<br>"
            f"<strong>Email:</strong> {email or '—'}<br>"
            f"<strong>Plan:</strong> <span style='color:#F0A500;font-weight:700;text-transform:uppercase;'>{plan}</span><br>"
            f"<strong>Member since:</strong> {profile.get('created_at','—')[:10] if profile.get('created_at') else '—'}"
            f"</div>",
            accent="rgba(240,165,0,0.2)"
        ), unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        new_name = st.text_input("Display name", value=profile.get("full_name",""), key="acc_name")
        if st.button("Save Name", key="save_name", type="primary"):
            try:
                sb.table("profiles").update({"full_name": new_name}).eq("id", uid).execute()
                st.session_state.profile["full_name"] = new_name
                st.success("✅ Name updated!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        if is_admin:
            st.markdown(
                "<div style='background:rgba(240,165,0,0.08);border:1px solid rgba(240,165,0,0.3);"
                "border-radius:8px;padding:12px 16px;font-family:DM Mono,monospace;font-size:12px;color:#F0A500;'>"
                "👑 Admin access — <a href='#' style='color:#F0A500;' "
                "onclick=\"window.dispatchEvent(new CustomEvent('navigate',{detail:'admin'}))\">Go to Admin Panel</a>"
                "</div>",
                unsafe_allow_html=True
            )
            if st.button("👑 Open Admin Dashboard", key="goto_admin", type="primary"):
                st.session_state.current_page = "admin"
                st.rerun()

        if st.button("🚪 Log Out", key="logout_btn"):
            for key in ["user","profile","current_page"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()

    # ══════════════════════════════════════════════════
    # TAB 2 — NOTIFICATIONS
    # ══════════════════════════════════════════════════
    with tabs[1]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        push_on  = bool(profile.get("push_alerts_enabled", True))
        email_on = bool(profile.get("email_alerts_enabled", False))
        tg_joined= bool(profile.get("telegram_joined", False))
        tg_id    = profile.get("telegram_user_id")

        # Push
        st.markdown(_card(
            f"<div style='font-family:Space Grotesk,sans-serif;font-size:15px;"
            f"font-weight:700;color:#FFFFFF;margin-bottom:4px;'>🔔 Push Notifications</div>"
            f"<div style='font-size:12px;color:#A0A0A0;line-height:1.6;'>"
            f"Browser push alerts for every new signal. "
            f"{'Instant on your ' + plan + ' plan.' if is_paid else '3-minute delay on free plan.'}</div>",
            accent="rgba(240,165,0,0.2)"
        ), unsafe_allow_html=True)
        new_push = st.toggle("Enable push notifications", value=push_on, key="tog_push")
        if new_push != push_on:
            try:
                sb.table("profiles").update({"push_alerts_enabled": new_push}).eq("id", uid).execute()
                st.session_state.profile["push_alerts_enabled"] = new_push
                st.success("Saved!"); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Telegram
        tg_link = f"https://t.me/{TELEGRAM_BOT}?start={'premium_'+uid if is_paid else 'free'}"
        st.markdown(_card(
            f"<div style='font-family:Space Grotesk,sans-serif;font-size:15px;"
            f"font-weight:700;color:#FFFFFF;margin-bottom:4px;'>✈️ Telegram "
            f"{'<span style=\"color:#22C55E;font-size:11px;\">● Connected</span>' if tg_joined else '<span style=\"color:#606060;font-size:11px;\">● Not connected</span>'}</div>"
            f"<div style='font-size:12px;color:#A0A0A0;line-height:1.6;'>"
            f"{'Private premium channel — instant signals with entry/target/stop.' if is_paid else 'Free public channel — delayed signals.'}</div>",
            accent="rgba(34,158,217,0.25)"
        ), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Join Telegram Channel →", key="tg_join", type="primary", use_container_width=True):
                try:
                    sb.table("profiles").update({"telegram_joined": True}).eq("id", uid).execute()
                    st.session_state.profile["telegram_joined"] = True
                except Exception: pass
                st.success(f"[Click here to open Telegram]({tg_link})")
        with c2:
            if tg_id:
                st.markdown(f"<div style='font-size:12px;color:#22C55E;padding:10px 0;'>ID: {tg_id}</div>", unsafe_allow_html=True)
            else:
                tg_inp = st.text_input("Paste Telegram ID", placeholder="123456789", key="tg_id")
                if st.button("Link", key="tg_link"):
                    if (tg_inp or "").strip().isdigit():
                        try:
                            sb.table("profiles").update({"telegram_user_id": int(tg_inp.strip()), "telegram_joined": True}).eq("id", uid).execute()
                            st.session_state.profile["telegram_user_id"] = int(tg_inp.strip())
                            st.session_state.profile["telegram_joined"]  = True
                            st.success("Linked!"); st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                    else: st.warning("Enter a numeric Telegram ID")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Email
        st.markdown(_card(
            f"<div style='font-family:Space Grotesk,sans-serif;font-size:15px;"
            f"font-weight:700;color:#FFFFFF;margin-bottom:4px;'>📧 Email Digest</div>"
            f"<div style='font-size:12px;color:#A0A0A0;line-height:1.6;'>"
            f"Weekly market summary every Monday 8AM WAT.</div>",
        ), unsafe_allow_html=True)
        new_email = st.toggle("Enable email digest", value=email_on, key="tog_email")
        if new_email != email_on:
            try:
                sb.table("profiles").update({"email_alerts_enabled": new_email}).eq("id", uid).execute()
                st.session_state.profile["email_alerts_enabled"] = new_email
                st.success("Saved!"); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

    # ══════════════════════════════════════════════════
    # TAB 3 — PLAN
    # ══════════════════════════════════════════════════
    with tabs[2]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        PLANS = [
            {"key": "free",    "name": "Free",    "price": "₦0",         "color": "#606060",
             "features": ["Signals with 3-min delay","Public Telegram channel","Weekly digest","Trade Game (₦500k)"]},
            {"key": "starter", "name": "Starter", "price": "₦3,500/mo",  "color": "#2563EB",
             "features": ["Instant signals","Daily AI brief","Push + Telegram alerts","10 watchlist stocks","5 price alerts","Trade Game (₦1M)"]},
            {"key": "trader",  "name": "Trader",  "price": "₦8,000/mo",  "color": "#7C3AED",
             "features": ["Everything in Starter","30 stocks","Ask AI (30/mo)","Pidgin mode","Signal reports PDF","Trade Game (₦5M)"]},
            {"key": "pro",     "name": "Pro",     "price": "₦18,000/mo", "color": "#F0A500",
             "features": ["Unlimited everything","Priority instant alerts","All PDF report types","Morning & evening briefs","Trade Game (₦10M)","Admin tools"]},
        ]

        cols = st.columns(2)
        for i, p in enumerate(PLANS):
            is_current = p["key"] == plan
            border = f"rgba({','.join(str(int(p['color'].lstrip('#')[j:j+2],16)) for j in (0,2,4))}, 0.4)" if is_current else "#1F1F1F"
            badge = "<span style='background:#22C55E;color:#000;font-size:9px;font-weight:700;padding:2px 7px;border-radius:999px;margin-left:8px;'>CURRENT</span>" if is_current else ""

            with cols[i % 2]:
                feats = "".join(f"<div style='font-size:11px;color:#A0A0A0;padding:2px 0;'>✓ {f}</div>" for f in p["features"])
                st.markdown(
                    f"<div style='background:#0A0A0A;border:1px solid {border};border-radius:12px;"
                    f"padding:16px;margin-bottom:10px;{"animation:ngx-glow-gold 4s ease-in-out infinite;" if is_current else ""}'>"
                    f"<div style='font-family:Space Grotesk,sans-serif;font-size:16px;font-weight:700;"
                    f"color:{p['color']};margin-bottom:2px;'>{p['name']}{badge}</div>"
                    f"<div style='font-family:DM Mono,monospace;font-size:18px;font-weight:500;"
                    f"color:#FFFFFF;margin-bottom:12px;'>{p['price']}</div>"
                    f"{feats}</div>",
                    unsafe_allow_html=True
                )
                if not is_current and p["key"] != "free":
                    if st.button(f"Upgrade to {p['name']}", key=f"plan_{p['key']}", use_container_width=True, type="primary"):
                        st.info(f"Paystack payment integration coming soon. Contact us to upgrade to {p['name']}.")

        st.markdown("""
        <div style='background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;
                    padding:12px 16px;font-family:DM Mono,monospace;font-size:11px;color:#606060;margin-top:8px;'>
          To upgrade: send payment to our bank account and share your receipt via Telegram.
          We'll activate your plan within 1 hour.
          <br><br>Bank: GTBank · Account: 0123456789 · Name: NGX Signal Ltd
        </div>
        """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════
    # TAB 4 — PRICE ALERTS
    # ══════════════════════════════════════════════════
    with tabs[3]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if not is_paid:
            st.info("Price alerts are available on Starter plan and above.")
            if st.button("Upgrade to set Price Alerts →", key="alert_upgrade", type="primary"):
                st.session_state.current_page = "settings"; st.rerun()
        else:
            # Set new alert
            st.markdown("**Set a new price alert**")
            ac1, ac2, ac3 = st.columns(3)
            with ac1: sym  = st.text_input("Symbol", placeholder="e.g. GTCO", key="al_sym").upper().strip()
            with ac2: tprc = st.number_input("Target price (₦)", min_value=0.01, step=0.5, key="al_price")
            with ac3: atype= st.selectbox("Alert when price goes", ["above","below"], key="al_type")

            if st.button("Set Alert", key="set_alert", type="primary"):
                if sym and tprc > 0:
                    try:
                        sb.table("price_alerts").insert({
                            "user_id": uid, "symbol": sym,
                            "target_price": tprc, "alert_type": atype, "is_active": True,
                        }).execute()
                        st.success(f"✅ Alert set: {sym} {atype} ₦{tprc:,.2f}")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                else: st.warning("Enter a symbol and target price")

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.markdown("**Active alerts**")

            try:
                alerts_res = sb.table("price_alerts").select("*").eq("user_id", uid).eq("is_active", True).execute()
                alerts = alerts_res.data or []
                if alerts:
                    for a in alerts:
                        c1, c2 = st.columns([4,1])
                        with c1:
                            st.markdown(
                                f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#FFFFFF;"
                                f"padding:8px 0;border-bottom:1px solid #1F1F1F;'>"
                                f"<strong>{a['symbol']}</strong> — price goes "
                                f"<span style='color:#F0A500;'>{a['alert_type']}</span>"
                                f" ₦{float(a['target_price']):,.2f}</div>",
                                unsafe_allow_html=True
                            )
                        with c2:
                            if st.button("Delete", key=f"del_al_{a['id']}"):
                                try:
                                    sb.table("price_alerts").update({"is_active": False}).eq("id", a["id"]).execute()
                                    st.rerun()
                                except Exception as e: st.error(f"Error: {e}")
                else:
                    st.caption("No active alerts. Set one above.")
            except Exception as e:
                st.error(f"Could not load alerts: {e}")
