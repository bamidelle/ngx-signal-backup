import streamlit as st
from datetime import date
from app.utils.supabase_client import get_supabase

NGX_DIVIDENDS = [
    {"symbol":"GTCO","company":"Guaranty Trust Holding Co.","sector":"Banking","dividend_per_share":3.00,"ex_date":"2026-03-15","payment_date":"2026-04-30","yield_pct":2.56,"frequency":"Annual"},
    {"symbol":"ZENITHBANK","company":"Zenith Bank Plc","sector":"Banking","dividend_per_share":4.00,"ex_date":"2026-03-20","payment_date":"2026-05-15","yield_pct":10.39,"frequency":"Annual"},
    {"symbol":"ACCESSCORP","company":"Access Holdings Plc","sector":"Banking","dividend_per_share":1.80,"ex_date":"2026-04-01","payment_date":"2026-05-20","yield_pct":7.88,"frequency":"Annual"},
    {"symbol":"UBA","company":"United Bank for Africa Plc","sector":"Banking","dividend_per_share":2.00,"ex_date":"2026-03-28","payment_date":"2026-05-10","yield_pct":7.04,"frequency":"Annual"},
    {"symbol":"FBNH","company":"FBN Holdings Plc","sector":"Banking","dividend_per_share":1.00,"ex_date":"2026-04-10","payment_date":"2026-06-01","yield_pct":3.56,"frequency":"Annual"},
    {"symbol":"MTNN","company":"MTN Nigeria Communications","sector":"Telecoms","dividend_per_share":15.76,"ex_date":"2026-05-05","payment_date":"2026-06-15","yield_pct":5.15,"frequency":"Annual"},
    {"symbol":"DANGCEM","company":"Dangote Cement Plc","sector":"Cement","dividend_per_share":20.00,"ex_date":"2026-05-20","payment_date":"2026-07-01","yield_pct":4.70,"frequency":"Annual"},
    {"symbol":"NESTLE","company":"Nestlé Nigeria Plc","sector":"Consumer Goods","dividend_per_share":50.00,"ex_date":"2026-04-25","payment_date":"2026-06-10","yield_pct":4.21,"frequency":"Annual"},
    {"symbol":"PRESCO","company":"Presco Plc","sector":"Agriculture","dividend_per_share":10.00,"ex_date":"2026-06-01","payment_date":"2026-07-15","yield_pct":3.45,"frequency":"Annual"},
    {"symbol":"OKOMUOIL","company":"Okomu Oil Palm Plc","sector":"Agriculture","dividend_per_share":12.00,"ex_date":"2026-06-10","payment_date":"2026-07-25","yield_pct":3.12,"frequency":"Annual"},
    {"symbol":"BUAFOODS","company":"BUA Foods Plc","sector":"Consumer Goods","dividend_per_share":8.00,"ex_date":"2026-05-15","payment_date":"2026-07-01","yield_pct":2.03,"frequency":"Annual"},
    {"symbol":"STANBIC","company":"Stanbic IBTC Holdings","sector":"Banking","dividend_per_share":5.00,"ex_date":"2026-04-20","payment_date":"2026-06-05","yield_pct":8.49,"frequency":"Annual"},
]

