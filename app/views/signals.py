import streamlit as st
from app.utils.supabase_client import get_supabase
from app.components.inline_alert_widget import load_user_alerts, render_alert_widget, _bell_label
from app.utils.webpushr import maybe_push_signal

SIGNAL_CONFIG = {
    "STRONG_BUY":     ("#16A34A", "⭐⭐⭐⭐⭐", "STRONG BUY"),
    "BUY":            ("#22C55E", "⭐⭐⭐⭐",   "BUY"),
    "BREAKOUT_WATCH": ("#3B82F6", "⭐⭐⭐⭐",   "BREAKOUT WATCH"),
    "HOLD":           ("#D97706", "⭐⭐⭐",     "HOLD"),
    "CAUTION":        ("#EA580C", "⭐⭐",       "CAUTION"),
    "AVOID":          ("#DC2626", "⭐",         "AVOID"),
}
DEFAULT_CONFIG = ("#6B7280", "⭐⭐⭐", "HOLD")


# ══════════════════════════════════════════════════════════════
# RICH NARRATIVE GENERATOR
# Produces a full plain-English analysis for every stock using
# only the numeric data already in signal_scores + stock_prices.
# No external API calls — deterministic, instant, always runs.
# ══════════════════════════════════════════════════════════════

def generate_signal_narrative(
    symbol: str,
    signal_code: str,
    stars: int,
    price: float,
    chg: float,
    volume: int,
    momentum: float,   # 0-1
    vol_score: float,  # 0-1
    composite: float,  # 0-1  (news_score field)
    db_reasoning: str = "",
) -> str:
    """
    Returns a rich, multi-sentence signal narrative.
    If the DB already has a long, meaningful narrative (>120 chars) it is
    kept as-is. Otherwise a full narrative is generated from the numbers.
    """
    # Keep rich DB content when it exists
    if db_reasoning and len(db_reasoning.strip()) > 120:
        return db_reasoning.strip()

    # ── No price data edge-case ───────────────────────
    if price <= 0:
        return (
            f"No price data has been recorded for {symbol} yet. "
            f"This stock exists on the NGX but the scraper has not yet "
            f"collected its pricing data — this typically happens for "
            f"low-liquidity or recently listed equities. "
            f"It will appear with full analysis on the next successful market data run."
        )

    # ── Helper values ─────────────────────────────────
    abs_chg   = abs(chg)
    is_gain   = chg >= 0
    arrow     = "▲" if is_gain else "▼"
    chg_str   = "{:+.2f}".format(chg)
    price_str = "₦{:,.2f}".format(price)
    m_pct     = int(min(momentum,  1.0) * 100)
    v_pct     = int(min(vol_score, 1.0) * 100)
    c_pct     = int(min(composite, 1.0) * 100)
    vol_str   = "{:,}".format(volume) if volume > 0 else "N/A"

    # ── Momentum narrative ────────────────────────────
    if m_pct >= 75:
        mom_line = (
            f"Momentum is strong at {m_pct}% — buyers have been in control "
            f"across recent sessions, with consistent upward pressure on the price."
        )
    elif m_pct >= 50:
        mom_line = (
            f"Momentum reads {m_pct}% — solidly positive. "
            f"The stock has been trending in the right direction, "
            f"with more up-days than down-days in recent trading."
        )
    elif m_pct >= 30:
        mom_line = (
            f"Momentum is moderate at {m_pct}%. "
            f"Price action has been mixed — some sessions up, some flat, "
            f"suggesting the market is still forming a view on {symbol}."
        )
    else:
        mom_line = (
            f"Momentum is weak at {m_pct}%. "
            f"Recent sessions have shown little upward conviction, "
            f"and price has been drifting or declining."
        )

    # ── Volume narrative ──────────────────────────────
    if v_pct >= 75:
        vol_line = (
            f"Volume is significantly above average ({v_pct}% score) — "
            f"{vol_str} shares changed hands today. "
            f"When volume surges like this, it usually means real money is moving, "
            f"not just noise."
        )
    elif v_pct >= 50:
        vol_line = (
            f"Trading volume is above average ({v_pct}% score, {vol_str} shares). "
            f"More participants than usual are engaging with {symbol} today, "
            f"which adds weight to the current price move."
        )
    elif v_pct >= 25:
        vol_line = (
            f"Volume is around average ({v_pct}% score, {vol_str} shares). "
            f"A normal crowd — enough for the move to be real, "
            f"but not a standout conviction day."
        )
    else:
        vol_line = (
            f"Volume is thin ({v_pct}% score, {vol_str} shares). "
            f"Few participants traded {symbol} today. "
            f"Moves on low volume are easier to reverse — treat with caution."
        )

    # ── Today's price move narrative ──────────────────
    if abs_chg >= 9.5 and is_gain:
        move_line = (
            f"{symbol} hit the NGX daily ceiling today, surging {chg_str}% to {price_str}. "
            f"Buyers so dominated that the exchange had to cap the move. "
            f"Something significant — news, earnings, or a large order — triggered this."
        )
    elif abs_chg >= 9.5 and not is_gain:
        move_line = (
            f"{symbol} hit the NGX daily floor, falling {chg_str}% to {price_str}. "
            f"Sellers flooded out and the exchange's circuit breaker kicked in. "
            f"Watch for the catalyst — this level of selling rarely happens without cause."
        )
    elif abs_chg >= 5 and is_gain:
        move_line = (
            f"{symbol} gained {chg_str}% today to close at {price_str} — "
            f"a strong single-session move. "
            f"This kind of gain on the NGX reflects real conviction, "
            f"not just routine trading."
        )
    elif abs_chg >= 5 and not is_gain:
        move_line = (
            f"{symbol} fell {chg_str}% to {price_str} — a sharp pull-back. "
            f"Sellers have taken control and the stock is giving back recent gains. "
            f"The question is whether this is profit-taking or a shift in sentiment."
        )
    elif abs_chg >= 2 and is_gain:
        move_line = (
            f"{symbol} moved up {chg_str}% to {price_str}. "
            f"A meaningful but measured gain — the kind that suggests steady "
            f"buyer interest rather than speculative excitement."
        )
    elif abs_chg >= 2 and not is_gain:
        move_line = (
            f"{symbol} slipped {chg_str}% to {price_str}. "
            f"A moderate dip — sellers nudging the price lower to attract buyers. "
            f"Not a crisis, but worth watching for follow-through."
        )
    else:
        move_line = (
            f"{symbol} barely moved today ({chg_str}%) and is currently priced at {price_str}. "
            f"The market is taking a breath — no strong push in either direction."
        )

    # ── Composite / overall signal verdict ────────────
    if signal_code == "STRONG_BUY":
        verdict = (
            f"With {stars} stars and a composite score of {c_pct}%, "
            f"this is one of the highest-conviction signals on the NGX today. "
            f"All three scoring dimensions — momentum, volume, and composite — "
            f"are aligned. The risk/reward at current levels is favourable for "
            f"investors with a medium-term horizon."
        )
    elif signal_code == "BUY":
        verdict = (
            f"This is a BUY signal with {stars} stars and a composite score of {c_pct}%. "
            f"The setup is positive: momentum is building and volume is supporting the move. "
            f"Wait for the market to open and confirm the trend before entering."
        )
    elif signal_code == "BREAKOUT_WATCH":
        verdict = (
            f"A BREAKOUT WATCH signal with {stars} stars — the stock is approaching "
            f"a level where a decisive move is likely. "
            f"Composite score sits at {c_pct}%. "
            f"Watch for volume expansion as confirmation: if the next session "
            f"brings higher volume alongside a price push, that is your green light."
        )
    elif signal_code == "HOLD":
        verdict = (
            f"The signal is HOLD ({stars} stars, composite {c_pct}%). "
            f"There is no urgent reason to buy or sell — "
            f"the stock is in a neutral zone. "
            f"Existing holders should stay patient; new buyers should wait "
            f"for a cleaner entry or stronger signal."
        )
    elif signal_code == "CAUTION":
        verdict = (
            f"CAUTION is warranted here ({stars} stars, composite {c_pct}%). "
            f"The data shows deteriorating conditions — weakening momentum "
            f"or declining volume behind recent moves. "
            f"Tighten stop-losses if you hold, and avoid new positions until "
            f"conditions improve."
        )
    elif signal_code == "AVOID":
        verdict = (
            f"This stock is rated AVOID ({stars} star, composite {c_pct}%). "
            f"All scoring dimensions point negative. "
            f"There is no technical case for a new position at this time. "
            f"Let the stock stabilise and build a new base before reconsidering."
        )
    else:
        verdict = (
            f"Composite score: {c_pct}%. "
            f"Review the score breakdown below before making any decision."
        )

    # ── Assemble final narrative ───────────────────────
    # Use the DB short text as a lead-in quote if it exists and is non-trivial
    lead = ""
    if db_reasoning and len(db_reasoning.strip()) > 10:
        lead = db_reasoning.strip().rstrip(".") + ". "

    return lead + move_line + " " + mom_line + " " + vol_line + " " + verdict


