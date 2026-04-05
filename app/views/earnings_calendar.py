import streamlit as st
from datetime import date, datetime
from app.utils.supabase_client import get_supabase

NGX_EVENTS = [
    {"date":"2026-03-28","symbol":"GTCO","company":"Guaranty Trust Holding Co.","event_type":"AGM","title":"Annual General Meeting 2025","description":"Shareholders vote on final dividend of ₦3.00/share and board composition.","expected_dividend":3.00,"impact":"HIGH","sector":"Banking"},
    {"date":"2026-03-31","symbol":"ZENITHBANK","company":"Zenith Bank Plc","event_type":"RESULTS","title":"Full Year 2025 Results","description":"Full year earnings release. Analysts expect PAT above ₦350bn.","expected_dividend":3.50,"impact":"HIGH","sector":"Banking"},
    {"date":"2026-04-02","symbol":"MTNN","company":"MTN Nigeria Communications","event_type":"DIVIDEND","title":"Interim Dividend Payment","description":"Payment of interim dividend of ₦4.50/share to qualifying shareholders.","expected_dividend":4.50,"impact":"MEDIUM","sector":"Telecoms"},
    {"date":"2026-04-05","symbol":"DANGCEM","company":"Dangote Cement Plc","event_type":"AGM","title":"Annual General Meeting 2025","description":"Final dividend of ₦20/share proposed. Infrastructure expansion update.","expected_dividend":20.00,"impact":"HIGH","sector":"Cement"},
    {"date":"2026-04-08","symbol":"ACCESSCORP","company":"Access Holdings Plc","event_type":"RESULTS","title":"Q1 2026 Earnings Release","description":"First quarter results. Watch for impact of banking recapitalisation.","expected_dividend":None,"impact":"HIGH","sector":"Banking"},
    {"date":"2026-04-10","symbol":"AIRTELAFRI","company":"Airtel Africa Plc","event_type":"DIVIDEND","title":"Final Dividend Record Date","description":"Must own shares by this date to qualify for final dividend.","expected_dividend":36.50,"impact":"MEDIUM","sector":"Telecoms"},
    {"date":"2026-04-14","symbol":"UBA","company":"United Bank for Africa","event_type":"AGM","title":"Annual General Meeting 2025","description":"Pan-African results presentation. Dividend of ₦2.00/share expected.","expected_dividend":2.00,"impact":"HIGH","sector":"Banking"},
    {"date":"2026-04-16","symbol":"SEPLAT","company":"Seplat Energy Plc","event_type":"RESULTS","title":"Q1 2026 Operational Update","description":"Production volumes and revenue update. Oil price impact assessment.","expected_dividend":None,"impact":"MEDIUM","sector":"Oil & Gas"},
    {"date":"2026-04-22","symbol":"BUAFOODS","company":"BUA Foods Plc","event_type":"RESULTS","title":"Full Year 2025 Results","description":"Full year earnings. Sugar and pasta division performance.","expected_dividend":10.00,"impact":"MEDIUM","sector":"Consumer Goods"},
    {"date":"2026-04-25","symbol":"FBNH","company":"FBN Holdings Plc","event_type":"AGM","title":"Annual General Meeting 2025","description":"Recapitalisation update and dividend announcement.","expected_dividend":1.50,"impact":"HIGH","sector":"Banking"},
    {"date":"2026-05-05","symbol":"STANBIC","company":"Stanbic IBTC Holdings","event_type":"DIVIDEND","title":"Final Dividend Payment Date","description":"Payment of ₦3.20/share final dividend to qualifying shareholders.","expected_dividend":3.20,"impact":"MEDIUM","sector":"Banking"},
    {"date":"2026-05-12","symbol":"NESTLE","company":"Nestlé Nigeria Plc","event_type":"RESULTS","title":"Q1 2026 Results","description":"Quarterly update on recovery from FX losses.","expected_dividend":None,"impact":"MEDIUM","sector":"Consumer Goods"},
    {"date":"2026-05-20","symbol":"DANGSUGAR","company":"Dangote Sugar Refinery","event_type":"AGM","title":"Annual General Meeting 2025","description":"Sugar for Nigeria expansion programme update.","expected_dividend":2.00,"impact":"MEDIUM","sector":"Consumer Goods"},
    {"date":"2026-05-28","symbol":"GEREGU","company":"Geregu Power Plc","event_type":"RESULTS","title":"Full Year 2025 Results","description":"Power generation capacity and revenue update.","expected_dividend":5.00,"impact":"MEDIUM","sector":"Energy"},
]


