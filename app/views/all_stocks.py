import streamlit as st
from datetime import date, timedelta
from app.utils.supabase_client import get_supabase

# ── Sector → color map ────────────────────────────────
SECTOR_COLORS = {
    "Banking":           "#3B82F6",
    "Finance":           "#3B82F6",
    "Telecoms":          "#8B5CF6",
    "ICT":               "#8B5CF6",
    "Consumer Goods":    "#F59E0B",
    "Cement":            "#6B7280",
    "Construction":      "#6B7280",
    "Oil & Gas":         "#EF4444",
    "Energy":            "#F97316",
    "Agriculture":       "#22C55E",
    "Healthcare":        "#06B6D4",
    "Insurance":         "#A78BFA",
    "Real Estate":       "#EC4899",
    "Technology":        "#10B981",
    "Transportation":    "#F59E0B",
    "Other":             "#6B7280",
}

# Company name → abbreviation for logo placeholder
def get_sector_color(sector: str) -> str:
    for k, v in SECTOR_COLORS.items():
        if k.lower() in (sector or "").lower():
            return v
    return "#6B7280"

def build_svg_chart(prices: list, color: str, width: int = 300, height: int = 80) -> str:
    """Build a responsive SVG price chart from price history."""
    if not prices or len(prices) < 2:
        return f"""<svg width="100%" height="{height}" viewBox="0 0 {width} {height}"
                    xmlns="http://www.w3.org/2000/svg">
          <text x="{width//2}" y="{height//2}" text-anchor="middle"
                fill="#374151" font-size="12" font-family="monospace">
            Insufficient data
          </text></svg>"""

    mn, mx = min(prices), max(prices)
    rng    = mx - mn if mx != mn else 1.0
    n      = len(prices)
    step   = width / (n - 1)

    pts = []
    for i, p in enumerate(prices):
        x = round(i * step, 1)
        y = round(height - ((p - mn) / rng) * (height - 10) - 5, 1)
        pts.append(f"{x},{y}")

    poly  = " ".join(pts)
    fill  = f"0,{height} " + poly + f" {width},{height}"
    cid   = color.replace("#", "c")

    # Y-axis labels
    top_price   = f"₦{mx:,.0f}"
    bot_price   = f"₦{mn:,.0f}"

    return f"""<svg width="100%" height="{height}" viewBox="0 0 {width} {height}"
               xmlns="http://www.w3.org/2000/svg" style="display:block;">
      <defs>
        <linearGradient id="{cid}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="{color}" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <!-- Grid lines -->
      <line x1="0" y1="{height//2}" x2="{width}" y2="{height//2}"
            stroke="#1E2229" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- Area fill -->
      <polygon points="{fill}" fill="url(#{cid})"/>
      <!-- Price line -->
      <polyline points="{poly}" fill="none" stroke="{color}"
                stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <!-- Price labels -->
      <text x="4" y="12" fill="#4B5563" font-size="9" font-family="monospace">{top_price}</text>
      <text x="4" y="{height-3}" fill="#4B5563" font-size="9" font-family="monospace">{bot_price}</text>
    </svg>"""


