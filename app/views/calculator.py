import streamlit as st
from datetime import date
from app.utils.supabase_client import get_supabase


def render():
    sb = get_supabase()

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap');

    .calc-hero {
        background: linear-gradient(135deg, #0A0C0F 0%, #10131A 50%, #1A1600 100%);
        border: 1px solid #2A2200;
        border-radius: 16px;
        padding: 32px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
    }
    .calc-hero::before {
        content: '₦';
        position: absolute;
        right: -20px;
        top: -30px;
        font-size: 180px;
        color: #F0A500;
        opacity: 0.04;
        font-family: 'Syne', sans-serif;
        font-weight: 800;
    }
    .calc-title {
        font-family: 'Syne', sans-serif;
        font-size: 28px;
        font-weight: 800;
        color: #F0A500;
        margin: 0 0 8px 0;
        letter-spacing: -0.5px;
    }
    .calc-subtitle {
        font-family: 'DM Mono', monospace;
        font-size: 13px;
        color: #6B7280;
        margin: 0;
        letter-spacing: 0.05em;
    }
    .calc-result {
        background: #10131A;
        border: 1px solid #2A2200;
        border-left: 4px solid #F0A500;
        border-radius: 12px;
        padding: 24px;
        margin-top: 20px;
        font-family: 'DM Mono', monospace;
    }
    .calc-result-main {
        font-size: 42px;
        font-weight: 500;
        letter-spacing: -1px;
        margin-bottom: 4px;
    }
    .calc-result-label {
        font-size: 11px;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 20px;
    }
    .calc-stat-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #1E2229;
        font-size: 13px;
    }
    .calc-stat-row:last-child { border-bottom: none; }
    .calc-stat-key { color: #6B7280; }
    .calc-stat-val { color: #E8E2D4; font-weight: 500; }
    .calc-stat-val.up { color: #22C55E; }
    .calc-stat-val.down { color: #EF4444; }
    .share-banner {
        background: linear-gradient(135deg, #1A1600, #2A2200);
        border: 1px solid #3D3200;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin-top: 16px;
        font-family: 'DM Mono', monospace;
    }
    .share-text {
        font-size: 18px;
        font-weight: 500;
        color: #F0A500;
        margin-bottom: 6px;
    }
    .share-sub {
        font-size: 12px;
        color: #6B7280;
    }
    .stock-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 8px;
        margin: 16px 0;
    }
    .stock-chip {
        background: #10131A;
        border: 1px solid #1E2229;
        border-radius: 8px;
        padding: 10px 12px;
        font-family: 'DM Mono', monospace;
        font-size: 12px;
        color: #E8E2D4;
        cursor: pointer;
        transition: all 0.15s;
    }
    .stock-chip:hover {
        border-color: #F0A500;
        color: #F0A500;
    }
    .stock-chip .chip-symbol { font-weight: 500; font-size: 13px; }
    .stock-chip .chip-price { color: #6B7280; font-size: 11px; margin-top: 2px; }
    </style>
    """, unsafe_allow_html=True)

    # ── HERO ─────────────────────────────────────────
    st.markdown("""
    <div class="calc-hero">
      <div class="calc-title">₦100k Calculator</div>
      <div class="calc-subtitle">
        WHAT WOULD YOUR INVESTMENT BE WORTH TODAY?
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── GET STOCK DATA ────────────────────────────────
    prices_res = sb.table("stock_prices")\
        .select("symbol, price, change_percent")\
        .order("trading_date", desc=True)\
        .limit(200).execute()

    seen = set()
    stocks = []
    for p in (prices_res.data or []):
        if p["symbol"] not in seen:
            seen.add(p["symbol"])
            stocks.append(p)

    if not stocks:
        st.info("No stock data available. Run the scraper first.")
        return

    price_map = {s["symbol"]: float(s["price"]) for s in stocks}
    symbols = sorted(price_map.keys())

    # ── INPUTS ───────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        selected = st.selectbox(
            "🏢 Choose stock",
            symbols,
            key="calc_symbol"
        )
    with col2:
        investment = st.number_input(
            "💰 Your investment (₦)",
            min_value=1000,
            value=100000,
            step=10000,
            key="calc_amount"
        )
    with col3:
        buy_price = st.number_input(
            "📅 Price you bought at (₦)",
            min_value=0.01,
            value=float(price_map.get(selected, 100)),
            format="%.2f",
            key="calc_buy_price"
        )

    current_price = price_map.get(selected, buy_price)
    shares = investment / buy_price if buy_price > 0 else 0
    current_value = shares * current_price
    profit_loss = current_value - investment
    pct_change = ((current_value - investment) / investment * 100) \
        if investment > 0 else 0

    is_profit = profit_loss >= 0
    val_color = "#22C55E" if is_profit else "#EF4444"
    val_class = "up" if is_profit else "down"
    arrow = "▲" if is_profit else "▼"
    label = "PROFIT" if is_profit else "LOSS"

    # ── LIVE RESULT ───────────────────────────────────
    st.markdown(f"""
    <div class="calc-result">
      <div class="calc-result-label">Current value of your investment</div>
      <div class="calc-result-main" style="color:{val_color};">
        ₦{current_value:,.2f}
      </div>
      <div style="font-family:'DM Mono',monospace;font-size:14px;
                  color:{val_color};margin-bottom:20px;">
        {arrow} {label}: ₦{abs(profit_loss):,.2f}
        ({pct_change:+.2f}%)
      </div>
      <div class="calc-stat-row">
        <span class="calc-stat-key">Stock</span>
        <span class="calc-stat-val">{selected}</span>
      </div>
      <div class="calc-stat-row">
        <span class="calc-stat-key">Shares owned</span>
        <span class="calc-stat-val">{shares:,.4f}</span>
      </div>
      <div class="calc-stat-row">
        <span class="calc-stat-key">Bought at</span>
        <span class="calc-stat-val">₦{buy_price:,.2f}</span>
      </div>
      <div class="calc-stat-row">
        <span class="calc-stat-key">Current price</span>
        <span class="calc-stat-val">₦{current_price:,.2f}</span>
      </div>
      <div class="calc-stat-row">
        <span class="calc-stat-key">Amount invested</span>
        <span class="calc-stat-val">₦{investment:,.2f}</span>
      </div>
      <div class="calc-stat-row">
        <span class="calc-stat-key">Current value</span>
        <span class="calc-stat-val {val_class}">₦{current_value:,.2f}</span>
      </div>
      <div class="calc-stat-row">
        <span class="calc-stat-key">Return</span>
        <span class="calc-stat-val {val_class}">
          {arrow} {abs(pct_change):.2f}%
        </span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── SHAREABLE BANNER ──────────────────────────────
    if is_profit:
        st.markdown(f"""
        <div class="share-banner">
          <div class="share-text">
            📱 Share your win!
          </div>
          <div style="font-size:16px;color:#E8E2D4;margin:8px 0;">
            "I invested ₦{investment:,.0f} in {selected} and
            it's now worth ₦{current_value:,.0f}
            (+{pct_change:.1f}%) 🚀
            Calculated on NGX Signal"
          </div>
          <div class="share-sub">
            Copy and share on WhatsApp, Twitter or Telegram
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── ALL STOCKS QUICK VIEW ─────────────────────────
    st.markdown("""
    <div style="font-family:'Syne',sans-serif;font-size:14px;
                font-weight:700;color:#F0A500;
                text-transform:uppercase;letter-spacing:0.1em;
                margin-bottom:12px;">
      📊 Quick Calculate — All Stocks
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        "<div style='font-family:DM Mono,monospace;font-size:12px;"
        "color:#6B7280;margin-bottom:12px;'>"
        f"If you invested ₦{investment:,.0f} in each stock at today's price:</div>",
        unsafe_allow_html=True
    )

    # Show all stocks as a grid
    cols = st.columns(4)
    for i, stock in enumerate(stocks[:24]):
        sym = stock["symbol"]
        price = float(stock["price"])
        chg = float(stock.get("change_percent", 0) or 0)
        hypothetical_shares = investment / price if price > 0 else 0
        hypothetical_value = hypothetical_shares * price
        color = "#22C55E" if chg >= 0 else "#EF4444"
        arrow_s = "▲" if chg >= 0 else "▼"

        with cols[i % 4]:
            st.markdown(f"""
            <div class="stock-chip">
              <div class="chip-symbol">{sym}</div>
              <div class="chip-price">₦{price:,.2f}</div>
              <div style="color:{color};font-size:11px;margin-top:2px;">
                {arrow_s} {abs(chg):.2f}%
              </div>
            </div>
            """, unsafe_allow_html=True)