def render():
    st.markdown("""
    <div style='font-family:Space Grotesk,sans-serif;font-size:22px;font-weight:800;
                color:#FFFFFF;margin-bottom:4px;'>💸 Dividend Tracker</div>
    <div style='font-family:DM Mono,monospace;font-size:11px;color:#808080;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:20px;'>
        Track NGX dividends, payment dates and calculate your income
    </div>""", unsafe_allow_html=True)

    today_str = str(date.today())
    upcoming  = [d for d in NGX_DIVIDENDS if d["ex_date"] >= today_str]
    past      = [d for d in NGX_DIVIDENDS if d["ex_date"] < today_str]
    high_yld  = [d for d in NGX_DIVIDENDS if d["yield_pct"] >= 5.0]

    c1,c2,c3 = st.columns(3)
    for col, label, val, color in [
        (c1, "Upcoming Dividends", str(len(upcoming)), "#22C55E"),
        (c2, "Total Tracking",     str(len(NGX_DIVIDENDS)), "#F0A500"),
        (c3, "High Yield (≥5%)",   str(len(high_yld)), "#A78BFA"),
    ]:
        with col:
            st.markdown(f"""
            <div style='background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;
                        padding:14px;text-align:center;margin-bottom:16px;'>
              <div style='font-size:10px;color:#808080;text-transform:uppercase;
                          letter-spacing:.08em;margin-bottom:6px;'>{label}</div>
              <div style='font-family:DM Mono,monospace;font-size:24px;font-weight:500;
                          color:{color};'>{val}</div>
            </div>""", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📅 All Dividends", "🧮 Income Calculator", "📊 Yield Rankings"])

    with tab1:
        st.markdown("**Upcoming & Recent NGX Dividends**")
        for d in NGX_DIVIDENDS:
            is_upcoming = d["ex_date"] >= today_str
            border_c    = "rgba(34,197,94,0.3)" if is_upcoming else "#1F1F1F"
            badge       = "<span style='background:rgba(34,197,94,.15);color:#22C55E;font-size:10px;padding:2px 8px;border-radius:999px;margin-left:8px;'>UPCOMING</span>" if is_upcoming else ""
            st.markdown(f"""
            <div style='background:#0A0A0A;border:1px solid {border_c};border-radius:10px;
                        padding:14px 16px;margin-bottom:8px;font-family:DM Mono,monospace;'>
              <div style='display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;'>
                <div>
                  <span style='font-family:Space Grotesk,sans-serif;font-size:15px;font-weight:700;
                               color:#FFFFFF;'>{d["symbol"]}</span>{badge}
                  <span style='font-size:11px;color:#808080;margin-left:8px;'>{d["company"][:30]}</span>
                </div>
                <div style='text-align:right;'>
                  <span style='font-size:16px;font-weight:600;color:#22C55E;'>
                    ₦{d["dividend_per_share"]:.2f}
                  </span>
                  <span style='font-size:11px;color:#A0A0A0;margin-left:6px;'>
                    {d["yield_pct"]:.2f}% yield
                  </span>
                </div>
              </div>
              <div style='display:flex;gap:16px;margin-top:6px;font-size:11px;color:#808080;flex-wrap:wrap;'>
                <span>📅 Ex-date: <span style='color:#FFFFFF;'>{d["ex_date"]}</span></span>
                <span>💳 Payment: <span style='color:#FFFFFF;'>{d["payment_date"]}</span></span>
                <span>🔄 {d["frequency"]}</span>
                <span>🏭 {d["sector"]}</span>
              </div>
            </div>""", unsafe_allow_html=True)

    with tab2:
        st.markdown("**Calculate your dividend income**")
        syms = [d["symbol"] for d in NGX_DIVIDENDS]
        sel  = st.selectbox("Select stock", syms, key="div_calc_sym")
        d_data = next((d for d in NGX_DIVIDENDS if d["symbol"]==sel), NGX_DIVIDENDS[0])
        shares = st.number_input("Number of shares you hold", min_value=1, value=1000, step=100, key="div_calc_shares")

        income = shares * d_data["dividend_per_share"]
        cost_basis = st.number_input("Your average buy price (₦)", min_value=0.01, step=0.5, key="div_calc_cost",
                                      value=float(f"{d_data.get('dividend_per_share',0)*10:.2f}"))
        personal_yield = (d_data["dividend_per_share"] / cost_basis * 100) if cost_basis > 0 else 0

        st.markdown(f"""
        <div style='background:#0A0A0A;border:1px solid rgba(240,165,0,0.3);border-radius:12px;
                    padding:20px;margin-top:12px;font-family:DM Mono,monospace;'>
          <div style='font-size:13px;color:#808080;margin-bottom:12px;'>
            {sel} · {shares:,} shares · Ex-date {d_data["ex_date"]}
          </div>
          <div style='display:grid;grid-template-columns:1fr 1fr;gap:12px;'>
            <div style='background:#000;border:1px solid #1F1F1F;border-radius:8px;padding:14px;text-align:center;'>
              <div style='font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;'>Dividend Income</div>
              <div style='font-size:24px;font-weight:600;color:#22C55E;'>₦{income:,.2f}</div>
            </div>
            <div style='background:#000;border:1px solid #1F1F1F;border-radius:8px;padding:14px;text-align:center;'>
              <div style='font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;'>Your Personal Yield</div>
              <div style='font-size:24px;font-weight:600;color:#F0A500;'>{personal_yield:.2f}%</div>
            </div>
          </div>
          <div style='font-size:11px;color:#606060;margin-top:12px;'>
            ⚠️ Dividend data is indicative. Always verify with official NGX announcements.
          </div>
        </div>""", unsafe_allow_html=True)

    with tab3:
        st.markdown("**Stocks ranked by dividend yield**")
        ranked = sorted(NGX_DIVIDENDS, key=lambda x: x["yield_pct"], reverse=True)
        for i,d in enumerate(ranked):
            bar_w = int(d["yield_pct"] / ranked[0]["yield_pct"] * 100)
            color = "#22C55E" if d["yield_pct"]>=7 else "#F0A500" if d["yield_pct"]>=4 else "#808080"
            st.markdown(f"""
            <div style='display:flex;align-items:center;gap:12px;padding:8px 0;
                        border-bottom:1px solid #111;font-family:DM Mono,monospace;font-size:13px;'>
              <span style='min-width:20px;color:#606060;'>#{i+1}</span>
              <span style='min-width:100px;font-weight:700;color:#FFFFFF;'>{d["symbol"]}</span>
              <div style='flex:1;background:#1A1A1A;border-radius:3px;height:5px;'>
                <div style='background:{color};border-radius:3px;height:5px;width:{bar_w}%;'></div>
              </div>
              <span style='min-width:60px;text-align:right;color:{color};font-weight:600;'>{d["yield_pct"]:.2f}%</span>
              <span style='min-width:60px;text-align:right;color:#A0A0A0;'>₦{d["dividend_per_share"]:.2f}</span>
            </div>""", unsafe_allow_html=True)
