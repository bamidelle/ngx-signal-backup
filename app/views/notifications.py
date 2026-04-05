"""
NGX Signal — Notification Onboarding UI
========================================
Components:
- Push notification opt-in modal
- Telegram join CTA
- Upgrade nudge (shown after delayed alert)
- Device registration (store OneSignal player_id)
"""

import streamlit as st
import requests
import os
from app.utils.supabase_client import get_supabase

ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID", "")
TELEGRAM_BOT     = os.environ.get("TELEGRAM_BOT_USERNAME", "NGXSignalBot")
APP_URL          = "https://ngxsignal.streamlit.app"
PAID_PLANS       = {"starter", "trader", "pro"}


def register_push_device(player_id: str, user_id: str, plan: str):
    """Save OneSignal player_id to Supabase devices table."""
    sb = get_supabase()
    try:
        # Deactivate old devices for this user first
        sb.table("devices").update({"is_active": False})\
            .eq("user_id", user_id)\
            .neq("player_id", player_id)\
            .execute()

        # Upsert current device
        sb.table("devices").upsert({
            "user_id":     user_id,
            "player_id":   player_id,
            "platform":    "web",
            "plan":        plan,
            "is_active":   True,
            "tags": {
                "plan":     plan,
                "user_id":  user_id,
            },
        }, on_conflict="player_id").execute()

        # Update OneSignal device tags for segmentation
        if ONESIGNAL_APP_ID:
            requests.put(
                f"https://onesignal.com/api/v1/players/{player_id}",
                json={
                    "app_id": ONESIGNAL_APP_ID,
                    "tags": {
                        "plan":      plan,
                        "user_id":   user_id,
                        "ngx_user":  "true",
                    },
                },
                timeout=10,
            )
    except Exception as e:
        st.error(f"Device registration error: {e}")


def inject_onesignal_sdk():
    """Inject OneSignal Web SDK into the Streamlit page."""
    if not ONESIGNAL_APP_ID:
        return

    st.markdown(f"""
    <script src="https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js" defer></script>
    <script>
      window.OneSignalDeferred = window.OneSignalDeferred || [];
      OneSignalDeferred.push(async function(OneSignal) {{
        await OneSignal.init({{
          appId: "{ONESIGNAL_APP_ID}",
          notifyButton: {{ enable: false }},
          promptOptions: {{
            slidedown: {{
              prompts: [{{
                type: "push",
                autoPrompt: false,
              }}]
            }}
          }}
        }});

        // Listen for subscription change
        OneSignal.User.PushSubscription.addEventListener("change", async function(event) {{
          if (event.current.optedIn) {{
            const playerId = event.current.id;
            // Send player_id back to Streamlit via query param
            const url = new URL(window.location.href);
            url.searchParams.set("player_id", playerId);
            history.replaceState(null, "", url.toString());

            // Also store in sessionStorage for immediate access
            sessionStorage.setItem("ngx_player_id", playerId);
          }}
        }});

        // Expose prompt function globally
        window.ngxPromptPush = async function() {{
          await OneSignal.Slidedown.promptPush();
        }};

        // Get current subscription state
        const isSubscribed = OneSignal.User.PushSubscription.optedIn;
        window.ngxIsSubscribed = isSubscribed;
        const playerId = OneSignal.User.PushSubscription.id;
        if (playerId) {{
          sessionStorage.setItem("ngx_player_id", playerId);
          const url = new URL(window.location.href);
          url.searchParams.set("player_id", playerId);
          history.replaceState(null, "", url.toString());
        }}
      }});
    </script>
    """, unsafe_allow_html=True)

    # Check if player_id came back from JS
    params = st.query_params
    player_id = params.get("player_id", "")
    if player_id:
        profile      = st.session_state.get("profile", {})
        user         = st.session_state.get("user")
        plan         = profile.get("plan", "free")
        if user and player_id not in st.session_state.get("registered_devices", set()):
            register_push_device(player_id, user.id, plan)
            registered = st.session_state.get("registered_devices", set())
            registered.add(player_id)
            st.session_state.registered_devices = registered


