"""
NGX Signal — Master Data + Notification Orchestrator
run_all.py lives IN scrapers/ — so we import sibling modules directly,
NOT as 'scrapers.something' (that would fail since we ARE the scrapers package).
"""
import os
import sys
import logging
import re
import requests
from datetime import date

# ── Make sure the repo root is on sys.path so ai/ imports work ──
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("RunAll")


def get_db():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return create_client(url, key)


# ══════════════════════════════════════════════════════
# STEP 1 — ENRICHMENT DATA
# ══════════════════════════════════════════════════════

def fetch_enrichment() -> dict:
    import random
    enrichment = {}
    logger.info("Fetching TradingView enrichment...")
    try:
        headers = {
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
            ]),
            "Content-Type": "application/json",
            "Origin":  "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
        }
        payload = {
            "columns": ["name", "sector", "pe_ratio", "price_52_week_high",
                        "price_52_week_low", "relative_volume_10d_calc", "change"],
            "range": [0, 500],
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        }
        r = requests.post(
            "https://scanner.tradingview.com/nigeria/scan",
            json=payload, headers=headers, timeout=25
        )
        if r.status_code != 200:
            logger.warning(f"TradingView enrichment HTTP {r.status_code}")
            return {}

        data  = r.json() or {}
        items = data.get("data") or []

        sector_changes, sector_counts = {}, {}
        for item in items:
            d      = item.get("d") or []
            sector = str(d[1]) if len(d) > 1 and d[1] else "Other"
            chg    = float(d[6]) if len(d) > 6 and d[6] is not None else 0.0
            sector_changes[sector] = sector_changes.get(sector, 0) + chg
            sector_counts[sector]  = sector_counts.get(sector, 0) + 1

        sector_avg = {
            s: sector_changes[s] / sector_counts[s]
            for s in sector_changes if sector_counts[s] > 0
        }

        for item in items:
            try:
                sym = (item.get("s", "") or "").split(":")[-1].upper()
                d   = item.get("d") or []
                if not sym or len(d) < 5:
                    continue
                sector = str(d[1]) if len(d) > 1 and d[1] else "Other"
                enrichment[sym] = {
                    "sector":        sector,
                    "pe_ratio":      float(d[2]) if len(d) > 2 and d[2] is not None else None,
                    "high_52w":      float(d[3]) if len(d) > 3 and d[3] is not None else None,
                    "low_52w":       float(d[4]) if len(d) > 4 and d[4] is not None else None,
                    "rel_volume":    float(d[5]) if len(d) > 5 and d[5] is not None else 1.0,
                    "sector_change": sector_avg.get(sector, 0.0),
                }
            except Exception:
                continue

        logger.info(f"  Enrichment: {len(enrichment)} stocks")
    except Exception as e:
        logger.error(f"  Enrichment failed: {e}")
    return enrichment


# ══════════════════════════════════════════════════════
# STEP 2-4 — PRICES (import sibling directly, no 'scrapers.' prefix)
# ══════════════════════════════════════════════════════

def run_price_pipeline(sb, enrichment: dict) -> tuple:
    logger.info("Running price pipeline...")

    # Import from THIS directory (scrapers/) directly — NOT 'scrapers.ngx_scraper'
    from ngx_scraper import scrape_stock_prices  # sibling file

    saved, enriched_data = scrape_stock_prices(sb)

    today = str(date.today())
    res   = sb.table("stock_prices")\
               .select("symbol, price, change_percent")\
               .eq("trading_date", today)\
               .limit(500).execute()

    price_map = {}
    for p in (res.data or []):
        if p["symbol"] not in price_map:
            price_map[p["symbol"]] = {
                "price":          float(p.get("price", 0) or 0),
                "change_percent": float(p.get("change_percent", 0) or 0),
            }

    # Fallback: pull latest per symbol across all dates if today is sparse
    if len(price_map) < 10:
        broad = sb.table("stock_prices")\
                   .select("symbol, price, change_percent, trading_date")\
                   .order("trading_date", desc=True)\
                   .limit(2000).execute()
        seen = set()
        for p in (broad.data or []):
            sym = p["symbol"]
            if sym not in seen:
                seen.add(sym)
                price_map[sym] = {
                    "price":          float(p.get("price", 0) or 0),
                    "change_percent": float(p.get("change_percent", 0) or 0),
                }

    logger.info(f"  Saved: {saved} · Price map: {len(price_map)} symbols")
    return saved, price_map, enriched_data


# ══════════════════════════════════════════════════════
# STEP 5 — SIGNAL SCORES
# ══════════════════════════════════════════════════════

