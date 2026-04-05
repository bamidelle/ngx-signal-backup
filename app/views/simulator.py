import streamlit as st
from app.utils.supabase_client import get_supabase


def render():
    sb = get_supabase()
    profile = st.session_state.get("profile", {})
    plan = profile.get("plan", "free")

    st.markdown("""
    <div style="padding:10px 0 20px 0;">
      <h2 style="margin:0;font-size:22px;color:#1a1612;">
        💰 Investment Simulator
      </h2>
      <p style="margin:4px 0 0 0;color:#6b6560;font-size:14px;">
        See what your investment would be worth today
      </p>
    </div>
    """, unsafe_allow_html=True)

    if plan == "free":
        st.markdown("""
        <div style="background:#fffbeb;border:1px solid #fde68a;
                    border-radius:12px;padding:20px;text-align:center;">
          <div style="font-size:32px;margin-bottom:8px;">💰</div>
          <div style="font-weight:700;font-size:16px;color:#1a1612;
                      margin-bottom:8px;">
            Simulator on Starter plan
          </div>
          <div style="color:#6b6560;font-size:14px;">
            Upgrade to Starter to use the investment simulator
            and see what your money would be worth today.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    stocks_res = sb.table("stock_prices")\
        .select("symbol, price")\
        .order("trading_date", desc=True)\
        .order("symbol")\
        .limit(200).execute()

    seen = set()
    stocks = []
    for s in (stocks_res.data or []):
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            stocks.append(s)

    if not stocks:
        st.info("No stock data available yet.")
        return

    symbols = [s["symbol"] for s in stocks]
    price_map = {s["symbol"]: s["price"] for s in stocks}

    col1, col2 = st.columns(2)
    with col1:
        selected = st.selectbox("Choose a stock", symbols, key="sim_stock")
    with col2:
        amount = st.number_input(
            "Amount invested (₦)",
            min_value=1000, value=100000,
            step=5000, key="sim_amount"
        )

    current_p = float(price_map.get(selected, 100))
    buy_price = st.number_input(
        "Price you bought at (₦)",
        min_value=0.01,
        value=current_p,
        format="%.2f",
        key="sim_buy_price"
    )

    if st.button("Calculate →", key="sim_calc", type="primary"):
        shares = amount / buy_price
        current_value = shares * current_p
        profit_loss = current_value - amount
        pct_change = ((current_value - amount) / amount) * 100
        is_profit = profit_loss >= 0
        color = "#16a34a" if is_profit else "#dc2626"
        emoji = "📈" if is_profit else "📉"
        label = "Profit" if is_profit else "Loss"

        st.markdown(f"""
        <div style="background:#fff;border:2px solid {color};
                    border-radius:16px;padding:28px;text-align:center;
                    margin-top:16px;">
          <div style="font-size:40px;margin-bottom:8px;">{emoji}</div>
          <div style="font-size:14px;color:#6b6560;margin-bottom:6px;">
            If you invested ₦{amount:,.0f} in {selected}
          </div>
          <div style="font-size:32px;font-weight:700;color:{color};">
            ₦{current_value:,.0f}
          </div>
          <div style="font-size:16px;color:{color};font-weight:600;
                      margin-top:8px;">
            {label}: ₦{abs(profit_loss):,.0f}
            ({pct_change:+.2f}%)
          </div>
          <div style="font-size:13px;color:#9a9088;margin-top:12px;">
            {shares:,.4f} shares × ₦{current_p:,.2f} current price
          </div>
        </div>
        """, unsafe_allow_html=True)
