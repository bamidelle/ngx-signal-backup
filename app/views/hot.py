import streamlit as st
from datetime import date, timedelta
from app.utils.supabase_client import get_supabase


def build_sparkline(prices: list, color: str,
                    width: int = 130, height: int = 44) -> str:
    """Build an inline SVG sparkline from price history."""
    if not prices or len(prices) < 2:
        return ""
    mn, mx = min(prices), max(prices)
    rng    = mx - mn if mx != mn else 1.0
    n      = len(prices)
    step   = width / (n - 1)

    pts = []
    for i, p in enumerate(prices):
        x = round(i * step, 1)
        y = round(height - ((p - mn) / rng) * (height - 6) - 3, 1)
        pts.append(f"{x},{y}")

    polyline  = " ".join(pts)
    fill_pts  = f"0,{height} " + polyline + f" {width},{height}"
    cid       = color.replace("#", "g")

    return f"""
    <svg width="{width}" height="{height}"
         viewBox="0 0 {width} {height}"
         xmlns="http://www.w3.org/2000/svg"
         style="display:block;">
      <defs>
        <linearGradient id="{cid}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="{color}" stop-opacity="0.25"/>
          <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <polygon points="{fill_pts}" fill="url(#{cid})"/>
      <polyline points="{polyline}" fill="none"
                stroke="{color}" stroke-width="1.8"
                stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    """


def generate_analysis(symbol: str, price: float,
                       chg: float, history: list,
                       volume: int, avg_volume: float) -> str:
    """
    Generate plain-English narrative from 30-day price history.
    Explains why the stock moved today based on context.
    """
    if not history or len(history) < 2:
        return (
            f"Limited historical data is available for {symbol}. "
            f"The NGX Signal scraper has tracked this stock for fewer "
            f"than 2 trading sessions, so there is not yet enough context "
            f"to explain today's move of {chg:+.2f}% in detail. "
            f"As more trading days accumulate, this section will show "
            f"trend context, volume analysis, and support/resistance levels. "
            f"Check back after a few more market days."
        )

    prices_list  = [float(h["price"]) for h in history if h.get("price")]
    if not prices_list:
        return f"Price history not yet recorded for {symbol}."

    oldest_price = prices_list[0]
    period_days  = len(history)
    period_chg   = (
        (price - oldest_price) / oldest_price * 100
    ) if oldest_price > 0 else 0

    high_30  = max(prices_list)
    low_30   = min(prices_list)
    near_high = price >= high_30 * 0.97
    near_low  = price <= low_30  * 1.03

    # Moving averages
    ma5  = sum(prices_list[-5:]) / min(5, len(prices_list))
    ma20 = sum(prices_list[-20:]) / min(20, len(prices_list)) \
           if len(prices_list) >= 5 else None

    trend = "upward" if ma5 > (ma20 or ma5) * 1.005 else \
            "downward" if ma5 < (ma20 or ma5) * 0.995 else "sideways"

    # Volatility
    if len(prices_list) >= 3:
        diffs = [
            abs(prices_list[i] - prices_list[i-1]) / prices_list[i-1] * 100
            for i in range(1, len(prices_list))
            if prices_list[i-1] > 0
        ]
        avg_daily_move = sum(diffs) / len(diffs) if diffs else 0
        is_volatile    = avg_daily_move > 2.0
    else:
        avg_daily_move = 0
        is_volatile    = False

    # Volume context
    vol_context = ""
    if avg_volume > 0 and volume > 0:
        ratio = volume / avg_volume
        if ratio > 2.0:
            vol_context = (
                f" Today's volume ({volume:,}) is {ratio:.1f}× the "
                f"30-day average — an unusually strong "
                f"{'buying' if chg > 0 else 'selling'} signal."
            )
        elif ratio > 1.3:
            vol_context = (
                f" Volume is above average at {ratio:.1f}×, "
                f"supporting the {'move up' if chg > 0 else 'decline'}."
            )
        elif ratio < 0.5:
            vol_context = (
                f" Volume is very low ({ratio:.1f}× average), "
                f"suggesting today's move may lack conviction."
            )

    # Build narrative
    parts = []

    if chg > 0:
        if near_high:
            parts.append(
                f"{symbol} gained {chg:+.2f}% to reach ₦{price:,.2f}, "
                f"which is near its 30-day high of ₦{high_30:,.2f}. "
                f"Breaking above this level could signal continued strength."
            )
        else:
            parts.append(
                f"{symbol} rose {chg:+.2f}% today to ₦{price:,.2f}."
            )
        parts.append(vol_context)

        if trend == "upward":
            parts.append(
                f" The 5-day moving average (₦{ma5:,.2f}) is trending "
                f"upward, consistent with a {period_days}-day uptrend "
                f"of {period_chg:+.1f}%."
            )
        elif trend == "downward":
            parts.append(
                f" Despite today's gain, the broader {period_days}-day "
                f"trend has been downward ({period_chg:+.1f}%). "
                f"This could be a temporary relief rally — "
                f"watch for follow-through in the next session."
            )
        else:
            parts.append(
                f" Price has been moving sideways over the past "
                f"{period_days} days ({period_chg:+.1f}% net change)."
            )

    else:
        if near_low:
            parts.append(
                f"{symbol} fell {chg:.2f}% to ₦{price:,.2f}, "
                f"approaching its 30-day low of ₦{low_30:,.2f}. "
                f"A break below this level could invite further selling."
            )
        else:
            parts.append(
                f"{symbol} declined {chg:.2f}% today to ₦{price:,.2f}."
            )
        parts.append(vol_context)

        if trend == "downward":
            parts.append(
                f" The 5-day moving average (₦{ma5:,.2f}) is in a "
                f"downtrend over {period_days} days ({period_chg:+.1f}%). "
                f"Wait for stabilisation before considering entry."
            )
        elif trend == "upward":
            parts.append(
                f" Despite today's dip, {symbol} is still up "
                f"{period_chg:+.1f}% over {period_days} days — "
                f"this may be a healthy pullback in an uptrend."
            )

    if is_volatile:
        parts.append(
            f" {symbol} has been volatile, averaging "
            f"{avg_daily_move:.1f}% daily swings — consider "
            f"sizing positions conservatively."
        )

    parts.append(
        f" 30-day range: ₦{low_30:,.2f} – ₦{high_30:,.2f}."
    )

    return " ".join(p for p in parts if p.strip())


