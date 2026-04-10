"""
NGX Signal — Trade Game
========================
Hybrid monetisation: Always show DATA, restrict INTELLIGENCE by tier.

Tier access:
  visitor  → gate wall
  free     → 3 trades/day cap, no leaderboard, ₦500k starting balance
  trial    → no cap, no leaderboard (trial is like starter)
  starter  → unlimited trades, ₦1M balance, no leaderboard
  trader   → unlimited, ₦5M balance, leaderboard + advanced stats
  pro      → unlimited, ₦10M balance, leaderboard + advanced stats
"""
import streamlit as st
from app.utils.supabase_client import get_supabase
from app.utils.tiers import (
    get_user_tier, can_access, render_locked_content,
    remaining_today, _increment_daily_count,
    tier_badge, quota_bar,
)

# ── Balance caps per tier ─────────────────────────────────────────────────────
TIER_BALANCE = {
    "visitor":  500_000,
    "free":     500_000,
    "trial":    1_000_000,
    "starter":  1_000_000,
    "trader":   5_000_000,
    "pro":      10_000_000,
}

# ── Schema fix SQL (shown on DB errors) ───────────────────────────────────────
_SCHEMA_FIX_SQL = """
-- Run in Supabase SQL Editor, then refresh the app
ALTER TABLE paper_portfolios
  ADD COLUMN IF NOT EXISTS cash_balance numeric(15,2) NOT NULL DEFAULT 500000,
  ADD COLUMN IF NOT EXISTS total_value  numeric(15,2) NOT NULL DEFAULT 500000,
  ADD COLUMN IF NOT EXISTS plan         text NOT NULL DEFAULT 'free';

ALTER TABLE paper_holdings
  ADD COLUMN IF NOT EXISTS symbol        text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS quantity      integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS avg_price     numeric(15,4) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS current_price numeric(15,4) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS paper_trades (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  symbol text NOT NULL, action text NOT NULL,
  quantity integer NOT NULL, price numeric(15,4) NOT NULL,
  total_value numeric(15,2) NOT NULL, traded_at timestamptz DEFAULT now()
);

NOTIFY pgrst, 'reload schema';
"""


# ══════════════════════════════════════════════════════════════════════════════
# ── Safe DB helpers (handle PGRST204 + column name variations) ────────────────
# ══════════════════════════════════════════════════════════════════════════════

def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _safe_int(val, default: int = 0) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _get_cash(port: dict, fallback: float) -> float:
    for col in ("cash_balance", "balance", "cash", "virtual_balance"):
        v = port.get(col)
        if v is not None:
            return _safe_float(v, fallback)
    return fallback


def _get_total_value(port: dict, cash: float) -> float:
    for col in ("total_value", "total", "portfolio_value", "value"):
        v = port.get(col)
        if v is not None:
            return _safe_float(v, cash)
    return cash


def _update_portfolio(sb, uid: str, new_cash: float, new_total: float) -> None:
    """Update cash_balance + total_value atomically; tries column name fallbacks."""
    for payload in [
        {"cash_balance": new_cash, "total_value": new_total},
        {"cash_balance": new_cash},
        {"balance": new_cash},
    ]:
        try:
            sb.table("paper_portfolios").update(payload).eq("user_id", uid).execute()
            return
        except Exception:
            continue
    st.error("⚠️ Could not update portfolio balance. Run the schema fix SQL.")


def _upsert_holding(sb, uid: str, symbol: str, qty: int, avg_p: float, cur_p: float) -> bool:
    """Insert or update a holding row. Returns True on success."""
    # Try update first (stock already held)
    try:
        existing = sb.table("paper_holdings").select("id,quantity,avg_price") \
            .eq("user_id", uid).eq("symbol", symbol).limit(1).execute()
    except Exception as e:
        st.error(f"Holdings fetch error: {e}\n\n**Fix:** {_SCHEMA_FIX_SQL}")
        return False

    if existing.data:
        row = existing.data[0]
        old_qty = _safe_int(row.get("quantity"), 0)
        old_avg = _safe_float(row.get("avg_price"), cur_p)
        new_qty = old_qty + qty
        new_avg = (old_avg * old_qty + cur_p * qty) / new_qty if new_qty else cur_p
        try:
            sb.table("paper_holdings").update({
                "quantity":      new_qty,
                "avg_price":     round(new_avg, 4),
                "current_price": round(cur_p, 4),
            }).eq("id", row["id"]).execute()
            return True
        except Exception as e:
            st.error(f"Holding update error: {e}\n\n**Fix:** Run schema fix SQL.")
            return False
    else:
        try:
            sb.table("paper_holdings").insert({
                "user_id":       uid,
                "symbol":        symbol,
                "quantity":      qty,
                "avg_price":     round(avg_p, 4),
                "current_price": round(cur_p, 4),
            }).execute()
            return True
        except Exception as e:
            st.error(f"Holding insert error: {e}\n\n**Fix:** Run schema fix SQL.")
            return False


