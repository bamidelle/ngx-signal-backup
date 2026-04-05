import streamlit as st
import re
from app.utils.supabase_client import get_supabase


def render():
    sb = get_supabase()
    profile = st.session_state.get("profile", {})
    plan = profile.get("plan", "free")
    user = st.session_state.get("user")

    st.markdown("""
    <div style="padding:10px 0 20px 0;">
      <h2 style="margin:0;font-size:22px;color:#1a1612;">📱 WhatsApp Briefs</h2>
      <p style="margin:4px 0 0 0;color:#6b6560;font-size:14px;">
        Receive your daily market brief on WhatsApp every morning
      </p>
    </div>
    """, unsafe_allow_html=True)

    if plan == "free":
        st.markdown("""
        <div style="background:#fffbeb;border:1px solid #fde68a;
                    border-radius:12px;padding:20px;margin-bottom:20px;
                    text-align:center;">
          <div style="font-size:32px;margin-bottom:8px;">📱</div>
          <div style="font-weight:700;font-size:16px;color:#1a1612;
                      margin-bottom:8px;">
            WhatsApp briefs on Starter plan
          </div>
          <div style="color:#6b6560;font-size:14px;">
            Upgrade to receive your daily NGX market brief on WhatsApp
            every morning at 8AM WAT — in English or Pidgin.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── WHATSAPP SETTINGS ────────────────────────────
    st.markdown("### Your WhatsApp Settings")

    phone = profile.get("phone_whatsapp", "") or ""
    current_lang = profile.get("brief_language", "en") or "en"
    whatsapp_enabled = profile.get("whatsapp_enabled", True)

    new_phone = st.text_input(
        "WhatsApp number (with country code)",
        value=phone,
        placeholder="+2348012345678",
        key="wa_phone"
    )

    use_pidgin = st.toggle(
        "🇳🇬 Receive brief in Pidgin English",
        value=current_lang == "pg",
        key="wa_pidgin"
    )

    wa_enabled = st.toggle(
        "📲 Enable WhatsApp notifications",
        value=whatsapp_enabled,
        key="wa_enabled"
    )

    if st.button("Save WhatsApp Settings", key="wa_save", type="primary"):
        try:
            sb.table("profiles").update({
                "phone_whatsapp": new_phone,
                "brief_language": "pg" if use_pidgin else "en",
                "whatsapp_enabled": wa_enabled,
            }).eq("id", user.id).execute()

            # Update session state
            st.session_state.profile["phone_whatsapp"] = new_phone
            st.session_state.profile["brief_language"] = \
                "pg" if use_pidgin else "en"
            st.session_state.profile["whatsapp_enabled"] = wa_enabled

            st.success("✅ WhatsApp settings saved!")
        except Exception as e:
            st.error(f"Could not save settings: {e}")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── DELIVERY SCHEDULE ────────────────────────────
    st.markdown("""
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;
                border-radius:12px;padding:16px;margin-bottom:20px;">
      <div style="font-weight:700;color:#16a34a;margin-bottom:8px;">
        📅 Delivery Schedule
      </div>
      <div style="font-size:13px;color:#3a3028;line-height:1.8;">
        🌅 <strong>Morning Brief</strong> — 8:00 AM WAT every weekday<br>
        ⚡ <strong>Price Alerts</strong> — Within minutes of trigger<br>
        📊 <strong>Market Close</strong> — 5:30 PM WAT summary (Pro only)
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── PREVIEW TODAY'S BRIEF ────────────────────────
    st.markdown("### Preview Today's Brief")

    lang_key = "pg" if use_pidgin else "en"
    brief_res = sb.table("ai_briefs")\
        .select("body, brief_date")\
        .eq("language", lang_key)\
        .eq("brief_type", "morning")\
        .order("brief_date", desc=True)\
        .limit(1).execute()

    if brief_res.data:
        body = brief_res.data[0].get("body", "")
        brief_date = brief_res.data[0].get("brief_date", "")
        formatted = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', body)
        formatted = formatted.replace("\n", "<br>")
        st.markdown(f"""
        <div style="background:#fffdf7;border:1px solid #f0d88a;
                    border-left:4px solid #f5b942;border-radius:12px;
                    padding:20px;font-size:14px;color:#3a3028;line-height:1.8;">
          <div style="font-size:11px;color:#9a9088;margin-bottom:10px;">
            📅 {brief_date} · {"Pidgin" if lang_key == "pg" else "English"}
          </div>
          {formatted}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No brief available yet for today. Check back after 8AM WAT.")