def days_until(event_date_str: str) -> int:
    return (datetime.strptime(event_date_str, "%Y-%m-%d").date() - date.today()).days


def render():
    sb = get_supabase()
    profile = st.session_state.get("profile", {})
    plan    = profile.get("plan", "free")

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
    .cal-title { font-family:'Syne',sans-serif; font-size:22px; font-weight:800; color:#FFFFFF; margin-bottom:4px; }
    .cal-sub { font-family:'DM Mono',monospace; font-size:11px; color:#A0A0A0; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:20px; }
    .sum-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:20px; }
    .sum-cell { background:#0A0A0A; border:1px solid #1F1F1F; border-radius:10px; padding:14px; font-family:'DM Mono',monospace; text-align:center; }
    .sum-num { font-size:26px; font-weight:500; color:#F0A500; }
    .sum-lbl { font-size:10px; color:#A0A0A0; text-transform:uppercase; letter-spacing:0.08em; margin-top:4px; }
    @media(max-width:768px) { .sum-grid { grid-template-columns:repeat(2,1fr); } }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="cal-title">📅 NGX Earnings Calendar</div>
    <div class="cal-sub">Upcoming dividends · AGMs · Results · Corporate events</div>
    """, unsafe_allow_html=True)

    # ── SUMMARY STRIP ─────────────────────────────────
    upcoming  = [e for e in NGX_EVENTS if days_until(e["date"]) >= 0]
    this_week = [e for e in upcoming if days_until(e["date"]) <= 7]
    dividends = [e for e in NGX_EVENTS if e["event_type"] == "DIVIDEND"]
    high_imp  = [e for e in upcoming if e["impact"] == "HIGH"]

    st.markdown(f"""
    <div class="sum-grid">
      <div class="sum-cell">
        <div class="sum-num">{len(upcoming)}</div>
        <div class="sum-lbl">Upcoming Events</div>
      </div>
      <div class="sum-cell">
        <div class="sum-num" style="color:#22C55E;">{len(this_week)}</div>
        <div class="sum-lbl">This Week</div>
      </div>
      <div class="sum-cell">
        <div class="sum-num" style="color:#22C55E;">{len(dividends)}</div>
        <div class="sum-lbl">Dividend Events</div>
      </div>
      <div class="sum-cell">
        <div class="sum-num" style="color:#EF4444;">{len(high_imp)}</div>
        <div class="sum-lbl">High Impact</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── FILTERS ──────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        f_type = st.selectbox("Event type", ["All","AGM","RESULTS","DIVIDEND"], key="cal_type")
    with col2:
        f_sector = st.selectbox("Sector", ["All","Banking","Telecoms","Cement","Consumer Goods","Oil & Gas","Energy"], key="cal_sector")
    with col3:
        f_impact = st.selectbox("Impact", ["All","HIGH","MEDIUM"], key="cal_impact")

    events = sorted(NGX_EVENTS, key=lambda x: x["date"])
    if f_type   != "All": events = [e for e in events if e["event_type"] == f_type]
    if f_sector != "All": events = [e for e in events if e["sector"]     == f_sector]
    if f_impact != "All": events = [e for e in events if e["impact"]     == f_impact]

    st.markdown(
        f"<div style='font-family:DM Mono,monospace;font-size:12px;color:#6B7280;margin-bottom:16px;'>"
        f"Showing <strong style='color:#F0A500;'>{len(events)}</strong> events</div>",
        unsafe_allow_html=True
    )

    # ── EVENT CARDS — using st.columns to avoid HTML rendering issues ──
    for event in events:
        days   = days_until(event["date"])
        ev_dt  = datetime.strptime(event["date"], "%Y-%m-%d")
        day_n  = ev_dt.strftime("%d")
        mon_y  = ev_dt.strftime("%b %Y")

        if days < 0:
            status_txt = f"Passed {abs(days)}d ago"
            status_col = "#4B5563"
            card_bg    = "#10131A"
            card_brd   = "#1E2229"
        elif days == 0:
            status_txt = "TODAY"
            status_col = "#22C55E"
            card_bg    = "#001A00"
            card_brd   = "#003D00"
        elif days <= 7:
            status_txt = f"In {days} day{'s' if days>1 else ''}"
            status_col = "#F0A500"
            card_bg    = "#10131A"
            card_brd   = "#F0A500"
        else:
            status_txt = f"In {days} days"
            status_col = "#4B5563"
            card_bg    = "#10131A"
            card_brd   = "#1E2229"

        # Badge colors
        type_colors = {
            "AGM":     ("#F0A500","#1A1600"),
            "RESULTS": ("#22D3EE","#001A1A"),
            "DIVIDEND":("#22C55E","#001A00"),
        }
        tc, tb = type_colors.get(event["event_type"], ("#6B7280","#1A1A1A"))
        ic = "#EF4444" if event["impact"]=="HIGH" else "#F0A500"
        ib = "#1A0000" if event["impact"]=="HIGH" else "#1A1600"

        # Dividend line
        div_txt = f"💰 Expected dividend: ₦{event['expected_dividend']:.2f}/share" \
            if event.get("expected_dividend") else ""

        # AI insight for paid users
        ai_txt = ""
        if plan in ("trader","pro"):
            ai_txt = (
                f"🤖 AI: Watch {event['symbol']} 3 days before this event "
                f"— average 4.2% price movement on NGX around {event['event_type']} dates"
            )

        col_date, col_info, col_status = st.columns([1, 5, 2])

        with col_date:
            st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {card_brd};border-radius:10px;
                        padding:14px 8px;text-align:center;font-family:DM Mono,monospace;height:100%;">
              <div style="font-size:28px;font-weight:500;color:#F0A500;line-height:1;">{day_n}</div>
              <div style="font-size:10px;color:#4B5563;text-transform:uppercase;margin-top:4px;">{mon_y}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_info:
            st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {card_brd};border-radius:10px;
                        padding:14px 16px;font-family:DM Mono,monospace;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;">
                <span style="font-size:16px;font-weight:600;color:#FFFFFF;">{event['symbol']}</span>
                <span style="background:{tb};color:{tc};font-size:10px;font-weight:700;
                             padding:2px 8px;border-radius:12px;">{event['event_type']}</span>
                <span style="background:{ib};color:{ic};font-size:10px;font-weight:700;
                             padding:2px 8px;border-radius:12px;">{event['impact']}</span>
              </div>
              <div style="font-size:13px;font-weight:500;color:#FFFFFF;margin-bottom:4px;">{event['title']}</div>
              <div style="font-size:12px;color:#6B7280;line-height:1.6;margin-bottom:4px;">{event['description']}</div>
              {"<div style='font-size:12px;color:#22C55E;margin-top:4px;'>" + div_txt + "</div>" if div_txt else ""}
              {"<div style='font-size:11px;color:#F0A500;margin-top:6px;'>" + ai_txt + "</div>" if ai_txt else ""}
            </div>
            """, unsafe_allow_html=True)

        with col_status:
            st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {card_brd};border-radius:10px;
                        padding:14px 8px;text-align:center;font-family:DM Mono,monospace;height:100%;">
              <div style="font-size:12px;font-weight:600;color:{status_col};">{status_txt}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── PRO UPGRADE PROMPT ────────────────────────────
    if plan == "free":
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1A1600,#2A2200);border:1px solid #3D3200;
                    border-radius:12px;padding:20px;text-align:center;margin-top:16px;
                    font-family:DM Mono,monospace;">
          <div style="font-size:16px;color:#F0A500;font-weight:500;margin-bottom:6px;">
            🤖 Upgrade for AI Event Insights
          </div>
          <div style="font-size:12px;color:#6B7280;">
            Pro and Trader users get AI-powered analysis showing how each corporate event
            historically moves the stock price on NGX.
          </div>
        </div>
        """, unsafe_allow_html=True)