def _log_trade(sb, uid: str, symbol: str, action: str, qty: int, price: float) -> None:
    """Silently log trade to paper_trades table (non-blocking)."""
    try:
        sb.table("paper_trades").insert({
            "user_id":     uid,
            "symbol":      symbol,
            "action":      action,
            "quantity":    qty,
            "price":       round(price, 4),
            "total_value": round(price * qty, 2),
        }).execute()
    except Exception:
        pass  # Trade history logging is non-critical


def _recalc_total(sb, uid: str, cash: float) -> float:
    """Recompute total portfolio value from all holdings."""
    try:
        res = sb.table("paper_holdings").select("quantity,current_price") \
            .eq("user_id", uid).execute()
        equity = sum(
            _safe_int(h.get("quantity")) * _safe_float(h.get("current_price"))
            for h in (res.data or [])
        )
        return cash + equity
    except Exception:
        return cash


def _sync_leaderboard(sb, uid: str, display_name: str, total: float, balance_cap: float) -> None:
    """Upsert leaderboard snapshot (non-blocking)."""
    try:
        ret_pct = round((total - balance_cap) / balance_cap * 100, 4) if balance_cap else 0
        sb.table("leaderboard_snapshots").upsert({
            "user_id":        uid,
            "display_name":   display_name or "Investor",
            "return_percent": ret_pct,
            "total_value":    round(total, 2),
        }, on_conflict="user_id").execute()
    except Exception:
        pass  # Non-critical


# ══════════════════════════════════════════════════════════════════════════════
# SHARE SHEET — TRADE GAME PROFITABLE SALE
# Shown after a sell that produces a gain. Viral surface for NGX Signal.
# ══════════════════════════════════════════════════════════════════════════════

