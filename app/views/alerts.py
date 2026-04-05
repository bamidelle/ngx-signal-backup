import streamlit as st
from app.utils.supabase_client import get_supabase


def render():
    sb = get_supabase()
    profile = st.session_state.get("profile", {})
    plan = profile.get("plan", "free")
    user = st.session_state.get("user")

    st.markdown("""
    <div style="padding:10px 0 20px 0;">
      <h2 style="margin:0;font-size:22px;color:#1a1612;">⚡ My Price Alerts</h2>
      <p style="margin:4px 0 0 0;color:#6b6560;font-size:14px;">
        Get notified when a stock hits your target price
      </p>
    </div>
    """, unsafe_allow_html=True)

    if plan == "free":
        st.markdown("""
        <div style="background:#fffbeb;border:1px solid #fde68a;
                    border-radius:12px;padding:20px;text-align:center;">
          <div style="font-size:32px;margin-bottom:8px;">⚡</div>
          <div style="font-weight:700;font-size:16px;color:#1a1612;
                      margin-bottom:8px;">
            Price alerts on Starter plan
          </div>
          <div style="color:#6b6560;font-size:14px;">
            Upgrade to get notified on WhatsApp when
            any stock hits your target price.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Get latest prices
    stocks_res = sb.table("stock_prices")\
        .select("symbol, price")\
        .order("trading_date", desc=True)\
        .limit(200).execute()

    seen = set()
    stocks = []
    for s in (stocks_res.data or []):
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            stocks.append(s)

    symbols = [s["symbol"] for s in stocks]
    price_map = {s["symbol"]: s["price"] for s in stocks}

    st.markdown("### Set a New Alert")
    col1, col2, col3 = st.columns(3)
    with col1:
        alert_symbol = st.selectbox("Stock", symbols, key="alert_symbol")
    with col2:
        current = float(price_map.get(alert_symbol, 0))
        target = st.number_input(
            "Target price (₦)",
            min_value=0.01,
            value=current,
            format="%.2f",
            key="alert_price"
        )
    with col3:
        direction = st.selectbox(
            "Alert when",
            ["goes above ↑", "goes below ↓"],
            key="alert_dir"
        )

    if st.button("Set Alert ⚡", key="set_alert", type="primary"):
        try:
            sb.table("price_alerts").insert({
                "user_id": user.id,
                "symbol": alert_symbol,
                "target_price": target,
                "alert_type": "above" if "above" in direction else "below",
                "is_active": True,
            }).execute()
            st.success(
                f"✅ Alert set! You'll be notified when {alert_symbol} "
                f"{direction} ₦{target:,.2f}"
            )
        except Exception as e:
            st.error(f"Could not set alert: {e}")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown("### Your Active Alerts")

    alerts_res = sb.table("price_alerts")\
        .select("*")\
        .eq("user_id", user.id)\
        .eq("is_active", True)\
        .execute()

    if not (alerts_res.data or []):
        st.info("No active alerts. Set one above.")
        return

    for alert in alerts_res.data:
        current_p = float(price_map.get(alert["symbol"], 0))
        target_p = float(alert.get("target_price", 0))
        direction_label = "above ↑" if alert.get("alert_type") == "above" \
                          else "below ↓"
        diff = abs(current_p - target_p)

        st.markdown(f"""
        <div style="background:#fff;border:1px solid #e5e0da;
                    border-radius:10px;padding:14px 16px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;
                      align-items:center;">
            <div>
              <span style="font-weight:700;font-size:16px;color:#1a1612;">
                {alert['symbol']}
              </span>
              <span style="color:#6b6560;font-size:13px;margin-left:8px;">
                Alert when {direction_label} ₦{target_p:,.2f}
              </span>
            </div>
            <div style="text-align:right;">
              <div style="font-size:13px;color:#1a1612;font-weight:600;">
                Now: ₦{current_p:,.2f}
              </div>
              <div style="font-size:11px;color:#9a9088;">
                ₦{diff:,.2f} away
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