def render_stock_card(stock: dict, history_map: dict, avg_vol_map: dict, index: int):
    """Render a single stock card with interactive chart tabs."""
    symbol   = stock.get("symbol", "")
    price    = float(stock.get("price", 0) or 0)
    chg      = float(stock.get("change_percent", 0) or 0)
    volume   = int(stock.get("volume", 0) or 0)
    sector   = stock.get("sector", "Other") or "Other"
    company  = stock.get("company_name", symbol) or symbol

    color    = "#22C55E" if chg >= 0 else "#EF4444"
    arrow    = "▲" if chg >= 0 else "▼"
    sc_color = get_sector_color(sector)
    avg_vol  = avg_vol_map.get(symbol, 0)

    # 30-day history
    history_30  = history_map.get(symbol, [])
    prices_30   = [float(h["price"]) for h in history_30 if h.get("price")]

    # Subset slices
    def last_n(lst, n): return lst[-n:] if len(lst) >= n else lst
    p1w  = last_n(prices_30, 5)
    p1m  = last_n(prices_30, 22)
    p3m  = prices_30   # max 30 days is best we have
    fall = prices_30   # ALL = same as 30d for now

    period_chg = ""
    if prices_30 and len(prices_30) >= 2:
        pc = ((prices_30[-1] - prices_30[0]) / prices_30[0]) * 100
        period_chg = f"{pc:+.1f}% (30d)"

    # Layman analysis
    if not prices_30 or len(prices_30) < 2:
        analysis = (
            f"{symbol} is listed on the Nigerian Exchange. "
            f"Not enough historical data has been collected yet to show trend analysis. "
            f"Today it moved {chg:+.2f}%. Check back in a few trading sessions "
            f"as the data builds up."
        )
    else:
        mn30, mx30 = min(prices_30), max(prices_30)
        near_hi    = price >= mx30 * 0.97
        near_lo    = price <= mn30 * 1.03
        ma5        = sum(prices_30[-5:]) / min(5, len(prices_30))
        trend      = "upward" if price > ma5 * 1.002 else "downward" if price < ma5 * 0.998 else "flat"
        vol_note   = ""
        if avg_vol > 0 and volume > 0:
            r = volume / avg_vol
            if r > 1.5: vol_note = f" Volume today is {r:.1f}× the 30-day average — strong conviction."
            elif r < 0.5: vol_note = " Volume is low — today's move may lack follow-through."

        if chg > 0:
            analysis = f"{symbol} gained {chg:+.2f}% to ₦{price:,.2f} today.{vol_note}"
            if near_hi: analysis += f" It's near its 30-day high of ₦{mx30:,.2f} — bullish momentum."
            if trend == "upward": analysis += " The short-term trend is upward."
        else:
            analysis = f"{symbol} fell {abs(chg):.2f}% to ₦{price:,.2f} today.{vol_note}"
            if near_lo: analysis += f" It's near its 30-day low of ₦{mn30:,.2f} — watch support."
            if trend == "downward": analysis += " The short-term trend is downward."
        analysis += f" 30-day range: ₦{mn30:,.2f}–₦{mx30:,.2f}."

    initials = "".join(w[0] for w in company.split()[:2]).upper()[:2]

    with st.expander(
        f"{arrow}  {symbol}  ·  ₦{price:,.2f}  ·  {chg:+.2f}%  ·  {company[:30]}",
        expanded=False
    ):
        # ── TradingView symbol: Nigerian Exchange uses "NSENG:SYMBOL" on TradingView ──
        # NSE: = National Stock Exchange of India (wrong)
        # NSENG: = Nigerian Exchange Group (correct)
        tv_symbol = f"NSENG:{symbol}"

        # ── Header card with price info ────────────────
        vol_vs_avg = f"{volume/avg_vol:.1f}×" if avg_vol > 0 and volume > 0 else "N/A"
        st.components.v1.html(f"""
<!DOCTYPE html><html>
<head>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:transparent;font-family:'DM Mono',monospace;color:#fff;overflow:hidden;}}
.hdr{{display:flex;align-items:flex-start;gap:12px;padding:12px 0 10px;}}
.logo{{width:44px;height:44px;border-radius:10px;background:{sc_color};display:flex;align-items:center;
       justify-content:center;font-size:15px;font-weight:700;color:#fff;
       font-family:'Space Grotesk',sans-serif;flex-shrink:0;}}
.co{{flex:1;min-width:0;}}
.co-name{{font-size:15px;font-weight:700;color:#fff;margin-bottom:2px;
          font-family:'Space Grotesk',sans-serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.co-sub{{font-size:11px;color:#808080;}}
.tag{{display:inline-block;background:{sc_color}22;color:{sc_color};font-size:9px;
      padding:2px 7px;border-radius:10px;margin-top:3px;}}
.pb{{text-align:right;flex-shrink:0;}}
.pm{{font-size:24px;font-weight:500;color:#fff;font-family:'DM Mono',monospace;}}
.pc{{font-size:13px;font-weight:600;color:{color};}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:10px;}}
.st{{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:6px;padding:7px 9px;}}
.sl{{font-size:9px;color:#808080;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px;}}
.sv{{font-size:12px;color:#fff;font-weight:500;}}
</style>
</head>
<body>
<div class="hdr">
  <div class="logo">{initials}</div>
  <div class="co">
    <div class="co-name">{company}</div>
    <div class="co-sub">NGX: {symbol}</div>
    <div class="tag">{sector}</div>
  </div>
  <div class="pb">
    <div class="pm">&#8358;{price:,.2f}</div>
    <div class="pc">{arrow} {abs(chg):.2f}%</div>
    {'<div style="font-size:10px;color:#808080;margin-top:2px;">' + period_chg + '</div>' if period_chg else ''}
  </div>
</div>
<div class="stats">
  <div class="st"><div class="sl">Volume</div><div class="sv">{volume:,}</div></div>
  <div class="st"><div class="sl">Vs Avg</div><div class="sv">{vol_vs_avg}</div></div>
  <div class="st"><div class="sl">30d Hi</div><div class="sv">{"&#8358;"+f"{max(prices_30):,.2f}" if prices_30 else "N/A"}</div></div>
  <div class="st"><div class="sl">30d Lo</div><div class="sv">{"&#8358;"+f"{min(prices_30):,.2f}" if prices_30 else "N/A"}</div></div>
</div>
</body></html>
""", height=145, scrolling=False)

        # ── TradingView Advanced Chart Widget ─────────────────────────────
        # style:"3" = Area chart (line + fill) — matches image 1
        # style:"1" = Candlestick (avoid — that's image 2, wrong)
        # interval:"D" = Daily bars — most current data for NGX
        # range:"3M"  = Show 3 months of data so chart isn't stale-looking
        # hide_top_toolbar:false lets user switch timeframe manually
        # Script loaded synchronously (not async) for faster first paint
        # Loading overlay hides the blank iframe flash on slow connections

        tv_html = f"""<!DOCTYPE html><html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{height:100%;background:#000;overflow:hidden;}}
.tv-outer{{
  position:relative;height:420px;
  background:#000;border:1px solid #1F1F1F;border-radius:10px;overflow:hidden;
}}
/* Loading shimmer shown until TradingView widget fires */
.tv-loader{{
  position:absolute;inset:0;z-index:10;
  background:#000;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:10px;
  font-family:'DM Mono',monospace;font-size:11px;color:#4B5563;
  transition:opacity .4s ease;
}}
.tv-loader-bar{{
  width:120px;height:3px;background:#1F1F1F;border-radius:2px;overflow:hidden;
}}
.tv-loader-fill{{
  height:100%;width:0%;background:#F0A500;border-radius:2px;
  animation:tv-load 2.5s ease-in-out infinite;
}}
@keyframes tv-load{{0%{{width:0%}}60%{{width:85%}}100%{{width:100%}}}}
.tradingview-widget-container{{height:100%;width:100%;}}
.tradingview-widget-container__widget{{height:calc(100% - 32px);width:100%;}}
.tradingview-widget-copyright{{font-size:10px;}}
</style>
</head>
<body>
<div class="tv-outer" id="tvOuter">
  <!-- Loading overlay — hidden once widget fires -->
  <div class="tv-loader" id="tvLoader">
    <div style="font-size:13px;color:#808080;">📈 Loading chart…</div>
    <div class="tv-loader-bar"><div class="tv-loader-fill"></div></div>
    <div style="font-size:10px;color:#374151;">NSENG:{symbol}</div>
  </div>

  <!-- TradingView Advanced Chart -->
  <div class="tradingview-widget-container" id="tvContainer">
    <div class="tradingview-widget-container__widget"></div>
    <div class="tradingview-widget-copyright">
      <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">
        <span class="blue-text" style="font-size:10px;color:#374151;">TradingView</span>
      </a>
    </div>
  </div>
</div>

<script>
// Hide loader once TradingView widget has painted
function hideLoader() {{
  var el = document.getElementById('tvLoader');
  if (el) {{ el.style.opacity = '0'; setTimeout(function(){{el.style.display='none';}}, 450); }}
}}

// Widget config — style 3 = Area chart (line + fill under it)
var tvConfig = {{
  "autosize": true,
  "symbol": "NSENG:{symbol}",
  "interval": "D",
  "range": "3M",
  "timezone": "Africa/Lagos",
  "theme": "dark",
  "style": "3",
  "locale": "en",
  "backgroundColor": "#000000",
  "gridColor": "rgba(17,17,17,0.9)",
  "hide_top_toolbar": false,
  "hide_legend": false,
  "save_image": false,
  "hide_volume": false,
  "support_host": "https://www.tradingview.com",
  "overrides": {{
    "paneProperties.background": "#000000",
    "paneProperties.backgroundType": "solid",
    "paneProperties.vertGridProperties.color": "#111111",
    "paneProperties.horzGridProperties.color": "#111111",
    "scalesProperties.textColor": "#808080",
    "mainSeriesProperties.areaStyle.color1": "{color}",
    "mainSeriesProperties.areaStyle.color2": "rgba(0,0,0,0)",
    "mainSeriesProperties.areaStyle.linecolor": "{color}",
    "mainSeriesProperties.areaStyle.linewidth": 2,
    "mainSeriesProperties.areaStyle.priceSource": "close",
    "mainSeriesProperties.lineStyle.color": "{color}",
    "mainSeriesProperties.lineStyle.linewidth": 2
  }}
}};

// Load the script — synchronous so no async blank-page flash
(function() {{
  var s = document.createElement('script');
  s.type = 'text/javascript';
  s.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  s.onload = function() {{ setTimeout(hideLoader, 1800); }};
  // Also hide loader on MutationObserver — catches widget render
  var observer = new MutationObserver(function(muts) {{
    for (var m of muts) {{
      if (m.addedNodes.length) {{ setTimeout(hideLoader, 600); observer.disconnect(); break; }}
    }}
  }});
  observer.observe(document.querySelector('.tradingview-widget-container__widget'), {{childList: true, subtree: true}});
  // Inject config as the script's text content
  s.text = JSON.stringify(tvConfig);
  document.querySelector('.tradingview-widget-container').appendChild(s);
}})();

// Resize iframe to content
function resize() {{
  var h = document.body.scrollHeight + 16;
  window.parent.postMessage({{type:'streamlit:setFrameHeight', height: 440}}, '*');
}}
window.addEventListener('load', resize);
</script>
</body></html>"""

        st.components.v1.html(tv_html, height=440, scrolling=False)

        # ── Analysis text ──────────────────────────────
        st.components.v1.html(f"""
<!DOCTYPE html><html>
<head>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:transparent;overflow:hidden;}}
.box{{background:#000;border:1px solid #1F1F1F;border-left:3px solid {color};
      border-radius:8px;padding:12px 14px;font-family:'DM Mono',monospace;
      font-size:12px;color:#D0D0D0;line-height:1.75;margin-top:8px;}}
.box strong{{color:#fff;}}
.disc{{font-size:10px;color:#505050;margin-top:8px;padding-top:6px;border-top:1px solid #111;}}
</style></head>
<body>
<div class="box">
  <strong>What happened:</strong><br>
  {analysis}
</div>
<div class="disc">&#9888;&#65039; Educational analysis only — not financial advice. Chart data from TradingView.</div>
</body></html>
""", height=130, scrolling=False)


