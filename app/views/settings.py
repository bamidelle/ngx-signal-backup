import streamlit as st
from app.utils.supabase_client import get_supabase


def render():
    sb = get_supabase()
    profile = st.session_state.get("profile", {})
    user = st.session_state.get("user")
    plan = profile.get("plan", "free")

    st.markdown("""
    <div style="padding:10px 0 20px 0;">
      <h2 style="margin:0;font-size:22px;color:#1a1612;">⚙️ Settings</h2>
      <p style="margin:4px 0 0 0;color:#6b6560;font-size:14px;">
        Manage your account and preferences
      </p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["👤 Profile", "💳 Plan", "🔔 Notifications"])

    # ── TAB 1: PROFILE ───────────────────────────────
    with tab1:
        st.markdown("### Personal Details")

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
            "WhatsApp number",
            value=profile.get("phone_whatsapp", "") or "",
            placeholder="+2348012345678",
            key="set_phone"
        )

        current_lang = profile.get("brief_language", "en") or "en"
        use_pidgin = st.toggle(
            "🇳🇬 Receive briefs in Pidgin English",
            value=current_lang == "pg",
            key="set_pidgin"
        )

        if st.button("Save Profile", key="save_profile", type="primary"):
            try:
                sb.table("profiles").update({
                    "full_name": full_name,
                    "phone_whatsapp": phone,
                    "brief_language": "pg" if use_pidgin else "en",
                }).eq("id", user.id).execute()

                st.session_state.profile["full_name"] = full_name
                st.session_state.profile["phone_whatsapp"] = phone
                st.session_state.profile["brief_language"] = \
                    "pg" if use_pidgin else "en"

                st.success("✅ Profile updated!")
            except Exception as e:
                st.error(f"Could not update profile: {e}")

    # ── TAB 2: PLAN ──────────────────────────────────
    with tab2:
        plan_colors = {
            "free": "#6b6560", "starter": "#2563eb",
            "trader": "#7c3aed", "pro": "#f5b942",
        }
        plan_color = plan_colors.get(plan, "#6b6560")

        st.markdown(f"""
        <div style="background:#fff;border:2px solid {plan_color};
                    border-radius:16px;padding:24px;margin-bottom:20px;">
          <div style="font-size:13px;color:#9a9088;">Current plan</div>
          <div style="font-size:28px;font-weight:700;color:{plan_color};
                      text-transform:uppercase;margin-top:4px;">{plan}</div>
          <div style="font-size:13px;color:#6b6560;margin-top:8px;">
            {"Upgrade to unlock more features" if plan == "free" else
             "Thank you for being a subscriber!"}
          </div>
        </div>
        """, unsafe_allow_html=True)

        if plan == "free":
            plans = [
                ("Starter", "₦3,500/mo", "#2563eb", [
                    "Daily AI morning brief",
                    "10 watchlist stocks",
                    "5 WhatsApp price alerts/month",
                    "Investment simulator",
                    "WhatsApp brief delivery",
                ]),
                ("Trader", "₦8,000/mo", "#7c3aed", [
                    "30 stocks watchlist",
                    "Unlimited price alerts",
                    "Ask AI (30 queries/month)",
                    "Pidgin English briefs",
                    "Priority WhatsApp delivery",
                ]),
                ("Pro", "₦18,000/mo", "#f5b942", [
                    "Unlimited everything",
                    "PDF intelligence reports",
                    "Unlimited Ask AI",
                    "Evening market close brief",
                    "Early access to new features",
                ]),
            ]
            for pname, price, pcolor, features in plans:
                features_html = "".join(
                    f"<div style='font-size:13px;color:#3a3028;"
                    f"padding:3px 0;'>✓ {f}</div>"
                    for f in features
                )
                st.markdown(f"""
                <div style="background:#fff;border:1px solid {pcolor}44;
                            border-top:3px solid {pcolor};border-radius:12px;
                            padding:16px;margin-bottom:12px;">
                  <div style="display:flex;justify-content:space-between;
                              align-items:center;margin-bottom:10px;">
                    <span style="font-weight:700;font-size:16px;
                                 color:{pcolor};">{pname}</span>
                    <span style="font-weight:700;font-size:16px;
                                 color:#1a1612;">{price}</span>
                  </div>
                  {features_html}
                </div>
                """, unsafe_allow_html=True)

            st.info(
                "💳 Paystack payment integration coming soon. "
                "Contact us on WhatsApp to upgrade manually for now."
            )

    # ── TAB 3: NOTIFICATIONS ─────────────────────────
    with tab3:
        st.markdown("### Notification Preferences")

        whatsapp_enabled = profile.get("whatsapp_enabled", True)
        current_lang = profile.get("brief_language", "en") or "en"

        wa_on = st.toggle(
            "📱 WhatsApp brief delivery (8AM WAT daily)",
            value=whatsapp_enabled,
            disabled=plan == "free",
            key="notif_wa"
        )

        pidgin_on = st.toggle(
            "🇳🇬 Receive in Pidgin English",
            value=current_lang == "pg",
            disabled=plan == "free",
            key="notif_pidgin"
        )

        alert_on = st.toggle(
            "⚡ Price alert notifications",
            value=plan != "free",
            disabled=plan == "free",
            key="notif_alerts"
        )

        if plan == "free":
            st.caption(
                "🔒 Notifications require Starter plan or above."
            )

        if st.button(
            "Save Notification Settings",
            key="save_notifs",
            type="primary",
            disabled=plan == "free"
        ):
            try:
                sb.table("profiles").update({
                    "whatsapp_enabled": wa_on,
                    "brief_language": "pg" if pidgin_on else "en",
                }).eq("id", user.id).execute()

                st.session_state.profile["whatsapp_enabled"] = wa_on
                st.session_state.profile["brief_language"] = \
                    "pg" if pidgin_on else "en"

                st.success("✅ Notification preferences saved!")
            except Exception as e:
                st.error(f"Could not save: {e}")

    # ── SIGN OUT ─────────────────────────────────────
    st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<hr style='border-color:#e5e0da;'>",
        unsafe_allow_html=True
    )
    if st.button("🚪 Sign Out", key="settings_signout"):
        sb.auth.sign_out()
        st.session_state.user = None
        st.session_state.profile = {}
        st.session_state.current_page = "home"
        st.rerun()