def render_push_optin_modal():
    """
    High-converting push notification opt-in prompt.
    Show during onboarding or when user hasn't opted in.
    """
    if st.session_state.get("push_optin_dismissed"):
        return

    st.markdown("""
    <div style="background:linear-gradient(135deg,#10131A,#1A1600);
                border:1px solid #3D2E00;border-radius:14px;
                padding:24px;margin-bottom:20px;text-align:center;">
      <div style="font-size:36px;margin-bottom:12px;">⚡</div>
      <div style="font-family:Syne,sans-serif;font-size:20px;font-weight:700;
                  color:#F0A500;margin-bottom:8px;">
        Never Miss a Profitable Signal Again
      </div>
      <div style="font-family:DM Mono,monospace;font-size:13px;color:#9CA3AF;
                  line-height:1.7;max-width:420px;margin:0 auto 20px auto;">
        Get instant alerts the moment our AI detects a breakout, entry point,
        or high-conviction BUY signal — <strong style="color:#E8E2D4;">
        before the market moves</strong>.
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;
                  max-width:380px;margin:0 auto 20px auto;">
        <div style="background:#0A0C0F;border:1px solid #1E2229;border-radius:8px;padding:10px;">
          <div style="font-size:20px;">🚀</div>
          <div style="font-size:11px;color:#F0A500;margin-top:4px;font-weight:600;">Instant</div>
          <div style="font-size:10px;color:#4B5563;">alerts</div>
        </div>
        <div style="background:#0A0C0F;border:1px solid #1E2229;border-radius:8px;padding:10px;">
          <div style="font-size:20px;">📈</div>
          <div style="font-size:11px;color:#F0A500;margin-top:4px;font-weight:600;">Real NGX</div>
          <div style="font-size:10px;color:#4B5563;">stocks</div>
        </div>
        <div style="background:#0A0C0F;border:1px solid #1E2229;border-radius:8px;padding:10px;">
          <div style="font-size:20px;">🎯</div>
          <div style="font-size:11px;color:#F0A500;margin-top:4px;font-weight:600;">Entry +</div>
          <div style="font-size:10px;color:#4B5563;">targets</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])
    with col1:
        if st.button(
            "⚡ Enable Instant Alerts →",
            key="enable_push_btn",
            type="primary",
            use_container_width=True,
        ):
            # Trigger OneSignal push prompt via JS
            st.markdown("""
            <script>
              if (window.ngxPromptPush) { window.ngxPromptPush(); }
              else { console.log("OneSignal not ready"); }
            </script>
            """, unsafe_allow_html=True)
            st.session_state.push_prompt_shown = True
            st.success("✅ Check for the browser notification prompt above!")

    with col2:
        if st.button("Not now", key="dismiss_push", use_container_width=True):
            st.session_state.push_optin_dismissed = True
            st.rerun()

    st.markdown("""
    <div style="font-family:DM Mono,monospace;font-size:10px;color:#374151;
                text-align:center;margin-top:8px;">
      🔒 No spam. Only real market signals. Unsubscribe anytime.
    </div>
    """, unsafe_allow_html=True)


def render_telegram_cta(plan: str = "free"):
    """Telegram join CTA — shown during onboarding and in settings."""
    is_premium = plan in PAID_PLANS
    channel_link = f"https://t.me/{TELEGRAM_BOT}?start=free"
    channel_desc = "Free signal channel"

    if is_premium:
        user_id = st.session_state.get("user")
        if user_id:
            channel_link = f"https://t.me/{TELEGRAM_BOT}?start=premium_{user_id.id}"
        channel_desc = "Private premium signal channel"

    st.markdown(f"""
    <div style="background:#10131A;border:1px solid #1E2229;
                border-left:3px solid #229ED9;border-radius:12px;
                padding:20px;margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
        <div style="width:40px;height:40px;background:#229ED9;border-radius:10px;
                    display:flex;align-items:center;justify-content:center;
                    font-size:22px;flex-shrink:0;">✈️</div>
        <div>
          <div style="font-family:Syne,sans-serif;font-size:16px;font-weight:700;
                      color:#E8E2D4;">Join NGX Signal on Telegram</div>
          <div style="font-family:DM Mono,monospace;font-size:12px;color:#4B5563;">
            {channel_desc}
          </div>
        </div>
        {'<span style="background:rgba(34,197,94,0.12);color:#22C55E;font-size:10px;font-weight:700;padding:3px 10px;border-radius:999px;border:1px solid rgba(34,197,94,0.2);">PREMIUM</span>' if is_premium else ''}
      </div>
      <div style="font-family:DM Mono,monospace;font-size:13px;color:#9CA3AF;
                  line-height:1.65;margin-bottom:14px;">
        {'Get signals delivered <strong style="color:#E8E2D4;">instantly to Telegram</strong> — no app needed, works on any phone. Your premium private channel is waiting.' if is_premium else 'Get delayed signals on Telegram and see what the platform looks like before upgrading.'}
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button(
        "✈️ Join Telegram Channel →" if not is_premium else "💎 Join Private Premium Channel →",
        key="join_telegram_btn",
        type="primary",
    ):
        st.markdown(f"""
        <script>window.open("{channel_link}", "_blank");</script>
        """, unsafe_allow_html=True)
        # Mark as joined in Supabase
        profile = st.session_state.get("profile", {})
        sb = get_supabase()
        if profile.get("id"):
            try:
                sb.table("profiles").update({
                    "telegram_joined": True
                }).eq("id", profile["id"]).execute()
            except Exception:
                pass
        st.success("✅ Opening Telegram... Click the link to join.")


def render_upgrade_nudge(context: str = "delayed_alert"):
    """
    Conversion-optimized upgrade prompt.
    context: delayed_alert | signal_locked | weekly_limit
    """
    copies = {
        "delayed_alert": {
            "headline":  "⏱ You received this 3 minutes late",
            "body":      "Premium traders got this signal instantly — with full entry, target, and stop-loss. How many more opportunities will you miss?",
            "cta":       "Get Instant Signals from ₦3,500/mo →",
        },
        "signal_locked": {
            "headline":  "🔒 Entry, target & stop-loss locked",
            "body":      "The signal is just the start. Knowing exactly where to enter, what to aim for, and when to cut losses is what separates profitable traders. Unlock it now.",
            "cta":       "Unlock Full Signal Analysis →",
        },
        "weekly_limit": {
            "headline":  "📊 You've used your free signals this week",
            "body":      "Free users get limited signals per week. Premium users get unlimited signals, all day, every trading session.",
            "cta":       "Upgrade for Unlimited Signals →",
        },
    }
    copy = copies.get(context, copies["delayed_alert"])

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1A1600,#2A1A00);
                border:1px solid #4D3800;border-radius:12px;
                padding:20px 24px;margin:16px 0;">
      <div style="font-family:Syne,sans-serif;font-size:17px;font-weight:700;
                  color:#F0A500;margin-bottom:8px;">
        {copy['headline']}
      </div>
      <div style="font-family:DM Mono,monospace;font-size:13px;color:#9CA3AF;
                  line-height:1.65;margin-bottom:16px;">
        {copy['body']}
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button(copy["cta"], key=f"upgrade_btn_{context}", type="primary"):
        st.session_state.current_page = "settings"
        st.rerun()


def render_notification_settings():
    """Full notification preferences UI for the settings page."""
    sb      = get_supabase()
    profile = st.session_state.get("profile", {})
    user    = st.session_state.get("user")
    plan    = profile.get("plan", "free")
    user_id = profile.get("id", "")

    st.markdown("""
    <div style="font-family:Syne,sans-serif;font-size:18px;font-weight:700;
                color:#E8E2D4;margin-bottom:4px;">
        🔔 Notification Preferences
    </div>
    <div style="font-family:DM Mono,monospace;font-size:12px;color:#4B5563;
                text-transform:uppercase;letter-spacing:0.1em;margin-bottom:20px;">
        Control how NGX Signal reaches you
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        push_enabled = st.toggle(
            "🔔 Push Notifications",
            value=profile.get("push_alerts_enabled", True),
            key="toggle_push",
            help="Receive alerts directly in your browser"
        )
        email_enabled = st.toggle(
            "📧 Email Alerts",
            value=profile.get("email_alerts_enabled", False),
            key="toggle_email",
            help="Get signals and weekly digest by email"
        )

    with col2:
        tg_enabled = profile.get("telegram_joined", False)
        st.markdown(
            f"<div style='font-family:DM Mono,monospace;font-size:13px;"
            f"color:{'#22C55E' if tg_enabled else '#4B5563'};margin-top:8px;'>"
            f"{'✅ Telegram Connected' if tg_enabled else '⚪ Telegram Not Connected'}</div>",
            unsafe_allow_html=True
        )

    if st.button("💾 Save Preferences", key="save_notif_prefs", type="primary"):
        try:
            sb.table("profiles").update({
                "push_alerts_enabled":  push_enabled,
                "email_alerts_enabled": email_enabled,
            }).eq("id", user_id).execute()

            # Update OneSignal tags
            params    = st.query_params
            player_id = params.get("player_id", "")
            if player_id and ONESIGNAL_APP_ID:
                requests.put(
                    f"https://onesignal.com/api/v1/players/{player_id}",
                    json={
                        "app_id":         ONESIGNAL_APP_ID,
                        "notification_types": 1 if push_enabled else -2,
                        "tags": {"plan": plan, "push_enabled": str(push_enabled).lower()},
                    },
                    timeout=10,
                )

            # Update session state
            st.session_state.profile["push_alerts_enabled"]  = push_enabled
            st.session_state.profile["email_alerts_enabled"] = email_enabled
            st.success("✅ Notification preferences saved!")
        except Exception as e:
            st.error(f"Error saving preferences: {e}")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Telegram CTA
    render_telegram_cta(plan)


def render_onboarding_flow():
    """
    3-step onboarding modal shown to new users after signup.
    Step 1: Enable push · Step 2: Join Telegram · Step 3: Upgrade CTA
    """
    step = st.session_state.get("onboarding_step", 1)

    if step > 3 or st.session_state.get("onboarding_done"):
        return

    profile = st.session_state.get("profile", {})
    plan    = profile.get("plan", "free")
    name    = profile.get("full_name", "Investor").split()[0]

    progress = step / 3
    st.progress(progress, text=f"Setup {step} of 3")

    if step == 1:
        st.markdown(f"""
        <div style="text-align:center;padding:8px 0 16px;">
          <div style="font-size:40px;margin-bottom:8px;">👋</div>
          <div style="font-family:Syne,sans-serif;font-size:20px;font-weight:700;color:#E8E2D4;">
            Welcome, {name}!
          </div>
          <div style="font-family:DM Mono,monospace;font-size:13px;color:#9CA3AF;margin-top:8px;">
            Let's set up your alerts so you never miss a market signal.
          </div>
        </div>
        """, unsafe_allow_html=True)
        render_push_optin_modal()
        if st.button("Continue →", key="onboard_step1_next"):
            st.session_state.onboarding_step = 2
            st.rerun()

    elif step == 2:
        st.markdown("""
        <div style="text-align:center;padding:8px 0 16px;">
          <div style="font-size:40px;margin-bottom:8px;">✈️</div>
          <div style="font-family:Syne,sans-serif;font-size:20px;font-weight:700;color:#E8E2D4;">
            Get signals on Telegram
          </div>
          <div style="font-family:DM Mono,monospace;font-size:13px;color:#9CA3AF;margin-top:8px;">
            Telegram works even when you're away from the browser.
          </div>
        </div>
        """, unsafe_allow_html=True)
        render_telegram_cta(plan)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back", key="onboard_step2_back"):
                st.session_state.onboarding_step = 1
                st.rerun()
        with col2:
            if st.button("Continue →", key="onboard_step2_next", type="primary"):
                st.session_state.onboarding_step = 3
                st.rerun()

    elif step == 3:
        if plan not in PAID_PLANS:
            st.markdown("""
            <div style="text-align:center;padding:8px 0 16px;">
              <div style="font-size:40px;margin-bottom:8px;">⚡</div>
              <div style="font-family:Syne,sans-serif;font-size:20px;font-weight:700;color:#F0A500;">
                Get Instant Signals
              </div>
              <div style="font-family:DM Mono,monospace;font-size:13px;color:#9CA3AF;margin-top:8px;line-height:1.6;">
                On the Free plan, you receive signals <strong style="color:#E8E2D4;">
                3 minutes after</strong> premium subscribers — and without entry/target/stop details.
              </div>
            </div>
            """, unsafe_allow_html=True)
            render_upgrade_nudge("delayed_alert")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back", key="onboard_step3_back"):
                st.session_state.onboarding_step = 2
                st.rerun()
        with col2:
            label = "Go to Dashboard →" if plan in PAID_PLANS else "Start Free →"
            if st.button(label, key="onboard_step3_done", type="primary"):
                st.session_state.onboarding_done = True
                st.session_state.current_page    = "home"
                # Save onboarding complete to DB
                sb      = get_supabase()
                user_id = profile.get("id", "")
                if user_id:
                    try:
                        sb.table("profiles").update({
                            "onboarding_complete": True
                        }).eq("id", user_id).execute()
                    except Exception:
                        pass
                st.rerun()
