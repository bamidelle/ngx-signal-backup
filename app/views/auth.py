import streamlit as st
from app.utils.supabase_client import get_supabase
from app.utils.auth import load_profile


def render():
    sb = get_supabase()

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap');

    .auth-wrap {
        max-width: 420px;
        margin: 40px auto 0 auto;
        font-family: 'DM Mono', monospace;
    }
    .auth-logo {
        text-align: center;
        margin-bottom: 32px;
    }
    .auth-logo-text {
        font-family: 'Syne', sans-serif;
        font-size: 36px;
        font-weight: 800;
        letter-spacing: -1px;
        line-height: 1;
    }
    .auth-logo-ngx { color: #FFFFFF; }
    .auth-logo-signal { color: #F0A500; }
    .auth-tagline {
        font-family: 'DM Mono', monospace;
        font-size: 11px;
        color: #4B5563;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        margin-top: 8px;
    }
    .auth-card {
        background: #10131A;
        border: 1px solid #1E2229;
        border-radius: 16px;
        padding: 32px;
    }
    .auth-tab-row {
        display: flex;
        gap: 0;
        margin-bottom: 28px;
        border-bottom: 1px solid #1E2229;
    }
    .auth-tab {
        flex: 1;
        text-align: center;
        padding: 10px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        border-bottom: 2px solid transparent;
        color: #4B5563;
        transition: all 0.2s;
    }
    .auth-tab.active {
        color: #F0A500;
        border-bottom-color: #F0A500;
    }
    .auth-label {
        font-size: 11px;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 6px;
        margin-top: 16px;
    }
    .auth-footer {
        text-align: center;
        margin-top: 24px;
        font-size: 11px;
        color: #374151;
        line-height: 1.8;
    }
    .trial-banner {
        background: #1A1600;
        border: 1px solid #3D2E00;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 12px;
        color: #F0A500;
        margin: 16px 0;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Logo
        st.markdown("""
        <div class="auth-logo">
          <div class="auth-logo-text">
            <span class="auth-logo-ngx">NGX</span><span class="auth-logo-signal">Signal</span>
          </div>
          <div class="auth-tagline">Smart Investing · Nigeria</div>
          <div style="font-size:13px;color:#6B7280;margin-top:10px;
                      font-family:'DM Mono',monospace;">
            AI-powered stock intelligence for every Nigerian investor
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Tabs
        tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

        # ── LOGIN ─────────────────────────────────────
        with tab_login:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            email = st.text_input(
                "Email address",
                key="login_email",
                placeholder="you@example.com"
            )
            password = st.text_input(
                "Password",
                type="password",
                key="login_pass",
                placeholder="Your password"
            )
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            if st.button(
                "Sign In →",
                key="login_btn",
                use_container_width=True,
                type="primary"
            ):
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    try:
                        res = sb.auth.sign_in_with_password({
                            "email": email,
                            "password": password
                        })
                        st.session_state.user = res.user
                        st.session_state.profile = load_profile(res.user.id)
                        st.session_state.current_page = "home"
                        st.rerun()
                    except Exception as e:
                        st.error("Sign in failed. Check your email and password.")

        # ── SIGNUP ────────────────────────────────────
        with tab_signup:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            full_name = st.text_input(
                "Full name",
                key="signup_name",
                placeholder="Ayo Bamidele"
            )
            email_s = st.text_input(
                "Email address",
                key="signup_email",
                placeholder="you@example.com"
            )
            password_s = st.text_input(
                "Password",
                type="password",
                key="signup_pass",
                placeholder="Min. 8 characters"
            )
            phone = st.text_input(
                "WhatsApp number (optional)",
                key="signup_phone",
                placeholder="+234 812 000 0000"
            )

            st.markdown("""
            <div class="trial-banner">
              🎁 <strong>14-day free trial</strong> on any paid plan —
              no credit card required
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                "Create Account →",
                key="signup_btn",
                use_container_width=True,
                type="primary"
            ):
                if not full_name or not email_s or not password_s:
                    st.error("Please fill in all required fields.")
                elif len(password_s) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        res = sb.auth.sign_up({
                            "email": email_s,
                            "password": password_s,
                            "options": {"data": {"full_name": full_name}}
                        })
                        if res.user:
                            if phone:
                                sb.table("profiles").update({
                                    "phone_whatsapp": phone
                                }).eq("id", res.user.id).execute()

                            # Auto-login after signup
                            try:
                                login_res = sb.auth.sign_in_with_password({
                                    "email": email_s,
                                    "password": password_s
                                })
                                st.session_state.user = login_res.user
                                st.session_state.profile = load_profile(
                                    login_res.user.id
                                )
                                st.session_state.current_page = "home"
                                st.rerun()
                            except Exception:
                                st.success("Account created! You can now sign in.")
                        else:
                            st.error("Signup failed. Please try again.")

                    except Exception as e:
                        err = str(e)
                        if "already registered" in err.lower():
                            st.error("Email already registered. Please sign in.")
                        else:
                            st.error(f"Signup error: {err}")

        # Footer
        st.markdown("""
        <div class="auth-footer">
          By signing up you agree to our Terms of Service.<br>
          NGX Signal is for informational purposes only — not financial advice.
        </div>
        """, unsafe_allow_html=True)