def render_stock_card(s: dict, is_gain: bool,
                      history_map: dict, avg_vol_map: dict):
    symbol = s["symbol"]
    price  = float(s.get("price", 0) or 0)
    chg    = float(s.get("change_percent", 0) or 0)
    volume = int(s.get("volume", 0) or 0)
    color  = "#22C55E" if is_gain else "#EF4444"
    arrow  = "▲" if is_gain else "▼"
    bg     = "#001A00" if is_gain else "#1A0000"
    border = "#003D00" if is_gain else "#3D0000"

    history   = history_map.get(symbol, [])
    avg_vol   = avg_vol_map.get(symbol, 0)
    p_series  = [float(h["price"]) for h in history if h.get("price")]

    sparkline    = build_sparkline(p_series, color) if len(p_series) >= 2 else ""
    analysis     = generate_analysis(symbol, price, chg, history, volume, avg_vol)
    period_days  = len(history)

    # 30-day stats
    period_chg_html = ""
    if p_series and len(p_series) >= 2:
        pc = ((p_series[-1] - p_series[0]) / p_series[0]) * 100
        pc_color = "#22C55E" if pc >= 0 else "#EF4444"
        period_chg_html = (
            f"<div style='font-size:11px;color:{pc_color};margin-top:2px;'>"
            f"{pc:+.1f}% over {period_days}d</div>"
        )

    # Volume vs average
    vol_ratio_html = ""
    if avg_vol > 0 and volume > 0:
        ratio = volume / avg_vol
        rcol  = "#22C55E" if ratio > 1.2 else \
                "#EF4444" if ratio < 0.8 else "#6B7280"
        vol_ratio_html = (
            f"<div style='font-size:11px;color:{rcol};'>"
            f"{ratio:.1f}x avg vol</div>"
        )

    # 30-day range
    range_html = ""
    if p_series:
        lo, hi = min(p_series), max(p_series)
        range_html = (
            f"<div style='font-size:11px;color:#4B5563;'>"
            f"30d: &#8358;{lo:,.2f} – &#8358;{hi:,.2f}</div>"
        )

    card_h = 360 if len(p_series) >= 2 else 280

    with st.expander(
        f"{arrow} {symbol}  ·  {abs(chg):.2f}%  ·  ₦{price:,.2f}",
        expanded=False
    ):
        st.components.v1.html(f"""
        <!DOCTYPE html><html>
        <head>
        <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap"
              rel="stylesheet">
        <style>
          *{{margin:0;padding:0;box-sizing:border-box;}}
          body{{background:transparent;font-family:'DM Mono',monospace;
                color:#FFFFFF;overflow:hidden;padding:4px 0 6px 0;}}
        </style>
        </head>
        <body>

          <!-- Header row: symbol + chart -->
          <div style="display:flex;justify-content:space-between;
                      align-items:flex-start;margin-bottom:12px;">
            <div>
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
                <span style="font-size:20px;font-weight:700;color:#FFFFFF;">{symbol}</span>
                <span style="font-size:15px;font-weight:500;color:{color};">
                  {arrow} {abs(chg):.2f}%
                </span>
              </div>
              <div style="font-size:22px;font-weight:500;color:#FFFFFF;">
                &#8358;{price:,.2f}
              </div>
              {period_chg_html}
            </div>
            <div style="text-align:right;">
              {sparkline if sparkline else '<div style="font-size:11px;color:#374151;padding:10px;">No chart data yet</div>'}
            </div>
          </div>

          <!-- Stats row -->
          <div style="display:grid;grid-template-columns:repeat(3,1fr);
                      gap:10px;margin-bottom:12px;">
            <div style="background:#0A0A0A;border:1px solid #1F1F1F;
                        border-radius:6px;padding:8px 10px;">
              <div style="font-size:10px;color:#4B5563;text-transform:uppercase;
                          letter-spacing:0.07em;margin-bottom:3px;">Volume</div>
              <div style="font-size:13px;color:#FFFFFF;">{volume:,}</div>
              {vol_ratio_html}
            </div>
            <div style="background:#0A0A0A;border:1px solid #1F1F1F;
                        border-radius:6px;padding:8px 10px;">
              <div style="font-size:10px;color:#4B5563;text-transform:uppercase;
                          letter-spacing:0.07em;margin-bottom:3px;">30-Day Range</div>
              {range_html if range_html else '<div style="font-size:12px;color:#374151;">Insufficient data</div>'}
            </div>
            <div style="background:#0A0A0A;border:1px solid #1F1F1F;
                        border-radius:6px;padding:8px 10px;">
              <div style="font-size:10px;color:#4B5563;text-transform:uppercase;
                          letter-spacing:0.07em;margin-bottom:3px;">Data Points</div>
              <div style="font-size:13px;color:#FFFFFF;">{period_days} sessions</div>
            </div>
          </div>

          <!-- Analysis box -->
          <div style="background:{bg};border:1px solid {border};
                      border-left:3px solid {color};border-radius:8px;
                      padding:14px 16px;font-size:13px;color:#D0D0D0;
                      line-height:1.8;margin-bottom:8px;">
            {analysis}
          </div>

          <!-- Disclaimer -->
          <div style="font-size:10px;color:#374151;">
            &#9888;&#65039; Educational analysis only — not financial advice.
          </div>

        </body></html>
        """, height=card_h, scrolling=False)