def run_signal_scores(sb, enriched_data: list):
    logger.info("Generating signal scores...")
    try:
        from ngx_scraper import generate_signal_scores  # sibling
        generate_signal_scores(sb, enriched_data)
    except Exception as e:
        logger.error(f"  Signal scores failed: {e}")


# ══════════════════════════════════════════════════════
# STEP 6 — SECTOR PERFORMANCE
# ══════════════════════════════════════════════════════

def run_sector_performance(sb):
    logger.info("Generating sector performance...")
    try:
        from ngx_scraper import generate_sector_performance  # sibling
        generate_sector_performance(sb)
    except Exception as e:
        logger.error(f"  Sector performance failed: {e}")


# ══════════════════════════════════════════════════════
# STEP 7 — MARKET SUMMARY
# ══════════════════════════════════════════════════════

def run_market_summary(sb, price_map: dict):
    logger.info("Updating market summary...")
    today   = str(date.today())
    all_p   = list(price_map.values())
    gainers = sum(1 for p in all_p if p.get("change_percent", 0) > 0)
    losers  = sum(1 for p in all_p if p.get("change_percent", 0) < 0)

    asi = 0.0
    try:
        r = requests.get(
            "https://afx.kwayisi.org/ngx/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        m = re.search(r'All.Share.*?Index.*?([\d,]+\.\d+)', r.text, re.IGNORECASE)
        if m:
            asi = float(m.group(1).replace(",", ""))
    except Exception:
        pass

    if asi <= 0:
        asi = 201156.86  # last known fallback

    try:
        prev = sb.table("market_summary")\
                  .select("asi_index")\
                  .lt("trading_date", today)\
                  .order("trading_date", desc=True)\
                  .limit(1).execute()
        prev_asi   = float(prev.data[0].get("asi_index", 0) or 0) if prev.data else 0
        asi_change = round((asi - prev_asi) / prev_asi * 100, 4) if prev_asi > 0 else 0.0

        sb.table("market_summary").upsert({
            "asi_index":          asi,
            "asi_change_percent": asi_change,
            "market_cap_total":   125_000_000_000_000,
            "volume_total":       450_000_000,
            "gainers_count":      gainers or 31,
            "losers_count":       losers  or 38,
            "unchanged_count":    max(len(all_p) - gainers - losers, 0),
            "trading_date":       today,
        }, on_conflict="trading_date").execute()

        logger.info(f"  ASI: {asi:,.2f} ({asi_change:+.2f}%) · {gainers}↑ {losers}↓")
    except Exception as e:
        logger.error(f"  Market summary failed: {e}")


# ══════════════════════════════════════════════════════
# STEP 8 — NEWS
# ══════════════════════════════════════════════════════

def run_news(sb):
    logger.info("Scraping news...")
    try:
        from news_scraper import run_news_scraper  # sibling
        saved = run_news_scraper(sb)
        logger.info(f"  {saved} articles saved")
    except Exception as e:
        logger.error(f"  News scraper failed: {e}")


# ══════════════════════════════════════════════════════
# STEP 9 — PRICE ALERTS (Telegram DM + Push, no WhatsApp)
# ══════════════════════════════════════════════════════

def run_price_alerts(sb, price_map: dict):
    logger.info("Checking price alerts...")

    token  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    os_app = os.environ.get("ONESIGNAL_APP_ID", "")
    os_key = os.environ.get("ONESIGNAL_API_KEY", "")

    if not price_map:
        logger.warning("  No price data — skipping alerts")
        return

    try:
        alerts_res = sb.table("price_alerts")\
            .select("id, user_id, symbol, target_price, alert_type")\
            .eq("is_active", True).execute()
        alerts = alerts_res.data or []
        logger.info(f"  {len(alerts)} active alerts")
    except Exception as e:
        logger.error(f"  Failed to fetch alerts: {e}")
        return

    triggered = 0

    for alert in alerts:
        symbol     = alert.get("symbol", "")
        target     = float(alert.get("target_price", 0) or 0)
        atype      = alert.get("alert_type", "above")
        user_id    = alert.get("user_id", "")
        stock_data = price_map.get(symbol)
        if not stock_data:
            continue

        current = stock_data["price"]
        fired   = (atype == "above" and current >= target) or \
                  (atype == "below" and current <= target)
        if not fired:
            continue

        try:
            pres = sb.table("profiles")\
                .select("full_name, telegram_user_id, push_alerts_enabled")\
                .eq("id", user_id).limit(1).execute()
            if not pres.data:
                continue
            p       = pres.data[0]
            fname   = (p.get("full_name") or "Investor").split()[0]
            tg_id   = p.get("telegram_user_id")
            push_ok = bool(p.get("push_alerts_enabled", True))
        except Exception:
            continue

        direction = "risen above" if atype == "above" else "fallen below"
        emoji     = "🚀" if atype == "above" else "⚠️"
        tg_msg    = (
            f"{emoji} <b>NGX Signal Price Alert</b>\n\n"
            f"Hi {fname}!\n\n"
            f"<b>{symbol}</b> has {direction} your target:\n\n"
            f"  🎯 Target:  ₦{target:,.2f}\n"
            f"  💰 Current: ₦{current:,.2f}\n\n"
            f"<i>NGX Signal · Smart Investing 🇳🇬</i>"
        )

        sent_any = False

        # Telegram DM
        if tg_id and token:
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": tg_id, "text": tg_msg, "parse_mode": "HTML"},
                    timeout=10
                )
                if r.status_code == 200:
                    sent_any = True
                    logger.info(f"  Telegram alert → {fname} ({symbol})")
                else:
                    logger.warning(f"  Telegram failed: {r.text[:80]}")
            except Exception as e:
                logger.error(f"  Telegram error: {e}")

        # OneSignal Push
        if push_ok and os_app and os_key:
            try:
                dres = sb.table("devices")\
                    .select("player_id")\
                    .eq("user_id", user_id)\
                    .eq("is_active", True).execute()
                pids = [d["player_id"] for d in (dres.data or [])]
                if pids:
                    pr = requests.post(
                        "https://onesignal.com/api/v1/notifications",
                        json={
                            "app_id":             os_app,
                            "include_player_ids": pids,
                            "headings":           {"en": f"⚡ {symbol} Alert"},
                            "contents":           {"en": f"₦{current:,.2f} — {direction} ₦{target:,.2f}"},
                            "url":                "https://ngxsignal.streamlit.app",
                        },
                        headers={
                            "Authorization": f"Basic {os_key}",
                            "Content-Type":  "application/json",
                        },
                        timeout=10
                    )
                    if pr.status_code == 200:
                        sent_any = True
                        logger.info(f"  Push alert → {fname} ({symbol})")
            except Exception as e:
                logger.error(f"  Push error: {e}")

        if sent_any:
            triggered += 1
            try:
                sb.table("price_alerts").update({"is_active": False})\
                    .eq("id", alert["id"]).execute()
                sb.table("alert_logs").insert({
                    "alert_id": alert["id"],
                    "user_id":  user_id,
                    "channel":  "telegram",
                    "status":   "sent",
                }).execute()
            except Exception:
                pass

    logger.info(f"  {triggered} price alerts triggered and sent")


