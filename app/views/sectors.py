import streamlit as st
from app.utils.supabase_client import get_supabase


def render():
    sb = get_supabase()
    profile = st.session_state.get("profile", {})
    plan = profile.get("plan", "free")

    st.markdown("""
    <div style="padding:10px 0 20px 0;">
      <h2 style="margin:0;font-size:22px;color:#1a1612;">🚦 Sector Lights</h2>
      <p style="margin:4px 0 0 0;color:#6b6560;font-size:14px;">
        Traffic light view of every NGX market sector
      </p>
    </div>
    """, unsafe_allow_html=True)

    use_pidgin = False
    if plan in ("trader", "pro"):
        use_pidgin = st.toggle(
            "🇳🇬 Pidgin verdicts", key="sector_lang"
        )

    res = sb.table("sector_performance")\
        .select("*")\
        .order("change_percent", desc=True).execute()
    sectors = res.data or []

    if not sectors:
        st.info("No sector data yet. Run the scraper first.")
        return

    green = sum(1 for s in sectors if s.get("traffic_light") == "green")
    amber = sum(1 for s in sectors if s.get("traffic_light") == "amber")
    red   = sum(1 for s in sectors if s.get("traffic_light") == "red")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;
                    border-radius:10px;padding:14px;text-align:center;">
          <div style="font-size:28px;">🟢</div>
          <div style="font-size:22px;font-weight:700;color:#16a34a;">{green}</div>
          <div style="font-size:12px;color:#9a9088;">Strong sectors</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div style="background:#fffbeb;border:1px solid #fde68a;
                    border-radius:10px;padding:14px;text-align:center;">
          <div style="font-size:28px;">🟡</div>
          <div style="font-size:22px;font-weight:700;color:#d97706;">{amber}</div>
          <div style="font-size:12px;color:#9a9088;">Mixed sectors</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div style="background:#fef2f2;border:1px solid #fecaca;
                    border-radius:10px;padding:14px;text-align:center;">
          <div style="font-size:28px;">🔴</div>
          <div style="font-size:22px;font-weight:700;color:#dc2626;">{red}</div>
          <div style="font-size:12px;color:#9a9088;">Weak sectors</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    for sector in sectors:
        light = sector.get("traffic_light", "amber")
        emoji = "🟢" if light == "green" else \
                "🔴" if light == "red" else "🟡"
        chg = sector.get("change_percent", 0) or 0
        color = "#16a34a" if chg >= 0 else "#dc2626"
        bg = "#f0fdf4" if light == "green" else \
             "#fef2f2" if light == "red" else "#fffbeb"
        border = "#bbf7d0" if light == "green" else \
                 "#fecaca" if light == "red" else "#fde68a"
        verdict = sector.get(
            "verdict_pg" if use_pidgin else "verdict", ""
        ) or ""

        st.markdown(f"""
        <div style="background:{bg};border:1px solid {border};
                    border-radius:12px;padding:16px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;
                      align-items:center;margin-bottom:6px;">
            <span style="font-size:17px;font-weight:700;color:#1a1612;">
              {emoji} {sector['sector_name']}
            </span>
            <span style="font-size:16px;font-weight:700;color:{color};">
              {chg:+.2f}%
            </span>
          </div>
          <div style="font-size:13px;color:#5a524a;line-height:1.5;">
            {verdict}
          </div>
        </div>
        """, unsafe_allow_html=True)