def render():
    sb = get_supabase()

    profile  = st.session_state.get("profile", {})
    plan     = profile.get("plan", "free")
    user     = st.session_state.get("user")
    alerts_by_symbol = load_user_alerts(sb, user)

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
    .sig-header { font-family:'Syne',sans-serif; font-size:22px; font-weight:800; color:#E8E2D4; margin-bottom:4px; }
    .sig-sub { font-family:'DM Mono',monospace; font-size:11px; color:#4B5563; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:20px; }
    .sig-count { font-family:'DM Mono',monospace; font-size:12px; color:#6B7280; margin-bottom:12px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="sig-header">⭐ Signal Scores</div>
    <div class="sig-sub">AI-powered buy/sell/hold ratings — all NGX stocks</div>
    """, unsafe_allow_html=True)

    # ── FILTERS ──────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_signal = st.selectbox(
            "Filter by signal",
            ["All", "STRONG BUY", "BUY", "BREAKOUT WATCH",
             "HOLD", "CAUTION", "AVOID"],
            key="sig_filter"
        )
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Signal strength ↓", "Best % gain today",
             "Worst % loss today", "Highest volume", "Symbol A–Z"],
            key="sig_sort"
        )
    with col3:
        search = st.text_input(
            "Search symbol",
            placeholder="e.g. GTCO",
            key="sig_search"
        ).upper().strip()

    # ── FETCH ─────────────────────────────────────────
    scores_res = sb.table("signal_scores")\
        .select("*")\
        .order("score_date", desc=True)\
        .order("stars", desc=True)\
        .limit(500).execute()

    prices_res = sb.table("stock_prices")\
        .select("symbol, price, change_percent, volume")\
        .order("trading_date", desc=True)\
        .limit(500).execute()

    price_map = {}
    for p in (prices_res.data or []):
        if p["symbol"] not in price_map:
            price_map[p["symbol"]] = p

    # Deduplicate signals — keep latest per symbol
    seen = set()
    all_scores = []
    for s in (scores_res.data or []):
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            all_scores.append(s)

    label_to_code = {
        "STRONG BUY": "STRONG_BUY",
        "BUY": "BUY",
        "BREAKOUT WATCH": "BREAKOUT_WATCH",
        "HOLD": "HOLD",
        "CAUTION": "CAUTION",
        "AVOID": "AVOID",
    }

    # ── APPLY FILTERS ─────────────────────────────────
    filtered = all_scores[:]

    if filter_signal != "All":
        code = label_to_code.get(filter_signal, filter_signal)
        filtered = [
            s for s in filtered
            if s.get("signal", "").upper().replace(" ", "_") == code
            or s.get("signal", "") == filter_signal
        ]

    if search:
        filtered = [s for s in filtered if search in s.get("symbol", "")]

    # ── SORT ─────────────────────────────────────────
    if sort_by == "Best % gain today":
        filtered = sorted(
            filtered,
            key=lambda x: float(
                price_map.get(x["symbol"], {}).get("change_percent", 0) or 0
            ),
            reverse=True
        )
    elif sort_by == "Worst % loss today":
        filtered = sorted(
            filtered,
            key=lambda x: float(
                price_map.get(x["symbol"], {}).get("change_percent", 0) or 0
            )
        )
    elif sort_by == "Highest volume":
        filtered = sorted(
            filtered,
            key=lambda x: int(
                price_map.get(x["symbol"], {}).get("volume", 0) or 0
            ),
            reverse=True
        )
    elif sort_by == "Symbol A–Z":
        filtered = sorted(filtered, key=lambda x: x.get("symbol", ""))

    # ── DISTRIBUTION BAR ──────────────────────────────
    if all_scores:
        color_map = {
            "STRONG_BUY": "#16A34A", "STRONG BUY": "#16A34A",
            "BUY": "#22C55E",
            "BREAKOUT_WATCH": "#3B82F6", "BREAKOUT WATCH": "#3B82F6",
            "HOLD": "#D97706", "CAUTION": "#EA580C", "AVOID": "#DC2626",
        }
        dist = {}
        for s in all_scores:
            sig = s.get("signal", "HOLD")
            dist[sig] = dist.get(sig, 0) + 1

        parts = []
        for sig, cnt in sorted(dist.items(), key=lambda x: -x[1]):
            c = color_map.get(sig, "#6B7280")
            parts.append(
                f"<span style='color:{c};font-weight:600;'>{sig}</span>"
                f" <span style='color:#4B5563;'>{cnt}</span>"
            )
        st.markdown(
            "<div style='font-family:DM Mono,monospace;font-size:12px;"
            "margin-bottom:16px;display:flex;gap:16px;flex-wrap:wrap;'>"
            + " &nbsp;·&nbsp; ".join(parts) + "</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        f"<div class='sig-count'>Showing "
        f"<strong style='color:#F0A500;'>{len(filtered)}</strong> stocks</div>",
        unsafe_allow_html=True
    )

    if not filtered:
        st.info("No signals match your filter.")
        return

    # ── SIGNAL CARDS ─────────────────────────────────
    for s in filtered:
        symbol     = s.get("symbol", "")
        stars_num  = int(s.get("stars", 3))
        signal_raw = s.get("signal", "HOLD")
        reasoning  = s.get("reasoning", "")
        score_date = s.get("score_date", "")

        signal_code = signal_raw.upper().replace(" ", "_")
        cfg = SIGNAL_CONFIG.get(signal_code, DEFAULT_CONFIG)
        accent, stars_display, label = cfg

        price_data = price_map.get(symbol, {})
        price  = float(price_data.get("price", 0) or 0)
        chg    = float(price_data.get("change_percent", 0) or 0)
        volume = int(price_data.get("volume", 0) or 0)
        chg_color = "#22C55E" if chg >= 0 else "#EF4444"
        arrow     = "▲" if chg >= 0 else "▼"

        momentum  = float(s.get("momentum_score", 0) or 0)
        vol_score = float(s.get("volume_score", 0) or 0)
        composite = float(s.get("news_score", 0) or 0)

        # ── Split: short DB text shown above grid, rich narrative below score bars ──
        db_short = (s.get("reasoning", "") or "").strip()
        # Truncate DB text to 1-2 lines for the header display
        db_short_display = db_short if len(db_short) <= 140 else db_short[:137] + "…"

        rich_narrative = generate_signal_narrative(
            symbol       = symbol,
            signal_code  = signal_code,
            stars        = stars_num,
            price        = price,
            chg          = chg,
            volume       = volume,
            momentum     = momentum,
            vol_score    = vol_score,
            composite    = composite,
            db_reasoning = db_short,
        )

        # ── Fire push notification for BULLISH / BREAKOUT signals ────────────
        # Deduplication inside maybe_push_signal prevents repeat sends.
        maybe_push_signal(
            symbol      = symbol,
            signal_code = signal_code,
            narrative   = rich_narrative,
            price       = price,
            chg         = chg,
        )

        # Entry / Target / Stop Loss values
        entry_price = target_price = stop_loss = potential = None
        if signal_code in ("STRONG_BUY", "BUY", "BREAKOUT_WATCH") and price > 0:
            entry_price  = round(price * 1.002, 2)
            multiplier   = 1.12 if stars_num >= 5 else 1.08 if stars_num >= 4 else 1.06
            target_price = round(price * multiplier, 2)
            stop_loss    = round(price * 0.95, 2)
            potential    = round(((target_price - entry_price) / entry_price) * 100, 1)

        price_display = f"₦{price:,.2f}" if price > 0 else "No price data"
        vol_display   = f"Vol: {volume:,}" if volume > 0 else ""

        # Score percentages
        m_pct = int(min(momentum,  1.0) * 100)
        v_pct = int(min(vol_score, 1.0) * 100)
        c_pct = int(min(composite, 1.0) * 100)

        # ── Dynamic height calculation ─────────────────────────────────────
        # Estimate rendered lines for each content block at ~55 chars/line on mobile
        CHARS_PER_LINE = 55
        PX_PER_LINE    = 18   # line-height ~1.75 * 11px font

        def est_height(text: str, font_px: int = 11, lh: float = 1.75) -> int:
            if not text:
                return 0
            lines = max(1, len(text) // CHARS_PER_LINE + text.count("\n"))
            return int(lines * font_px * lh) + 10

        h_badge      = 30
        h_db_short   = est_height(db_short_display, 11, 1.55) if db_short_display else 0
        h_action     = 90 if entry_price else 0
        h_scores     = 70
        h_narrative  = est_height(rich_narrative, 11, 1.75)
        h_disclaimer = 24
        h_padding    = 40   # body padding + section gaps

        card_height = (
            h_badge + h_db_short + h_action +
            h_scores + h_narrative + h_disclaimer + h_padding
        )
        # Clamp: never shorter than 280px, never taller than 1400px
        card_height = max(280, min(card_height, 1400))

        with st.expander(
            f"{stars_display}  {symbol}  —  {label}  ·  {price_display}"
            f"  {_bell_label(symbol, alerts_by_symbol)}",
            expanded=False
        ):
            st.components.v1.html(f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap"
                  rel="stylesheet">
            <style>
              *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
              html {{ font-size:13px; }}
              body {{
                background: transparent;
                font-family: 'DM Mono', monospace;
                color: #E8E2D4;
                overflow-x: hidden;
                overflow-y: visible;
                padding: 4px 0 10px 0;
              }}
              /* ── Badge row ── */
              .badge-row {{
                display:flex; align-items:center; gap:8px;
                flex-wrap:wrap; margin-bottom:8px;
              }}
              .signal-badge {{
                font-size:10px; font-weight:700;
                padding:3px 10px; border-radius:20px;
                text-transform:uppercase; letter-spacing:0.05em;
                color:#fff; background:{accent};
              }}
              .chg-val {{ font-size:12px; font-weight:600; color:{chg_color}; }}
              .vol-val {{ font-size:10px; color:#4B5563; }}
              .date-val {{ font-size:10px; color:#374151; margin-left:auto; }}

              /* ── Short DB text ── */
              .db-text {{
                font-size:11px; color:#9CA3AF; line-height:1.55;
                margin-bottom:8px;
              }}

              /* ── Action grid ── */
              .action-grid {{
                display:grid; grid-template-columns:repeat(3,1fr);
                gap:6px; margin:8px 0;
              }}
              .action-cell {{
                border-radius:7px; padding:9px 6px; text-align:center;
              }}
              .action-lbl {{
                font-size:9px; text-transform:uppercase;
                letter-spacing:0.07em; margin-bottom:4px; color:#4B5563;
              }}
              .action-val {{ font-size:15px; font-weight:500; }}
              .action-sub {{ font-size:10px; margin-top:2px; }}

              /* ── Score bars ── */
              .scores {{
                margin:8px 0 0 0; padding-top:8px;
                border-top:1px solid #1E2229;
              }}
              .scores-title {{
                font-size:9px; color:#4B5563; text-transform:uppercase;
                letter-spacing:0.08em; margin-bottom:7px;
              }}
              .scores-grid {{
                display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;
              }}
              .score-lbl {{ font-size:9px; color:#4B5563; margin-bottom:4px; }}
              .bar-track {{
                background:#1A1D24; border-radius:4px;
                height:4px; margin-bottom:2px;
              }}
              .bar-fill {{ border-radius:4px; height:4px; }}
              .score-num {{ font-size:10px; }}

              /* ── Rich narrative ── */
              .narrative {{
                background:#0A0C0F; border:1px solid #1E2229;
                border-left:3px solid {accent}; border-radius:7px;
                padding:10px 12px; font-size:11px; color:#E8E2D4;
                line-height:1.75; margin-top:8px;
              }}

              /* ── Disclaimer ── */
              .disclaimer {{
                font-size:9px; color:#374151; margin-top:8px;
                padding-top:6px; border-top:1px solid #1A1D24;
              }}

              @media (max-width:400px) {{
                html {{ font-size:12px; }}
                .action-val {{ font-size:13px; }}
                .narrative {{ font-size:10.5px; line-height:1.7; }}
              }}
            </style>
            <script>
              function resize() {{
                var h = document.body.scrollHeight + 16;
                window.parent.postMessage({{type:'streamlit:setFrameHeight', height:h}}, '*');
              }}
              window.addEventListener('load', function(){{ resize(); setTimeout(resize, 600); }});
              new MutationObserver(resize).observe(document.body, {{subtree:true, childList:true}});
            </script>
            </head>
            <body>

              <!-- 1. Badge + change row -->
              <div class="badge-row">
                <span class="signal-badge">{label}</span>
                <span class="chg-val">{arrow} {abs(chg):.2f}% today</span>
                {'<span class="vol-val">' + vol_display + '</span>' if vol_display else ''}
                <span class="date-val">{score_date}</span>
              </div>

              <!-- 2. Short DB text -->
              {f'<div class="db-text">{db_short_display}</div>' if db_short_display else ''}

              <!-- 3. Entry / Target / Stop Loss -->
              {f'''<div class="action-grid">
                <div class="action-cell" style="background:#001A00;border:1px solid #003D00;">
                  <div class="action-lbl">&#10003; Entry</div>
                  <div class="action-val" style="color:#22C55E;">&#8358;{entry_price:,.2f}</div>
                </div>
                <div class="action-cell" style="background:#001A1A;border:1px solid #003D3D;">
                  <div class="action-lbl">&#127919; Target</div>
                  <div class="action-val" style="color:#22D3EE;">&#8358;{target_price:,.2f}</div>
                  <div class="action-sub" style="color:#22D3EE;">+{potential}%</div>
                </div>
                <div class="action-cell" style="background:#1A0000;border:1px solid #3D0000;">
                  <div class="action-lbl">&#128721; Stop Loss</div>
                  <div class="action-val" style="color:#EF4444;">&#8358;{stop_loss:,.2f}</div>
                </div>
              </div>''' if entry_price and target_price and stop_loss else ''}

              <!-- 4. Score bars -->
              <div class="scores">
                <div class="scores-title">Score Breakdown</div>
                <div class="scores-grid">
                  <div>
                    <div class="score-lbl">Momentum</div>
                    <div class="bar-track">
                      <div class="bar-fill" style="background:#F0A500;width:{m_pct}%;"></div>
                    </div>
                    <div class="score-num" style="color:#F0A500;">{m_pct}%</div>
                  </div>
                  <div>
                    <div class="score-lbl">Volume</div>
                    <div class="bar-track">
                      <div class="bar-fill" style="background:#22D3EE;width:{v_pct}%;"></div>
                    </div>
                    <div class="score-num" style="color:#22D3EE;">{v_pct}%</div>
                  </div>
                  <div>
                    <div class="score-lbl">Composite</div>
                    <div class="bar-track">
                      <div class="bar-fill" style="background:#A78BFA;width:{c_pct}%;"></div>
                    </div>
                    <div class="score-num" style="color:#A78BFA;">{c_pct}%</div>
                  </div>
                </div>
              </div>

              <!-- 5. Rich narrative -->
              <div class="narrative">{rich_narrative}</div>

              <!-- 6. Disclaimer -->
              <div class="disclaimer">
                &#9888;&#65039; Signal scores are educational only —
                not financial advice. Always do your own research.
              </div>

            </body>
            </html>
            """, height=card_height, scrolling=True)

            # ── Inline alert widget ──────────────────────────
            render_alert_widget(sb, user, plan, symbol, price, alerts_by_symbol)
