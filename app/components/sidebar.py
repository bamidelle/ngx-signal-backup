import streamlit as st
from app.utils.plan_check import get_user_plan, get_trial_days_remaining
from app.utils.auth import sign_out


def render_sidebar():
    with st.sidebar:

        # ── LOGO ──────────────────────────────────────
        st.markdown("""
        <div style="padding: 8px 0 16px 0; border-bottom: 1px solid #2a2520; margin-bottom: 16px;">
          <div style="font-family: Georgia, serif; font-weight: 700; font-size: 22px; color: #ffffff; letter-spacing: -0.5px;">
            NGX<span style="color: #f5b942;">Signal</span>
          </div>
          <div style="font-family: monospace; font-size: 9px; color: #4a4038;
                      letter-spacing: 2px; text-transform: uppercase; margin-top: 3px;">
            Smart Investing · Nigeria
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── TRIAL BANNER ──────────────────────────────
        plan = get_user_plan()
        profile = st.session_state.get("profile", {})
        status = profile.get("plan_status", "active")

        if status == "trial":
            days = get_trial_days_remaining()
            color = "#f5b942" if days > 3 else "#e8572a"
            st.markdown(f"""
            <div style="background:#2a2520; border:1px solid {color}40;
                        border-radius:8px; padding:10px 12px; margin-bottom:14px;">
              <div style="font-size:11px; color:{color}; font-weight:700; font-family:monospace;">
                ⏳ TRIAL — {days} DAYS LEFT
              </div>
              <div style="font-size:11px; color:#8a7f75; margin-top:3px;">
                Upgrade to keep full access
              </div>
            </div>
            """, unsafe_allow_html=True)

        # ── NAV ITEMS ─────────────────────────────────
        nav_items = [
            ("home",      "🏠", "Home"),
            ("hot",       "🔥", "What's Hot"),
            ("signals",   "⭐", "Signal Scores"),
            ("sectors",   "🚦", "Sector Lights"),
            ("simulator", "💰", "Simulator"),
            ("alerts",    "⚡", "My Alerts"),
            ("ask_ai",    "🤖", "Ask AI"),
            ("whatsapp",  "📱", "WhatsApp Briefs"),
            ("settings",  "⚙️", "Settings"),
        ]

        current = st.session_state.get("current_page", "home")

        st.markdown("<div style='margin-bottom:4px;'>", unsafe_allow_html=True)

        for page_id, icon, label in nav_items:
            is_active = current == page_id
            bg = "#f5b942" if is_active else "transparent"
            color = "#1a1612" if is_active else "#8a7f75"
            weight = "700" if is_active else "400"

            # Extra badges
            badge = ""
            if page_id == "ask_ai" and not is_active:
                badge = '<span style="margin-left:auto;background:#e8572a;color:white;font-size:8px;font-weight:700;padding:1px 5px;border-radius:10px;font-family:monospace;">AI</span>'

            clicked = st.button(
                f"{icon}  {label}",
                key=f"nav_{page_id}",
                use_container_width=True
            )

            if clicked:
                st.session_state.current_page = page_id
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # ── DIVIDER ───────────────────────────────────
        st.markdown("""
        <div style="border-top: 1px solid #2a2520; margin: 16px 0;"></div>
        """, unsafe_allow_html=True)

        # ── USER INFO ─────────────────────────────────
        profile = st.session_state.get("profile", {})
        name = profile.get("full_name") or profile.get("email", "User")
        plan_badge_colors = {
            "free":    ("#f0f0f0", "#666"),
            "starter": ("#e8f0fb", "#1a5fa8"),
            "trader":  ("#e8f5ee", "#1a7a4a"),
            "pro":     ("#fff8e8", "#c9860a"),
        }
        bg_c, txt_c = plan_badge_colors.get(plan, ("#f0f0f0", "#666"))

        st.markdown(f"""
        <div style="background:#221e1a; border-radius:10px; padding:10px 12px;">
          <div style="font-size:13px; font-weight:600; color:#d0c8be; margin-bottom:4px;">
            {name[:22]}
          </div>
          <span style="background:{bg_c}; color:{txt_c}; padding:2px 8px;
                       border-radius:20px; font-size:10px; font-weight:700;
                       font-family:monospace;">
            {plan.upper()} PLAN
          </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:10px;'>", unsafe_allow_html=True)
        if st.button("Sign Out", key="signout_btn", use_container_width=True):
            sign_out()
        st.markdown("</div>", unsafe_allow_html=True)