def _render_game_share_sheet(
    symbol:    str,
    qty:       int,
    avg_price: float,
    sell_price: float,
    pnl:       float,
    pnl_pct:   float,
) -> None:
    """
    Renders a bottom-sheet share card after a profitable sell.
    Share text: "I bought GTCO at ₦44.20 and sold at ₦52.80 — +19.5% profit
                 on NGX Signal Trade Game 🚀 ngxsignal.com"
    """
    import requests as _req

    pnl_str  = f"+₦{pnl:,.0f}"
    pct_str  = f"+{pnl_pct:.1f}%"
    buy_str  = f"₦{avg_price:,.2f}"
    sell_str = f"₦{sell_price:,.2f}"

    share_text = (
        f"🚀 Trade Game WIN — NGX Signal\n"
        f"I bought {qty} {symbol} at {buy_str} and sold at {sell_str}\n"
        f"Profit: {pnl_str} ({pct_str}) 📈\n\n"
        f"Playing the NGX Signal Trade Game — practice trading real NGX stocks risk-free.\n"
        f"👉 ngxsignal.com"
    )
    app_url = "https://ngxsignal.com"

    preview_html = (
        f'<div style="font-size:10px;color:#808080;margin-bottom:6px;'
        f'text-transform:uppercase;letter-spacing:.07em;">NGX Signal Trade Game</div>'
        f'<div style="font-size:16px;font-weight:700;color:#22C55E;margin-bottom:4px;">'
        f'{symbol} · {pct_str} 🚀</div>'
        f'<div style="font-size:11px;color:#C0C0C0;line-height:1.6;margin-bottom:6px;">'
        f'Bought {qty} shares at {buy_str} · Sold at {sell_str}<br>'
        f'<strong style="color:#22C55E;">Profit: {pnl_str}</strong></div>'
        f'<div style="font-size:10px;color:#404040;">NGX Signal · ngxsignal.com</div>'
    )

    uid = f"gs_{symbol}_{int(pnl)}"

    st.components.v1.html(f"""
<!DOCTYPE html><html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:transparent;font-family:'DM Mono',monospace;overflow:hidden;}}

/* Win celebration bar */
.win-bar{{
  display:flex;align-items:center;gap:10px;
  background:linear-gradient(135deg,rgba(34,197,94,.08),rgba(34,197,94,.04));
  border:1px solid rgba(34,197,94,.3);border-radius:10px;
  padding:12px 16px;margin-bottom:0;
}}
.win-emoji{{font-size:22px;}}
.win-text{{flex:1;font-size:12px;color:#22C55E;font-weight:600;}}
.win-pct{{font-family:'DM Mono',monospace;font-size:16px;font-weight:700;color:#22C55E;}}
.shr-trigger{{
  display:inline-flex;align-items:center;gap:6px;
  background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);
  border-radius:7px;padding:6px 12px;cursor:pointer;
  font-family:'DM Mono',monospace;font-size:11px;color:#22C55E;
  transition:all .15s;margin-top:8px;
}}
.shr-trigger:hover{{background:rgba(34,197,94,.18);border-color:#22C55E;}}

/* Backdrop */
.shr-backdrop{{display:none;position:fixed;inset:0;z-index:99990;
               background:rgba(0,0,0,.75);backdrop-filter:blur(4px);}}
/* Sheet */
.shr-sheet{{display:none;position:fixed;bottom:0;left:0;right:0;z-index:99999;
            background:#0E0E0E;border-top:1px solid #2A2A2A;
            border-radius:20px 20px 0 0;
            padding:0 0 env(safe-area-inset-bottom,24px) 0;
            animation:shr-slide-up .28s cubic-bezier(.16,1,.3,1) both;
            max-width:520px;margin:0 auto;}}
.shr-handle{{width:40px;height:4px;background:#2A2A2A;border-radius:2px;margin:12px auto 16px;}}
.shr-title{{font-family:'DM Mono',monospace;font-size:12px;font-weight:700;
            color:#FFFFFF;text-align:center;margin-bottom:4px;}}
.shr-subtitle{{font-family:'DM Mono',monospace;font-size:10px;color:#505050;
               text-align:center;margin-bottom:16px;letter-spacing:.04em;}}
.shr-preview{{background:#0A0A0A;border:1px solid rgba(34,197,94,.2);
              border-left:3px solid #22C55E;border-radius:10px;
              padding:12px 16px;margin:0 16px 16px;font-family:'DM Mono',monospace;}}
.shr-options{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:0 16px 12px;}}
.shr-btn{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;
          background:#141414;border:1px solid #222;border-radius:12px;padding:14px 8px;
          cursor:pointer;font-family:'DM Mono',monospace;font-size:11px;color:#A0A0A0;
          text-decoration:none;transition:all .15s;}}
.shr-btn:hover{{background:#1A1A1A;border-color:#3A3A3A;color:#FFFFFF;}}
.shr-btn-icon{{font-size:24px;line-height:1;}}
.shr-btn-wa{{border-color:rgba(37,211,102,.2);}}
.shr-btn-wa:hover{{border-color:#25D366;background:rgba(37,211,102,.07);color:#25D366;}}
.shr-btn-x{{border-color:rgba(255,255,255,.1);}}
.shr-btn-x:hover{{border-color:#fff;background:rgba(255,255,255,.04);color:#fff;}}
.shr-btn-copy{{border-color:rgba(34,197,94,.2);}}
.shr-btn-copy:hover{{border-color:#22C55E;background:rgba(34,197,94,.06);color:#22C55E;}}
.shr-close{{width:calc(100% - 32px);margin:4px 16px 0;background:transparent;
            border:1px solid #1F1F1F;border-radius:10px;padding:12px;
            font-family:'DM Mono',monospace;font-size:12px;color:#505050;cursor:pointer;
            transition:all .15s;}}
.shr-close:hover{{color:#FFFFFF;border-color:#3A3A3A;}}
.copied-flash{{display:none;position:absolute;top:-28px;left:50%;transform:translateX(-50%);
               background:#22C55E;color:#000;font-size:10px;font-weight:700;
               padding:3px 10px;border-radius:6px;white-space:nowrap;}}
@keyframes shr-slide-up{{from{{transform:translateY(100%);}}to{{transform:translateY(0);}}}}
</style>
</head>
<body>

<!-- Win celebration + share trigger -->
<div class="win-bar">
  <span class="win-emoji">🎉</span>
  <div class="win-text">
    Sold {symbol} for a profit!<br>
    <span style="font-size:11px;color:#A0A0A0;">
      {buy_str} → {sell_str} · {qty} shares
    </span>
  </div>
  <span class="win-pct">{pct_str}</span>
</div>
<button class="shr-trigger" onclick="openSheet_{uid}()">
  ↗ Share your win
</button>

<!-- Backdrop -->
<div class="shr-backdrop" id="bd_{uid}" onclick="closeSheet_{uid}()"></div>

<!-- Bottom sheet -->
<div class="shr-sheet" id="sh_{uid}">
  <div class="shr-handle"></div>
  <div class="shr-title">Share your trade win 🚀</div>
  <div class="shr-subtitle">Show your WhatsApp group what NGX Signal caught</div>

  <div class="shr-preview">{preview_html}</div>

  <div class="shr-options">
    <a class="shr-btn shr-btn-wa"
       href="https://wa.me/?text={_req.utils.quote(share_text)}"
       target="_blank" rel="noopener"
       onclick="closeSheet_{uid}()">
      <span class="shr-btn-icon">💬</span>
      <span>WhatsApp</span>
    </a>
    <a class="shr-btn shr-btn-x"
       href="https://twitter.com/intent/tweet?text={_req.utils.quote(share_text)}"
       target="_blank" rel="noopener"
       onclick="closeSheet_{uid}()">
      <span class="shr-btn-icon">𝕏</span>
      <span>X / Twitter</span>
    </a>
    <button class="shr-btn shr-btn-copy" onclick="copyText_{uid}()" style="position:relative;">
      <span class="copied-flash" id="cp_flash_{uid}">Copied!</span>
      <span class="shr-btn-icon">📋</span>
      <span id="cp_lbl_{uid}">Copy text</span>
    </button>
  </div>

  <button class="shr-close" onclick="closeSheet_{uid}()">✕ Close</button>
</div>

<script>
var _shareText_{uid} = {repr(share_text)};

function openSheet_{uid}() {{
  document.getElementById('bd_{uid}').style.display = 'block';
  document.getElementById('sh_{uid}').style.display = 'block';
  window.parent.postMessage({{type:'streamlit:setFrameHeight', height:540}}, '*');
}}
function closeSheet_{uid}() {{
  document.getElementById('bd_{uid}').style.display = 'none';
  document.getElementById('sh_{uid}').style.display = 'none';
  window.parent.postMessage({{type:'streamlit:setFrameHeight', height:100}}, '*');
}}
function copyText_{uid}() {{
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(_shareText_{uid}).then(function() {{ showCopied_{uid}(); }});
  }} else {{
    var ta = document.createElement('textarea');
    ta.value = _shareText_{uid};
    ta.style.position='fixed';ta.style.opacity='0';
    document.body.appendChild(ta);ta.select();
    try{{document.execCommand('copy');showCopied_{uid}();}}catch(e){{}}
    document.body.removeChild(ta);
  }}
}}
function showCopied_{uid}() {{
  document.getElementById('cp_flash_{uid}').style.display='block';
  document.getElementById('cp_lbl_{uid}').textContent='Copied!';
  setTimeout(function(){{
    document.getElementById('cp_flash_{uid}').style.display='none';
    document.getElementById('cp_lbl_{uid}').textContent='Copy text';
  }},2000);
  setTimeout(function(){{closeSheet_{uid}();}},2200);
}}
window.parent.postMessage({{type:'streamlit:setFrameHeight', height:100}}, '*');
</script>
</body></html>
""", height=102, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# ── Main render ───────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def render():
    sb   = get_supabase()
    tier = get_user_tier()
    user = st.session_state.get("user")

    # ── Page CSS ──────────────────────────────────────────────────────────────
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700;800&display=swap');
.game-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px;text-align:center;margin-bottom:12px;}
.game-label{font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;}
.game-val{font-family:'DM Mono',monospace;font-size:20px;font-weight:500;}
.hold-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:10px 14px;margin-bottom:6px;font-family:'DM Mono',monospace;}
.lb-row{display:flex;align-items:center;gap:12px;background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px 18px;margin-bottom:8px;font-family:'DM Mono',monospace;}
.stat-mini{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px;text-align:center;font-family:'DM Mono',monospace;}
.trade-row{background:#0A0A0A;border:1px solid #1A1A1A;border-radius:6px;padding:8px 12px;margin-bottom:4px;font-family:'DM Mono',monospace;font-size:11px;color:#A0A0A0;}
</style>
""", unsafe_allow_html=True)

    balance_cap = TIER_BALANCE.get(tier, 500_000)
    profile     = st.session_state.get("profile", {})

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">
  <div>
    <div style='font-family:Space Grotesk,sans-serif;font-size:22px;font-weight:800;
                color:#FFFFFF;margin-bottom:4px;'>🎮 NGX Trade Game</div>
    <div style='font-family:DM Mono,monospace;font-size:11px;color:#808080;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:20px;'>
      Paper trading · Virtual ₦{balance_cap:,} · No real money
    </div>
  </div>
  <div style="padding-top:4px;">{tier_badge(tier)}</div>
</div>
""", unsafe_allow_html=True)

    # ── Visitor gate ──────────────────────────────────────────────────────────
    if tier == "visitor":
        st.markdown("""
<div style='background:#0A0A0A;border:1px solid rgba(240,165,0,0.3);border-radius:12px;
            padding:24px;text-align:center;'>
  <div style='font-size:40px;margin-bottom:12px;'>🎮</div>
  <div style='font-family:Space Grotesk,sans-serif;font-size:18px;font-weight:700;
              color:#FFFFFF;margin-bottom:8px;'>Practice NGX Trading</div>
  <div style='font-family:DM Mono,monospace;font-size:13px;color:#E0E0E0;line-height:1.7;
              margin-bottom:16px;'>
    Trade real NGX stocks with virtual money. No risk, pure skill building.
    Create a free account to play.
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("Create Free Account →", key="game_visitor_cta",
                     type="primary", use_container_width=True):
            st.session_state.current_page = "settings"
            st.rerun()
        return

    # ── Must be logged in ──────────────────────────────────────────────────────
    if not user:
        st.warning("Please log in to access the Trade Game.")
        return

    uid          = user.id
    display_name = profile.get("display_name") or profile.get("full_name") or "Investor"

    # ── Trade quota bar (free tier) ───────────────────────────────────────────
    _trades_allowed = True
    if tier == "free":
        rem_trades = remaining_today("trades", tier)
        quota_bar("trades", tier)
        if rem_trades is not None and rem_trades == 0:
            render_locked_content("game_unlimited_trades", "game_trade_cap")
            _trades_allowed = False

    # ── Portfolio fetch / create ──────────────────────────────────────────────
    port = None
    try:
        pg_res = sb.table("paper_portfolios").select("*") \
            .eq("user_id", uid).limit(1).execute()
        port = pg_res.data[0] if pg_res.data else None
    except Exception as e:
        st.error(f"⚠️ Portfolio load failed: {e}")
        with st.expander("🔧 Schema Fix SQL — run in Supabase SQL Editor"):
            st.code(_SCHEMA_FIX_SQL, language="sql")
        return

    if not port:
        _render_onboarding(sb, uid, tier, balance_cap)
        return

    # ── Portfolio metrics ─────────────────────────────────────────────────────
    cash    = _get_cash(port, balance_cap)
    total   = _get_total_value(port, cash)
    pnl     = total - balance_cap
    pnl_pct = (pnl / balance_cap * 100) if balance_cap else 0
    pnl_col = "#22C55E" if pnl >= 0 else "#EF4444"

    c1, c2, c3 = st.columns(3)
    for col, label, val, color in [
        (c1, "Cash Balance",    f"₦{cash:,.0f}",   "#F0A500"),
        (c2, "Portfolio Value", f"₦{total:,.0f}",  "#FFFFFF"),
        (c3, "Total P&L",       f"{'+'if pnl>=0 else ''}₦{pnl:,.0f} ({pnl_pct:+.1f}%)", pnl_col),
    ]:
        with col:
            st.markdown(f"""
<div class="game-card">
  <div class="game-label">{label}</div>
  <div class="game-val" style="color:{color};">{val}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Advanced stats (trader / pro) ─────────────────────────────────────────
    if can_access("game_advanced_stats", tier):
        _render_advanced_stats(sb, uid, cash, total, balance_cap, pnl, pnl_pct)

    # ── Buy form ──────────────────────────────────────────────────────────────
    if _trades_allowed:
        with st.expander("📈 Buy a Stock", expanded=False):
            _render_buy_form(sb, uid, cash, total, tier, balance_cap, display_name)
    else:
        st.markdown("""
<div style="background:#0A0A0A;border:1px dashed #2A2A2A;border-radius:10px;
            padding:16px;text-align:center;font-family:'DM Mono',monospace;
            font-size:12px;color:#606060;">
  🔒 Daily trade limit reached. Upgrade for unlimited trades.
</div>""", unsafe_allow_html=True)

    # ── Holdings ──────────────────────────────────────────────────────────────
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    st.markdown("**📦 Current Holdings**")
    try:
        hold_res = sb.table("paper_holdings").select("*").eq("user_id", uid).execute()
        holdings = hold_res.data or []
    except Exception:
        holdings = []

    if holdings:
        for h in holdings:
            sym   = h.get("symbol", "")
            qty   = _safe_int(h.get("quantity"))
            avg   = _safe_float(h.get("avg_price"))
            cur   = _safe_float(h.get("current_price"), avg)
            val_n = cur * qty
            cost_b = avg * qty
            pnl_h = val_n - cost_b
            pnl_c = "#22C55E" if pnl_h >= 0 else "#EF4444"

            hc = st.columns([3, 1, 1])
            with hc[0]:
                st.markdown(f"""
<div class="hold-card">
  <span style='font-size:14px;font-weight:700;color:#FFFFFF;'>{sym}</span>
  <span style='font-size:12px;color:#808080;margin-left:8px;'>{qty} shares</span>
  <span style='float:right;color:{pnl_c};font-size:13px;'>
    {'+' if pnl_h>=0 else ''}₦{pnl_h:,.0f}
  </span>
  <br><span style='font-size:11px;color:#A0A0A0;'>
    Avg ₦{avg:,.2f} · Now ₦{cur:,.2f} · Value ₦{val_n:,.0f}
  </span>
</div>""", unsafe_allow_html=True)

            with hc[1]:
                sell_qty = st.number_input(
                    "Qty", min_value=1, max_value=max(qty, 1),
                    value=qty, step=1, key=f"sell_qty_{sym}",
                    label_visibility="collapsed"
                )
            with hc[2]:
                if st.button("Sell", key=f"sell_{sym}", use_container_width=True):
                    if not _trades_allowed:
                        st.error("Daily trade limit reached.")
                    else:
                        _do_sell(sb, uid, h, cur, sell_qty, cash, total,
                                 tier, balance_cap, display_name)
    else:
        st.markdown("""
<div style='font-family:DM Mono,monospace;font-size:13px;color:#606060;
            padding:16px;text-align:center;'>
  No holdings yet. Buy some stocks above.
</div>""", unsafe_allow_html=True)

    # ── Trade History (collapsible) ───────────────────────────────────────────
    with st.expander("📋 Trade History", expanded=False):
        _render_trade_history(sb, uid)

    # ── Leaderboard (trader / pro only) ──────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if can_access("game_leaderboard", tier):
        _render_leaderboard(sb, uid, tier)
    else:
        render_locked_content("game_leaderboard", "game_lb_lock", compact=True)

    # ── Reset portfolio option ────────────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    with st.expander("⚠️ Reset Portfolio", expanded=False):
        st.warning("This will delete all holdings and restart with your plan balance. Cannot be undone.")
        if st.button("🔄 Reset My Portfolio", key="game_reset", type="secondary"):
            _reset_portfolio(sb, uid, balance_cap, tier)

    # ── Upgrade nudge for free tier ───────────────────────────────────────────
    if tier == "free":
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown("""
<div style="background:linear-gradient(135deg,#1A1600,#2A2200);border:1px solid #3D2E00;
            border-radius:12px;padding:20px 24px;">
  <div style="font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;
              color:#F0A500;margin-bottom:6px;">🎮 Upgrade Your Game</div>
  <div style="font-family:'DM Mono',monospace;font-size:12px;color:#B0B0B0;line-height:1.7;">
    Free: 3 trades/day · ₦500k balance · No leaderboard<br>
    Starter: Unlimited trades · ₦1M balance<br>
    Trader: ₦5M balance · Leaderboard · Advanced analytics<br>
    Pro: ₦10M balance · Full competitive features
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        if st.button("Upgrade Plan →", key="game_upgrade_cta", type="primary"):
            st.session_state.current_page = "settings"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ── Sub-renderers ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def _render_onboarding(sb, uid: str, tier: str, balance_cap: float) -> None:
    """First-time portfolio creation screen."""
    st.markdown(f"""
<div style='background:#0A0A0A;border:1px solid rgba(240,165,0,0.3);border-radius:12px;
            padding:24px;text-align:center;'>
  <div style='font-size:40px;margin-bottom:12px;'>🎮</div>
  <div style='font-family:Space Grotesk,sans-serif;font-size:18px;font-weight:700;
              color:#FFFFFF;margin-bottom:8px;'>Start Your Virtual Portfolio</div>
  <div style='font-family:DM Mono,monospace;font-size:13px;color:#E0E0E0;line-height:1.7;
              margin-bottom:16px;'>
    Practice trading NGX stocks with
    <strong style="color:#F0A500;">₦{balance_cap:,}</strong> virtual naira.
    No real money involved.
  </div>
  <div style='font-family:DM Mono,monospace;font-size:11px;color:#606060;'>
    {tier.upper()} plan balance · Upgrade for larger starting balances
  </div>
</div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if st.button(f"🚀 Start Trading with Virtual ₦{balance_cap:,}",
                 type="primary", use_container_width=True, key="game_start"):
        ok = False
        # Try full insert → minimal insert → fallback
        for payload in [
            {"user_id": uid, "cash_balance": balance_cap, "total_value": balance_cap, "plan": tier},
            {"user_id": uid, "cash_balance": balance_cap},
            {"user_id": uid, "balance": balance_cap},
        ]:
            try:
                sb.table("paper_portfolios").insert(payload).execute()
                ok = True
                break
            except Exception:
                continue

        if ok:
            st.success("✅ Portfolio created! Let's trade.")
            st.rerun()
        else:
            st.error("Could not create portfolio. Run the schema fix SQL in Supabase.")
            with st.expander("🔧 Schema Fix SQL"):
                st.code(_SCHEMA_FIX_SQL, language="sql")


def _render_buy_form(sb, uid: str, cash: float, total: float,
                     tier: str, balance_cap: float, display_name: str) -> None:
    # Fetch latest prices
    try:
        pr_res = sb.table("stock_prices").select("symbol,price") \
            .order("trading_date", desc=True).limit(500).execute()
        prices_raw = pr_res.data or []
        seen: set = set()
        sym_prices: dict[str, float] = {}
        for p in prices_raw:
            s = p.get("symbol", "")
            if s and s not in seen:
                seen.add(s)
                sym_prices[s] = _safe_float(p.get("price"))
        syms = sorted(sym_prices.keys())
    except Exception as e:
        st.error(f"Could not load stock prices: {e}")
        return

    if not syms:
        st.info("No price data available right now.")
        return

    ca, cb = st.columns(2)
    with ca:
        sel_sym = st.selectbox("Stock", syms, key="game_buy_sym")
    with cb:
        qty = st.number_input("Quantity", min_value=1, step=1, value=100, key="game_buy_qty")

    cur_price = sym_prices.get(sel_sym, 0.0)
    cost      = cur_price * qty

    st.markdown(
        f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#FFFFFF;margin-bottom:8px;'>"
        f"Price: ₦{cur_price:,.2f} · Cost: <strong style='color:#F0A500;'>₦{cost:,.2f}</strong> · "
        f"Cash available: <span style='color:#808080;'>₦{cash:,.0f}</span></div>",
        unsafe_allow_html=True,
    )

    btn_disabled = cost > cash or cur_price <= 0
    if st.button(
        f"Buy {qty} × {sel_sym}",
        type="primary",
        key="game_buy_btn",
        disabled=btn_disabled,
    ):
        if cost > cash:
            st.error(f"Insufficient cash. Need ₦{cost:,.0f}, have ₦{cash:,.0f}")
            return
        if cur_price <= 0:
            st.error("No valid price for this stock today.")
            return

        if tier == "free":
            _increment_daily_count("trades")

        ok = _upsert_holding(sb, uid, sel_sym, qty, cur_price, cur_price)
        if ok:
            new_cash  = cash - cost
            new_total = _recalc_total(sb, uid, new_cash)
            _update_portfolio(sb, uid, new_cash, new_total)
            _log_trade(sb, uid, sel_sym, "buy", qty, cur_price)
            _sync_leaderboard(sb, uid, display_name, new_total, balance_cap)
            st.success(f"✅ Bought {qty} shares of {sel_sym} @ ₦{cur_price:,.2f}")
            st.rerun()


def _do_sell(sb, uid: str, holding: dict, cur: float, qty: int,
             cash: float, total: float, tier: str,
             balance_cap: float, display_name: str) -> None:
    sym      = holding.get("symbol", "")
    held_qty = _safe_int(holding.get("quantity"))
    avg      = _safe_float(holding.get("avg_price"), cur)

    if qty > held_qty:
        st.error(f"Cannot sell {qty} — only holding {held_qty} shares.")
        return
    if cur <= 0:
        st.error("No valid price to sell at.")
        return

    proceeds = cur * qty
    pnl_per_share = cur - avg
    pnl_total     = pnl_per_share * qty
    pnl_pct       = ((cur - avg) / avg * 100) if avg > 0 else 0
    is_profit     = pnl_total > 0

    try:
        if qty == held_qty:
            # Sell everything — delete row
            sb.table("paper_holdings").delete().eq("id", holding["id"]).execute()
        else:
            # Partial sell — reduce quantity
            sb.table("paper_holdings").update({
                "quantity": held_qty - qty,
                "current_price": round(cur, 4),
            }).eq("id", holding["id"]).execute()
    except Exception as e:
        st.error(f"Sell error: {e}")
        return

    new_cash  = cash + proceeds
    new_total = _recalc_total(sb, uid, new_cash)
    _update_portfolio(sb, uid, new_cash, new_total)
    _log_trade(sb, uid, sym, "sell", qty, cur)
    _sync_leaderboard(sb, uid, display_name, new_total, balance_cap)

    if tier == "free":
        _increment_daily_count("trades")

    st.success(f"✅ Sold {qty} shares of {sym} for ₦{proceeds:,.0f}")

    # ── Share sheet for profitable sells ──────────────────────────────────────
    if is_profit:
        _render_game_share_sheet(
            symbol     = sym,
            qty        = qty,
            avg_price  = avg,
            sell_price = cur,
            pnl        = pnl_total,
            pnl_pct    = pnl_pct,
        )
    # ─────────────────────────────────────────────────────────────────────────
    st.rerun()


def _render_trade_history(sb, uid: str) -> None:
    try:
        res = sb.table("paper_trades").select("*") \
            .eq("user_id", uid).order("traded_at", desc=True).limit(20).execute()
        trades = res.data or []
    except Exception:
        trades = []

    if not trades:
        st.markdown("<div style='color:#606060;font-size:12px;font-family:DM Mono,monospace;'>"
                    "No trades yet.</div>", unsafe_allow_html=True)
        return

    for t in trades:
        action = t.get("action", "buy")
        sym    = t.get("symbol", "")
        qty    = _safe_int(t.get("quantity"))
        price  = _safe_float(t.get("price"))
        total  = _safe_float(t.get("total_value"))
        when   = str(t.get("traded_at", ""))[:16].replace("T", " ")
        acol   = "#22C55E" if action == "buy" else "#EF4444"
        alabel = "BUY" if action == "buy" else "SELL"
        st.markdown(f"""
<div class="trade-row">
  <span style="color:{acol};font-weight:700;">{alabel}</span>
  <span style="color:#FFFFFF;margin-left:8px;">{sym}</span>
  <span style="color:#808080;margin-left:6px;">{qty} shares @ ₦{price:,.2f}</span>
  <span style="float:right;color:#F0A500;">₦{total:,.0f}</span>
  <br><span style="color:#505050;">{when}</span>
</div>""", unsafe_allow_html=True)


def _render_leaderboard(sb, uid: str, tier: str) -> None:
    st.markdown("""
<div style="font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;
            color:#FFFFFF;margin-bottom:10px;">🏆 Leaderboard</div>
""", unsafe_allow_html=True)
    try:
        board_res = sb.table("leaderboard_snapshots") \
            .select("display_name,return_percent,total_value,user_id") \
            .order("return_percent", desc=True).limit(10).execute()
        board = board_res.data or []
    except Exception:
        board = []

    medals = ["🥇", "🥈", "🥉"]
    if board:
        for i, e in enumerate(board):
            ret   = _safe_float(e.get("return_percent"))
            dname = (e.get("display_name") or "Investor")[:22]
            medal = medals[i] if i < 3 else f"#{i+1}"
            is_me = e.get("user_id") == uid
            ncol  = "#F0A500" if is_me else "#FFFFFF"
            rcol  = "#22C55E" if ret >= 0 else "#EF4444"
            you   = ('<span style="background:#1A1600;border:1px solid #3D2E00;color:#F0A500;'
                     'font-size:9px;padding:1px 5px;border-radius:3px;margin-left:6px;">YOU</span>'
                     if is_me else "")
            st.markdown(f"""
<div class="lb-row">
  <span style="font-size:20px;min-width:28px;">{medal}</span>
  <span style="flex:1;font-size:14px;color:{ncol};">{dname}{you}</span>
  <span style="font-size:15px;font-weight:600;color:{rcol};">{"+"if ret>=0 else ""}{ret:.1f}%</span>
</div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
<div style='background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:24px;
            text-align:center;font-family:DM Mono,monospace;color:#606060;'>
  No traders on the board yet — be the first! 🏆
</div>""", unsafe_allow_html=True)


def _render_advanced_stats(sb, uid: str, cash: float, total: float,
                           balance_cap: float, pnl: float, pnl_pct: float) -> None:
    st.markdown("""
<div style="font-family:'DM Mono',monospace;font-size:10px;color:#606060;
            text-transform:uppercase;letter-spacing:.1em;margin:12px 0 8px 0;">
  📊 Portfolio Analytics
</div>""", unsafe_allow_html=True)

    try:
        hold_res = sb.table("paper_holdings").select("quantity,avg_price,current_price,symbol") \
            .eq("user_id", uid).execute()
        holdings = hold_res.data or []
    except Exception:
        holdings = []

    n_positions = len(holdings)
    cash_pct    = (cash / total * 100) if total > 0 else 100
    equity_pct  = 100 - cash_pct

    best_hold  = max(
        holdings,
        key=lambda h: _safe_float(h.get("quantity")) * (
            _safe_float(h.get("current_price")) - _safe_float(h.get("avg_price"))
        ),
        default=None,
    ) if holdings else None

    best_sym   = best_hold.get("symbol", "—") if best_hold else "—"
    best_pnl_v = (
        _safe_float(best_hold.get("quantity")) *
        (_safe_float(best_hold.get("current_price")) - _safe_float(best_hold.get("avg_price")))
    ) if best_hold else 0

    sc = st.columns(4)
    stats = [
        ("Positions",   str(n_positions),                          "#FFFFFF"),
        ("Cash %",      f"{cash_pct:.1f}%",                        "#F0A500"),
        ("Equity %",    f"{equity_pct:.1f}%",                      "#22C55E" if equity_pct > 0 else "#606060"),
        ("Best Hold",   f"{best_sym} {'+' if best_pnl_v>=0 else ''}₦{best_pnl_v:,.0f}",
                        "#22C55E" if best_pnl_v >= 0 else "#EF4444"),
    ]
    for i, (label, val, color) in enumerate(stats):
        with sc[i]:
            st.markdown(f"""
<div class="stat-mini">
  <div style="font-size:9px;color:#606060;text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px;">{label}</div>
  <div style="font-size:13px;font-weight:600;color:{color};">{val}</div>
</div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


def _reset_portfolio(sb, uid: str, balance_cap: float, tier: str) -> None:
    """Delete all holdings and reset cash balance."""
    try:
        sb.table("paper_holdings").delete().eq("user_id", uid).execute()
    except Exception:
        pass
    try:
        sb.table("paper_trades").delete().eq("user_id", uid).execute()
    except Exception:
        pass
    _update_portfolio(sb, uid, balance_cap, balance_cap)
    st.success(f"✅ Portfolio reset to ₦{balance_cap:,}. Fresh start!")
    st.rerun()