def render():
    sb = get_supabase()

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
    .hot-header { font-family:'Syne',sans-serif; font-size:22px; font-weight:800; color:#FFFFFF; margin-bottom:4px; }
    .hot-sub { font-family:'DM Mono',monospace; font-size:11px; color:#A0A0A0; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:20px; }
    .hot-section { font-family:'DM Mono',monospace; font-size:11px; font-weight:600; color:#F0A500; text-transform:uppercase; letter-spacing:0.1em; margin:20px 0 10px 0; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="hot-header">🔥 What's Hot</div>
    <div class="hot-sub">Today's biggest movers on the Nigerian Exchange</div>
    """, unsafe_allow_html=True)

    # ── FETCH LATEST DATE ─────────────────────────────
    latest_res = sb.table("stock_prices")\
        .select("trading_date")\
        .order("trading_date", desc=True)\
        .limit(1).execute()
    latest_date = latest_res.data[0]["trading_date"] \
        if latest_res.data else str(date.today())

    # ── TODAY'S PRICES — all stocks ──────────────────
    prices_res = sb.table("stock_prices")\
        .select("symbol, price, change_percent, volume")\
        .eq("trading_date", latest_date)\
        .limit(500).execute()

    all_today = prices_res.data or []

    # Deduplicate
    seen = set()
    unique_today = []
    for p in all_today:
        if p["symbol"] not in seen:
            seen.add(p["symbol"])
            unique_today.append(p)

    # ── FETCH 30-DAY HISTORY ──────────────────────────
    since_30 = str(date.today() - timedelta(days=35))
    history_res = sb.table("stock_prices")\
        .select("symbol, price, volume, trading_date")\
        .gte("trading_date", since_30)\
        .order("trading_date", desc=False)\
        .limit(10000).execute()

    history_map: dict = {}
    for h in (history_res.data or []):
        sym = h["symbol"]
        if sym not in history_map:
            history_map[sym] = []
        history_map[sym].append(h)

    # Compute avg volume per symbol
    avg_vol_map: dict = {}
    for sym, hist in history_map.items():
        vols = [
            int(h.get("volume", 0) or 0)
            for h in hist if h.get("volume", 0)
        ]
        avg_vol_map[sym] = sum(vols) / len(vols) if vols else 0

    # ── SORT INTO GAINERS / LOSERS ────────────────────
    gainers = sorted(
        [p for p in unique_today if float(p.get("change_percent") or 0) > 0],
        key=lambda x: float(x.get("change_percent", 0) or 0),
        reverse=True
    )[:15]

    losers = sorted(
        [p for p in unique_today if float(p.get("change_percent") or 0) < 0],
        key=lambda x: float(x.get("change_percent", 0) or 0)
    )[:15]

    # ── GAINERS ───────────────────────────────────────
    st.markdown(
        f"<div class='hot-section'>"
        f"📈 Top Gainers Today — {len(gainers)} stocks</div>",
        unsafe_allow_html=True
    )
    if gainers:
        for s in gainers:
            render_stock_card(s, True, history_map, avg_vol_map)
    else:
        st.info("No gainers data available yet.")

    # ── LOSERS ────────────────────────────────────────
    st.markdown(
        f"<div class='hot-section'>"
        f"📉 Top Losers Today — {len(losers)} stocks</div>",
        unsafe_allow_html=True
    )
    if losers:
        for s in losers:
            render_stock_card(s, False, history_map, avg_vol_map)
    else:
        st.info("No losers data available yet.")