def render():
    sb = get_supabase()

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
    .al-title { font-family:'Syne',sans-serif; font-size:22px; font-weight:800; color:#FFFFFF; margin-bottom:4px; }
    .al-sub { font-family:'DM Mono',monospace; font-size:11px; color:#A0A0A0; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:20px; }
    .al-stat { font-family:'DM Mono',monospace; font-size:12px; color:#6B7280; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="al-title">📊 All Live NGX Stocks</div>
    <div class="al-sub">Real-time prices · 140–150 listed equities · Click any stock to expand</div>
    """, unsafe_allow_html=True)

    # ── FETCH ALL LATEST PRICES ───────────────────────
    date_res = sb.table("stock_prices").select("trading_date")\
        .order("trading_date", desc=True).limit(1).execute()
    latest_date = date_res.data[0]["trading_date"] \
        if date_res.data else str(date.today())

    prices_res = sb.table("stock_prices")\
        .select("symbol, price, change_percent, volume")\
        .eq("trading_date", latest_date).limit(500).execute()
    today_prices = prices_res.data or []

    # If sparse, pull all latest per symbol
    if len(today_prices) < 50:
        broad = sb.table("stock_prices")\
            .select("symbol, price, change_percent, volume, trading_date")\
            .order("trading_date", desc=True).limit(5000).execute()
        sym_map = {}
        for p in (broad.data or []):
            s = p.get("symbol", "")
            if s and s not in sym_map: sym_map[s] = p
        existing = {p["symbol"] for p in today_prices}
        today_prices += [p for s, p in sym_map.items() if s not in existing]

    # Get company names + sectors from stocks table
    stocks_meta_res = sb.table("stocks")\
        .select("symbol, company_name, sector").limit(500).execute()
    meta_map = {
        s["symbol"]: s for s in (stocks_meta_res.data or [])
    }

    # Merge meta into prices
    all_stocks = []
    seen = set()
    for p in today_prices:
        sym = p.get("symbol", "")
        if not sym or sym in seen: continue
        seen.add(sym)
        meta = meta_map.get(sym, {})
        all_stocks.append({
            "symbol":       sym,
            "price":        float(p.get("price", 0) or 0),
            "change_percent": float(p.get("change_percent", 0) or 0),
            "volume":       int(p.get("volume", 0) or 0),
            "company_name": meta.get("company_name", sym),
            "sector":       meta.get("sector", "Other"),
        })

    # ── FETCH 30-DAY HISTORY ──────────────────────────
    since = str(date.today() - timedelta(days=35))
    hist_res = sb.table("stock_prices")\
        .select("symbol, price, volume, trading_date")\
        .gte("trading_date", since)\
        .order("trading_date", desc=False)\
        .limit(10000).execute()

    history_map = {}
    for h in (hist_res.data or []):
        sym = h["symbol"]
        if sym not in history_map: history_map[sym] = []
        history_map[sym].append(h)

    avg_vol_map = {}
    for sym, hist in history_map.items():
        vols = [int(h.get("volume", 0) or 0) for h in hist if h.get("volume")]
        avg_vol_map[sym] = sum(vols) / len(vols) if vols else 0

    total = len(all_stocks)
    gainers = sum(1 for s in all_stocks if s["change_percent"] > 0)
    losers  = sum(1 for s in all_stocks if s["change_percent"] < 0)

    # ── SUMMARY ROW ──────────────────────────────────
    st.components.v1.html(f"""
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;font-family:DM Mono,monospace;">
      <div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:500;color:#F0A500;">{total}</div>
        <div style="font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-top:4px;">Stocks Tracked</div>
      </div>
      <div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:500;color:#22C55E;">{gainers}</div>
        <div style="font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-top:4px;">Gainers Today</div>
      </div>
      <div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:26px;font-weight:500;color:#EF4444;">{losers}</div>
        <div style="font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-top:4px;">Losers Today</div>
      </div>
    </div>
    """, height=90, scrolling=False)

    # ── SEARCH + FILTER ───────────────────────────────
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        search = st.text_input(
            "🔍 Search stocks",
            placeholder="Symbol or company name...",
            key="al_search",
            label_visibility="collapsed"
        ).upper().strip()
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Best gainers", "Biggest losers", "Highest volume", "Symbol A–Z"],
            key="al_sort",
            label_visibility="collapsed"
        )
    with col3:
        sector_opts = ["All sectors"] + sorted({
            s["sector"] for s in all_stocks if s.get("sector") and s["sector"] != "Other"
        })
        sector_filter = st.selectbox(
            "Sector",
            sector_opts,
            key="al_sector",
            label_visibility="collapsed"
        )

    # ── APPLY FILTERS ─────────────────────────────────
    filtered = all_stocks[:]

    if search:
        filtered = [
            s for s in filtered
            if search in s["symbol"] or
            search in (s.get("company_name") or "").upper()
        ]

    if sector_filter != "All sectors":
        filtered = [s for s in filtered if s.get("sector") == sector_filter]

    if sort_by == "Best gainers":
        filtered = sorted(filtered, key=lambda x: x["change_percent"], reverse=True)
    elif sort_by == "Biggest losers":
        filtered = sorted(filtered, key=lambda x: x["change_percent"])
    elif sort_by == "Highest volume":
        filtered = sorted(filtered, key=lambda x: x["volume"], reverse=True)
    elif sort_by == "Symbol A–Z":
        filtered = sorted(filtered, key=lambda x: x["symbol"])

    # ── PAGINATION ────────────────────────────────────
    PAGE_SIZE = 20
    total_filtered = len(filtered)
    total_pages    = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)

    if "al_page" not in st.session_state:
        st.session_state.al_page = 1

    # Reset page on search/filter change
    filter_key = f"{search}_{sort_by}_{sector_filter}"
    if st.session_state.get("al_filter_key") != filter_key:
        st.session_state.al_filter_key = filter_key
        st.session_state.al_page = 1

    page = st.session_state.al_page
    start = (page - 1) * PAGE_SIZE
    end   = start + PAGE_SIZE
    page_stocks = filtered[start:end]

    st.markdown(
        f"<div class='al-stat' style='margin-bottom:12px;'>"
        f"Showing <strong style='color:#F0A500;'>{len(page_stocks)}</strong> of "
        f"<strong style='color:#FFFFFF;'>{total_filtered}</strong> stocks "
        f"· Page <strong style='color:#F0A500;'>{page}</strong> of {total_pages}"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── STOCK CARDS ───────────────────────────────────
    for i, stock in enumerate(page_stocks):
        render_stock_card(stock, history_map, avg_vol_map, start + i)

    # ── PAGINATION CONTROLS ───────────────────────────
    if total_pages > 1:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        pg_cols = st.columns([1, 2, 1])

        with pg_cols[0]:
            if page > 1:
                if st.button("← Previous", key="al_prev", use_container_width=True):
                    st.session_state.al_page -= 1
                    st.rerun()

        with pg_cols[1]:
            # Page number buttons (show up to 7)
            num_cols = st.columns(min(7, total_pages))
            start_p  = max(1, page - 3)
            end_p    = min(total_pages + 1, start_p + 7)
            for pi, pnum in enumerate(range(start_p, end_p)):
                with num_cols[pi]:
                    if st.button(
                        str(pnum),
                        key=f"al_pg_{pnum}",
                        type="primary" if pnum == page else "secondary",
                        use_container_width=True
                    ):
                        st.session_state.al_page = pnum
                        st.rerun()

        with pg_cols[2]:
            if page < total_pages:
                if st.button("Next →", key="al_next", type="primary", use_container_width=True):
                    st.session_state.al_page += 1
                    st.rerun()

    st.markdown("""
    <div style="font-family:DM Mono,monospace;font-size:10px;color:#374151;
                margin-top:20px;padding-top:12px;border-top:1px solid #1E2229;
                text-align:center;">
      Data sourced from NGX Pulse, TradingView Screener and AFX Kwayisi.
      Prices are delayed. For educational purposes only.
    </div>
    """, unsafe_allow_html=True)