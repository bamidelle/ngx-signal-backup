"""
NGX Signal — Admin Dashboard
Manage users, plans, view stats, send broadcasts.
Only accessible to ADMIN_EMAIL.
"""
import os
import streamlit as st
from datetime import date, timedelta
from app.utils.supabase_client import get_supabase

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "aybamibello@gmail.com")
PAID_PLANS  = {"starter", "trader", "pro"}


def check_admin() -> bool:
    profile = st.session_state.get("profile", {})
    return profile.get("email", "") == ADMIN_EMAIL


def render():
    if not check_admin():
        st.error("🔒 Access denied. Admin only.")
        return

    sb = get_supabase()

    st.markdown("""
    <div style='font-family:Space Grotesk,sans-serif;font-size:22px;font-weight:800;
                color:#FFFFFF;margin-bottom:4px;'>👑 Admin Dashboard</div>
    <div style='font-family:DM Mono,monospace;font-size:11px;color:#808080;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:20px;'>
        NGX Signal · Internal Management Panel
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["📊 Overview", "👥 Users", "📅 Signals", "📢 Broadcast", "⚙️ System"])

    # ══════════════════════════════════════════════════
    # TAB 1 — OVERVIEW
    # ══════════════════════════════════════════════════
    with tabs[0]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        try:
            # User counts
            users_res  = sb.table("profiles").select("id, plan, created_at, email_alerts_enabled, telegram_joined").execute()
            all_users  = users_res.data or []
            total      = len(all_users)
            paid       = sum(1 for u in all_users if u.get("plan") in PAID_PLANS)
            free_users = total - paid
            tg_users   = sum(1 for u in all_users if u.get("telegram_joined"))
            email_on   = sum(1 for u in all_users if u.get("email_alerts_enabled"))

            # Plan breakdown
            plan_counts = {}
            for u in all_users:
                p = u.get("plan","free")
                plan_counts[p] = plan_counts.get(p, 0) + 1

            # MRR estimate
            plan_prices = {"starter": 3500, "trader": 8000, "pro": 18000}
            mrr = sum(plan_prices.get(u.get("plan","free"), 0) for u in all_users)

            # Stock prices
            sm_res = sb.table("market_summary").select("*").order("trading_date", desc=True).limit(1).execute()
            sm     = sm_res.data[0] if sm_res.data else {}
            asi    = float(sm.get("asi_index", 0) or 0)
            gainers= int(sm.get("gainers_count", 0) or 0)
            losers = int(sm.get("losers_count", 0) or 0)

            # Signal scores count
            sig_res = sb.table("signal_scores").select("id").order("score_date",desc=True).limit(1).execute()

        except Exception as e:
            st.error(f"DB error: {e}")
            return

        # KPI grid
        kpis = [
            ("Total Users",    str(total),            "#FFFFFF"),
            ("Paid Users",     str(paid),             "#F0A500"),
            ("Free Users",     str(free_users),       "#808080"),
            ("Estimated MRR",  f"₦{mrr:,}",          "#22C55E"),
            ("Telegram Users", str(tg_users),         "#229ED9"),
            ("Email Enabled",  str(email_on),         "#A78BFA"),
        ]

        cols = st.columns(3)
        for i, (label, val, color) in enumerate(kpis):
            with cols[i % 3]:
                st.markdown(
                    f"<div style='background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;"
                    f"padding:14px 16px;text-align:center;margin-bottom:10px;"
                    f"animation:ngx-fade-in .4s ease both;'>"
                    f"<div style='font-family:DM Mono,monospace;font-size:10px;color:#606060;"
                    f"text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;'>{label}</div>"
                    f"<div style='font-family:DM Mono,monospace;font-size:24px;font-weight:500;"
                    f"color:{color};'>{val}</div></div>",
                    unsafe_allow_html=True
                )

        # Plan breakdown
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("**Plan Distribution**")
        for p_name, cnt in sorted(plan_counts.items(), key=lambda x: -x[1]):
            pct = int(cnt / total * 100) if total > 0 else 0
            color = {"pro":"#F0A500","trader":"#7C3AED","starter":"#2563EB"}.get(p_name,"#606060")
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:12px;padding:6px 0;"
                f"border-bottom:1px solid #1A1A1A;font-family:DM Mono,monospace;font-size:13px;'>"
                f"<span style='min-width:70px;color:{color};font-weight:600;text-transform:uppercase;'>{p_name}</span>"
                f"<div style='flex:1;background:#1A1A1A;border-radius:4px;height:6px;'>"
                f"<div style='background:{color};border-radius:4px;height:6px;width:{pct}%;'></div></div>"
                f"<span style='min-width:40px;text-align:right;color:#FFFFFF;'>{cnt}</span>"
                f"<span style='color:#606060;'>({pct}%)</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        # Market summary
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("**Latest Market Data**")
        st.markdown(
            f"<div style='background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;"
            f"padding:12px 16px;font-family:DM Mono,monospace;font-size:12px;color:#A0A0A0;'>"
            f"ASI: <span style='color:#FFFFFF;'>{asi:,.2f}</span> &nbsp;·&nbsp; "
            f"Gainers: <span style='color:#22C55E;'>{gainers}</span> &nbsp;·&nbsp; "
            f"Losers: <span style='color:#EF4444;'>{losers}</span> &nbsp;·&nbsp; "
            f"Date: <span style='color:#FFFFFF;'>{sm.get('trading_date','—')}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    # ══════════════════════════════════════════════════
    # TAB 2 — USERS
    # ══════════════════════════════════════════════════
    with tabs[1]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Filters
        c1, c2 = st.columns(2)
        with c1:
            plan_filter = st.selectbox("Filter by plan", ["All","free","starter","trader","pro"], key="adm_plan_f")
        with c2:
            search_user = st.text_input("Search name or email", placeholder="Search...", key="adm_search")

        try:
            users_res = sb.table("profiles")\
                .select("id, full_name, email, plan, created_at, telegram_joined, email_alerts_enabled, telegram_user_id")\
                .order("created_at", desc=True)\
                .limit(200).execute()
            users = users_res.data or []
        except Exception as e:
            st.error(f"Error loading users: {e}"); users = []

        # Filter
        if plan_filter != "All":
            users = [u for u in users if u.get("plan") == plan_filter]
        if search_user:
            s = search_user.lower()
            users = [u for u in users if s in (u.get("full_name","") or "").lower()
                     or s in (u.get("email","") or "").lower()]

        st.caption(f"Showing {len(users)} users")

        for u in users[:50]:
            p_color = {"pro":"#F0A500","trader":"#7C3AED","starter":"#2563EB"}.get(u.get("plan","free"),"#606060")
            tg_icon = "✈️" if u.get("telegram_joined") else "—"
            em_icon = "📧" if u.get("email_alerts_enabled") else "—"

            col1, col2, col3 = st.columns([4, 2, 2])
            with col1:
                st.markdown(
                    f"<div style='padding:8px 0;border-bottom:1px solid #111;font-family:DM Mono,monospace;'>"
                    f"<div style='font-size:13px;color:#FFFFFF;font-weight:500;'>"
                    f"{u.get('full_name','—')}</div>"
                    f"<div style='font-size:11px;color:#606060;'>{u.get('email','—')}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    f"<div style='padding:10px 0;border-bottom:1px solid #111;'>"
                    f"<span style='background:{p_color}22;color:{p_color};font-size:10px;"
                    f"font-weight:700;padding:2px 8px;border-radius:999px;text-transform:uppercase;'>"
                    f"{u.get('plan','free')}</span></div>",
                    unsafe_allow_html=True
                )
            with col3:
                new_plan = st.selectbox(
                    "", ["free","starter","trader","pro"],
                    index=["free","starter","trader","pro"].index(u.get("plan","free")),
                    key=f"plan_sel_{u['id']}",
                    label_visibility="collapsed"
                )
                if new_plan != u.get("plan","free"):
                    if st.button("✓", key=f"plan_save_{u['id']}"):
                        try:
                            sb.table("profiles").update({"plan": new_plan}).eq("id", u["id"]).execute()
                            st.success(f"Updated {u.get('full_name','?')} → {new_plan}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    # ══════════════════════════════════════════════════
    # TAB 3 — SIGNALS
    # ══════════════════════════════════════════════════
    with tabs[2]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        try:
            sig_res = sb.table("signal_scores")\
                .select("symbol, signal, stars, reasoning, score_date")\
                .order("score_date", desc=True)\
                .order("stars", desc=True)\
                .limit(50).execute()
            signals = sig_res.data or []
        except Exception as e:
            st.error(f"Error: {e}"); signals = []

        for s in signals:
            color = {"STRONG_BUY":"#22C55E","BUY":"#22C55E","BREAKOUT_WATCH":"#3B82F6",
                     "HOLD":"#D97706","CAUTION":"#EA580C","AVOID":"#EF4444"}.get(s.get("signal","HOLD"),"#808080")
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:12px;padding:8px 0;"
                f"border-bottom:1px solid #111;font-family:DM Mono,monospace;font-size:12px;'>"
                f"<span style='min-width:90px;font-weight:600;color:#FFFFFF;'>{s['symbol']}</span>"
                f"<span style='min-width:110px;color:{color};font-size:11px;font-weight:700;'>"
                f"{(s.get('signal') or '').replace('_',' ')}</span>"
                f"<span style='color:#F0A500;'>{'⭐'*int(s.get('stars',3))}</span>"
                f"<span style='flex:1;color:#606060;font-size:11px;'>"
                f"{(s.get('reasoning') or '')[:80]}...</span>"
                f"<span style='color:#404040;font-size:10px;'>{s.get('score_date','')}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ══════════════════════════════════════════════════
    # TAB 4 — BROADCAST
    # ══════════════════════════════════════════════════
    with tabs[3]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("**Send a broadcast message to Telegram channels**")

        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN","")
        free_id  = os.environ.get("TELEGRAM_FREE_CHANNEL_ID","")
        prem_id  = os.environ.get("TELEGRAM_PREMIUM_CHANNEL_ID","")

        bc_msg = st.text_area(
            "Message (HTML supported)",
            placeholder="<b>NGX Signal Alert</b>\n\nMessage here...",
            height=120, key="bc_msg"
        )
        bc_target = st.multiselect(
            "Send to:", ["Free Channel", "Premium Channel"],
            default=["Free Channel", "Premium Channel"],
            key="bc_target"
        )

        if st.button("📢 Send Broadcast", key="send_bc", type="primary"):
            if bc_msg.strip() and tg_token:
                import requests as req
                sent = 0
                targets = []
                if "Free Channel"    in bc_target and free_id:  targets.append(("Free",    free_id))
                if "Premium Channel" in bc_target and prem_id:  targets.append(("Premium", prem_id))

                for label, chat_id in targets:
                    r = req.post(
                        f"https://api.telegram.org/bot{tg_token}/sendMessage",
                        json={"chat_id": chat_id, "text": bc_msg,
                              "parse_mode": "HTML", "disable_web_page_preview": True},
                        timeout=10
                    )
                    if r.status_code == 200:
                        st.success(f"✅ Sent to {label} channel")
                        sent += 1
                    else:
                        st.error(f"❌ Failed ({label}): {r.json().get('description','')}")
            else:
                st.warning("Enter a message and ensure TELEGRAM_BOT_TOKEN is set in Streamlit secrets.")

    # ══════════════════════════════════════════════════
    # TAB 5 — SYSTEM
    # ══════════════════════════════════════════════════
    with tabs[4]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Secret check
        secrets_check = {
            "SUPABASE_URL":                bool(os.environ.get("SUPABASE_URL")),
            "SUPABASE_SERVICE_KEY":        bool(os.environ.get("SUPABASE_SERVICE_KEY")),
            "TELEGRAM_BOT_TOKEN":          bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
            "TELEGRAM_FREE_CHANNEL_ID":    bool(os.environ.get("TELEGRAM_FREE_CHANNEL_ID")),
            "TELEGRAM_PREMIUM_CHANNEL_ID": bool(os.environ.get("TELEGRAM_PREMIUM_CHANNEL_ID")),
            "ONESIGNAL_APP_ID":            bool(os.environ.get("ONESIGNAL_APP_ID")),
            "ONESIGNAL_API_KEY":           bool(os.environ.get("ONESIGNAL_API_KEY")),
            "BREVO_API_KEY":               bool(os.environ.get("BREVO_API_KEY")),
            "GROQ_API_KEY":                bool(os.environ.get("GROQ_API_KEY")),
            "GEMINI_API_KEY":              bool(os.environ.get("GEMINI_API_KEY")),
        }

        st.markdown("**Environment / Secrets Status**")
        for key, ok in secrets_check.items():
            icon  = "✅" if ok else "❌"
            color = "#22C55E" if ok else "#EF4444"
            st.markdown(
                f"<div style='font-family:DM Mono,monospace;font-size:12px;padding:5px 0;"
                f"border-bottom:1px solid #111;display:flex;gap:10px;'>"
                f"<span>{icon}</span>"
                f"<span style='flex:1;color:#FFFFFF;'>{key}</span>"
                f"<span style='color:{color};font-weight:600;'>{'SET' if ok else 'MISSING'}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("**Database Tables**")
        try:
            for table in ["profiles","stock_prices","signal_scores","alerts","alert_logs","devices","telegram_users"]:
                try:
                    res = sb.table(table).select("id").limit(1).execute()
                    st.markdown(
                        f"<div style='font-family:DM Mono,monospace;font-size:11px;padding:4px 0;"
                        f"color:#22C55E;'>✅ {table}</div>",
                        unsafe_allow_html=True
                    )
                except Exception:
                    st.markdown(
                        f"<div style='font-family:DM Mono,monospace;font-size:11px;padding:4px 0;"
                        f"color:#EF4444;'>❌ {table} — not accessible</div>",
                        unsafe_allow_html=True
                    )
        except Exception as e:
            st.error(f"DB check failed: {e}")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.caption(f"Today: {date.today()} · Admin: {ADMIN_EMAIL}")
