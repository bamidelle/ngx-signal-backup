import streamlit as st
from app.utils.supabase_client import get_supabase

STARTING_BALANCE = 1_000_000

def render():
    sb   = get_supabase()
    user = st.session_state.get("user")
    if not user:
        st.warning("Please log in to access the Trade Game."); return

    uid  = user.id
    profile = st.session_state.get("profile", {})
    plan = profile.get("plan","free")
    PLAN_BALANCE = {"free":500_000,"starter":1_000_000,"trader":5_000_000,"pro":10_000_000}
    balance_cap  = PLAN_BALANCE.get(plan, 500_000)

    st.markdown(f"""
    <div style='font-family:Space Grotesk,sans-serif;font-size:22px;font-weight:800;
                color:#FFFFFF;margin-bottom:4px;'>🎮 NGX Trade Game</div>
    <div style='font-family:DM Mono,monospace;font-size:11px;color:#808080;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:20px;'>
        Paper trading · Virtual ₦{balance_cap:,} · No real money
    </div>""", unsafe_allow_html=True)

    try:
        pg_res = sb.table("paper_portfolios").select("*").eq("user_id", uid).limit(1).execute()
        port   = pg_res.data[0] if pg_res.data else None
    except Exception:
        port = None

    if not port:
        st.markdown(f"""
        <div style='background:#0A0A0A;border:1px solid rgba(240,165,0,0.3);border-radius:12px;
                    padding:24px;text-align:center;'>
          <div style='font-size:40px;margin-bottom:12px;'>🎮</div>
          <div style='font-family:Space Grotesk,sans-serif;font-size:18px;font-weight:700;
                      color:#FFFFFF;margin-bottom:8px;'>Start Your Virtual Portfolio</div>
          <div style='font-family:DM Mono,monospace;font-size:13px;color:#E0E0E0;line-height:1.7;
                      margin-bottom:16px;'>
            Practice trading NGX stocks with ₦{balance_cap:,} virtual naira.
            No real money — just skill building.
          </div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("🚀 Start Trading with Virtual ₦" + f"{balance_cap:,}", type="primary", use_container_width=True, key="game_start"):
            try:
                sb.table("paper_portfolios").insert({
                    "user_id": uid, "cash_balance": balance_cap,
                    "total_value": balance_cap, "plan": plan
                }).execute()
                st.success("Portfolio created! Reload to start trading."); st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        return

    cash    = float(port.get("cash_balance", balance_cap) or balance_cap)
    total   = float(port.get("total_value", cash) or cash)
    pnl     = total - balance_cap
    pnl_pct = (pnl / balance_cap * 100) if balance_cap else 0

    c1,c2,c3 = st.columns(3)
    for col, label, val, color in [
        (c1,"Cash Balance",f"₦{cash:,.0f}","#F0A500"),
        (c2,"Portfolio Value",f"₦{total:,.0f}","#FFFFFF"),
        (c3,"P&L",f"{'+'if pnl>=0 else ''}₦{pnl:,.0f} ({pnl_pct:+.1f}%)",
         "#22C55E" if pnl>=0 else "#EF4444"),
    ]:
        with col:
            st.markdown(f"""
            <div style='background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;
                        padding:14px;text-align:center;margin-bottom:12px;'>
              <div style='font-size:10px;color:#808080;text-transform:uppercase;
                          letter-spacing:.08em;margin-bottom:6px;'>{label}</div>
              <div style='font-family:DM Mono,monospace;font-size:20px;font-weight:500;
                          color:{color};'>{val}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Buy form
    with st.expander("📈 Buy a Stock", expanded=False):
        try:
            pr_res = sb.table("stock_prices").select("symbol,price").order("trading_date",desc=True).limit(300).execute()
            prices_raw = pr_res.data or []
            seen=set(); sym_prices={}
            for p in prices_raw:
                s=p.get("symbol","")
                if s and s not in seen:
                    seen.add(s); sym_prices[s]=float(p.get("price",0) or 0)
            syms = sorted(sym_prices.keys())
        except Exception:
            syms=[]; sym_prices={}

        if syms:
            col_a,col_b = st.columns(2)
            with col_a: sel_sym = st.selectbox("Stock", syms, key="game_buy_sym")
            with col_b: qty = st.number_input("Quantity (shares)", min_value=1, step=1, value=100, key="game_buy_qty")
            cur_price = sym_prices.get(sel_sym, 0)
            cost = cur_price * qty
            st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#FFFFFF;'>"
                        f"Price: ₦{cur_price:,.2f} · Total cost: <strong style='color:#F0A500;'>₦{cost:,.2f}</strong></div>",
                        unsafe_allow_html=True)
            if st.button(f"Buy {qty} × {sel_sym}", type="primary", key="game_buy_btn"):
                if cost > cash:
                    st.error(f"Insufficient cash. Need ₦{cost:,.0f}, have ₦{cash:,.0f}")
                elif cur_price <= 0:
                    st.error("No price data for this stock today")
                else:
                    try:
                        # Check existing holding
                        hold_res = sb.table("paper_holdings").select("*")\
                            .eq("user_id",uid).eq("symbol",sel_sym).limit(1).execute()
                        if hold_res.data:
                            h=hold_res.data[0]
                            old_qty=int(h.get("quantity",0)); old_avg=float(h.get("avg_price",0) or cur_price)
                            new_qty=old_qty+qty; new_avg=(old_avg*old_qty+cur_price*qty)/new_qty
                            sb.table("paper_holdings").update({"quantity":new_qty,"avg_price":new_avg,"current_price":cur_price})\
                              .eq("id",h["id"]).execute()
                        else:
                            sb.table("paper_holdings").insert({"user_id":uid,"symbol":sel_sym,"quantity":qty,
                                "avg_price":cur_price,"current_price":cur_price}).execute()
                        new_cash = cash - cost
                        sb.table("paper_portfolios").update({"cash_balance":new_cash})\
                          .eq("user_id",uid).execute()
                        st.success(f"✅ Bought {qty} shares of {sel_sym} @ ₦{cur_price:,.2f}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Trade error: {e}")
        else:
            st.info("No price data available. Run the scraper first.")

    # Holdings
    st.markdown("**Current Holdings**")
    try:
        hold_res = sb.table("paper_holdings").select("*").eq("user_id",uid).execute()
        holdings = hold_res.data or []
    except Exception:
        holdings=[]

    if holdings:
        for h in holdings:
            sym=h.get("symbol",""); qty2=int(h.get("quantity",0) or 0)
            avg=float(h.get("avg_price",0) or 0); cur=float(h.get("current_price",avg) or avg)
            val_now=cur*qty2; cost_b=avg*qty2; pnl_h=val_now-cost_b
            c=st.columns([3,1])
            with c[0]:
                st.markdown(f"""
                <div style='background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;
                            padding:10px 14px;margin-bottom:6px;font-family:DM Mono,monospace;'>
                  <span style='font-size:14px;font-weight:700;color:#FFFFFF;'>{sym}</span>
                  <span style='font-size:12px;color:#808080;margin-left:8px;'>{qty2} shares</span>
                  <span style='float:right;color:{"#22C55E" if pnl_h>=0 else "#EF4444"};font-size:13px;'>
                    {'+' if pnl_h>=0 else ''}₦{pnl_h:,.0f}
                  </span>
                  <br><span style='font-size:11px;color:#A0A0A0;'>
                    Avg ₦{avg:,.2f} · Now ₦{cur:,.2f} · Value ₦{val_now:,.0f}
                  </span>
                </div>""", unsafe_allow_html=True)
            with c[1]:
                if st.button("Sell All", key=f"sell_{sym}", use_container_width=True):
                    proceeds=cur*qty2
                    try:
                        sb.table("paper_holdings").delete().eq("id",h["id"]).execute()
                        sb.table("paper_portfolios").update({"cash_balance":cash+proceeds})\
                          .eq("user_id",uid).execute()
                        st.success(f"Sold {qty2} {sym} for ₦{proceeds:,.0f}"); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
    else:
        st.markdown("<div style='font-family:DM Mono,monospace;font-size:13px;color:#606060;"
                    "padding:16px;text-align:center;'>No holdings yet. Buy some stocks above.</div>",
                    unsafe_allow_html=True)