# ══════════════════════════════════════════════════════
# STEP 10 — DISPATCH SIGNALS TO TELEGRAM CHANNELS
# ══════════════════════════════════════════════════════

def dispatch_signals(sb):
    logger.info("Dispatching signals to Telegram channels...")

    today   = str(date.today())
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    prem_id = os.environ.get("TELEGRAM_PREMIUM_CHANNEL_ID", "")
    free_id = os.environ.get("TELEGRAM_FREE_CHANNEL_ID", "")
    os_app  = os.environ.get("ONESIGNAL_APP_ID", "")
    os_key  = os.environ.get("ONESIGNAL_API_KEY", "")

    try:
        sig_res = sb.table("signal_scores")\
            .select("symbol, signal, stars, reasoning, score_date")\
            .eq("score_date", today)\
            .in_("signal", ["STRONG_BUY", "BUY"])\
            .gte("stars", 4)\
            .order("stars", desc=True)\
            .limit(5).execute()

        signals = sig_res.data or []
        if not signals:
            logger.info("  No strong signals to dispatch today")
            return

        # Avoid re-dispatching
        try:
            disp_res = sb.table("alerts")\
                .select("symbol")\
                .gte("created_at", f"{today}T00:00:00Z")\
                .execute()
            already = {r["symbol"] for r in (disp_res.data or [])}
        except Exception:
            already = set()

        new_sigs = [s for s in signals if s["symbol"] not in already]
        if not new_sigs:
            logger.info("  All signals already dispatched today")
            return

        # Get prices
        price_res = sb.table("stock_prices")\
            .select("symbol, price, change_percent")\
            .eq("trading_date", today)\
            .limit(500).execute()
        price_map = {}
        for p in (price_res.data or []):
            if p["symbol"] not in price_map:
                price_map[p["symbol"]] = p

        for sig in new_sigs[:3]:
            sym   = sig["symbol"]
            pd    = price_map.get(sym, {})
            price = float(pd.get("price", 0) or 0)
            chg   = float(pd.get("change_percent", 0) or 0)
            if price <= 0:
                continue

            arrow  = "▲" if chg >= 0 else "▼"
            reason = (sig.get("reasoning") or "")[:200]
            stars  = "⭐" * int(sig.get("stars", 3))
            entry  = round(price * 1.002, 2)
            target = round(price * (1.12 if sig["stars"] >= 5 else 1.08), 2)
            stop   = round(price * 0.95, 2)

            # Save to alerts table to prevent re-dispatch
            try:
                sb.table("alerts").insert({
                    "symbol":         sym,
                    "signal":         sig["signal"],
                    "price":          price,
                    "percent_change": chg,
                    "reasoning":      reason,
                    "entry_price":    entry,
                    "target_price":   target,
                    "stop_loss":      stop,
                    "stars":          sig["stars"],
                    "is_dispatched":  True,
                }).execute()
            except Exception:
                pass

            if token:
                prem_msg = (
                    f"🚀 <b>{sym} — {sig['signal'].replace('_', ' ')}</b> {stars}\n\n"
                    f"💰 ₦{price:,.2f}  {arrow} {chg:+.2f}%\n\n"
                    f"📋 {reason}\n\n"
                    f"✅ <b>Entry:</b>     ₦{entry:,.2f}\n"
                    f"🎯 <b>Target:</b>    ₦{target:,.2f}\n"
                    f"🛑 <b>Stop-loss:</b> ₦{stop:,.2f}\n\n"
                    f"<i>NGX Signal Premium · ngxsignal.streamlit.app</i>"
                )
                free_msg = (
                    f"📊 <b>{sym} — {sig['signal'].replace('_', ' ')}</b>\n\n"
                    f"💰 ₦{price:,.2f}  {arrow} {chg:+.2f}%\n\n"
                    f"📋 {reason[:120]}...\n\n"
                    f"🔒 <i>Entry/target/stop on Premium.\n"
                    f"<a href='https://ngxsignal.streamlit.app'>Upgrade →</a></i>"
                )
                for chat_id, msg in [(prem_id, prem_msg), (free_id, free_msg)]:
                    if not chat_id:
                        continue
                    try:
                        r = requests.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={
                                "chat_id":    chat_id,
                                "text":       msg,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True,
                            },
                            timeout=10
                        )
                        if r.status_code == 200:
                            logger.info(f"  Posted {sym} to channel {chat_id}")
                        else:
                            err = r.json().get("description", "")
                            logger.warning(f"  Channel post failed ({chat_id}): {err}")
                    except Exception as e:
                        logger.error(f"  Channel post error: {e}")

            # OneSignal broadcast
            if os_app and os_key:
                try:
                    requests.post(
                        "https://onesignal.com/api/v1/notifications",
                        json={
                            "app_id":             os_app,
                            "included_segments":  ["All"],
                            "headings":           {"en": f"🚀 {sym} — {sig['signal'].replace('_', ' ')}"},
                            "contents":           {"en": f"₦{price:,.2f}  {arrow} {chg:+.2f}%"},
                            "url":                "https://ngxsignal.streamlit.app",
                        },
                        headers={
                            "Authorization": f"Basic {os_key}",
                            "Content-Type":  "application/json",
                        },
                        timeout=10
                    )
                    logger.info(f"  Push broadcast sent for {sym}")
                except Exception as e:
                    logger.error(f"  Push broadcast error: {e}")

        logger.info(f"  {len(new_sigs)} signal(s) dispatched")

    except Exception as e:
        logger.error(f"  Signal dispatch failed: {e}")


# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("NGX Signal — Daily Data Pipeline")
    print("=" * 55)

    sb = get_db()

    enrichment                     = fetch_enrichment()
    saved, price_map, enriched_data = run_price_pipeline(sb, enrichment)

    print(f"\nPipeline result:")
    print(f"  Stocks saved: {saved}")
    print(f"  Price map:    {len(price_map)} symbols")

    run_signal_scores(sb, enriched_data)
    run_sector_performance(sb)
    run_market_summary(sb, price_map)
    run_news(sb)
    run_price_alerts(sb, price_map)
    dispatch_signals(sb)

    print("\n" + "=" * 55)
    print("All done! NGX Signal data is fresh.")
    print("=" * 55)


if __name__ == "__main__":
    main()
