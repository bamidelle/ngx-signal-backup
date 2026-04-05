"""
NGX Signal — Hardened WhatsApp Sender
======================================
Features:
- Phone number normalization (handles +234, 0234, 07xxx, 234xxx formats)
- Daily briefs for paid subscribers (Starter, Trader, Pro)
- Weekly market digest for ALL users including free
- Price alert delivery
- Detailed error logging
- Test mode support
"""

import os
import sys
import requests
import logging
from datetime import date, datetime, timedelta
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("WhatsAppSender")


# ── SUPABASE ─────────────────────────────────────────
def get_db():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return create_client(url, key)


# ── PHONE NORMALISATION ───────────────────────────────
def normalize_phone(raw: str) -> str:
    """
    Convert any Nigerian phone format to E.164 without the + sign.
    WhatsApp API requires: 2347061002488 (no + prefix)

    Handles:
      +2347061002488  →  2347061002488
      2347061002488   →  2347061002488
      07061002488     →  2347061002488
      7061002488      →  2347061002488
      234 706 100 2488 → 2347061002488
      +234-706-100-2488 → 2347061002488
    """
    if not raw:
        return ""

    # Strip everything except digits
    digits = "".join(c for c in str(raw) if c.isdigit())

    if not digits:
        return ""

    # Already has country code 234
    if digits.startswith("234") and len(digits) == 13:
        return digits

    # Starts with 0 (local format: 07061002488)
    if digits.startswith("0") and len(digits) == 11:
        return "234" + digits[1:]

    # Starts with 234 but wrong length — still try
    if digits.startswith("234") and len(digits) > 10:
        return digits

    # 10 digits starting with 7/8/9 (mobile without leading 0)
    if len(digits) == 10 and digits[0] in "789":
        return "234" + digits

    # If already 13 digits, return as-is
    if len(digits) == 13:
        return digits

    # Last resort — prepend 234
    return "234" + digits


def is_valid_phone(phone: str) -> bool:
    """Check if normalised phone looks valid."""
    norm = normalize_phone(phone)
    return len(norm) == 13 and norm.startswith("234")


# ── WHATSAPP API ─────────────────────────────────────
def send_whatsapp_message(
    phone: str,
    message: str,
    token: str,
    phone_id: str,
) -> tuple:
    """
    Send a WhatsApp message.
    Returns (success: bool, error_msg: str)
    """
    norm = normalize_phone(phone)
    if not is_valid_phone(norm):
        return False, f"Invalid phone number: {phone} → {norm}"

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": norm,
        "type": "text",
        "text": {"body": message, "preview_url": False},
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        data = res.json()

        if res.status_code == 200 and "messages" in data:
            msg_id = data["messages"][0].get("id", "unknown")
            logger.info(f"✅ Sent to {norm} — msg_id: {msg_id}")
            return True, ""
        else:
            error = data.get("error", {})
            err_msg = error.get("message", str(data))
            err_code = error.get("code", res.status_code)
            logger.error(f"❌ Failed {norm} — [{err_code}] {err_msg}")
            return False, f"[{err_code}] {err_msg}"

    except Exception as e:
        logger.error(f"❌ Exception sending to {norm}: {e}")
        return False, str(e)


# ── FORMAT MESSAGES ──────────────────────────────────
def format_morning_brief(brief_body: str, brief_date: str,
                          name: str, plan: str) -> str:
    plan_emoji = {"pro": "💎", "trader": "📊", "starter": "⭐"}.get(plan, "📈")
    return (
        f"📈 *NGX Signal Morning Brief*\n"
        f"{plan_emoji} {brief_date}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Good morning, {name}! 👋\n\n"
        f"{brief_body[:1500]}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"_NGX Signal — Smart Investing 🇳🇬_\n"
        f"_Reply STOP to unsubscribe_"
    )


def format_weekly_digest(
    gainers: list,
    losers: list,
    asi: float,
    asi_chg: float,
    total_stocks: int,
    name: str,
    plan: str,
    week_str: str,
) -> str:
    """Format the weekly market digest for all users."""
    asi_arrow = "▲" if asi_chg >= 0 else "▼"
    plan_label = plan.upper() if plan != "free" else "FREE"

    top_g = "\n".join(
        f"  • {s['symbol']}: +{s.get('change_percent', 0):.2f}%"
        for s in gainers[:5]
    ) or "  No data"

    top_l = "\n".join(
        f"  • {s['symbol']}: {s.get('change_percent', 0):.2f}%"
        for s in losers[:5]
    ) or "  No data"

    upgrade_note = (
        "\n💡 *Upgrade to get daily AI briefs & price alerts!*\n"
        "Starter plan from ₦3,500/month."
    ) if plan == "free" else ""

    return (
        f"📊 *NGX Signal — Weekly Market Digest*\n"
        f"🗓️ Week of {week_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hello {name}! Here's your weekly NGX summary.\n\n"
        f"*📈 All-Share Index*\n"
        f"  {asi_arrow} {asi:,.2f} ({asi_chg:+.2f}% this week)\n"
        f"  {total_stocks} stocks tracked\n\n"
        f"*🔥 Top Gainers This Week*\n{top_g}\n\n"
        f"*📉 Top Losers This Week*\n{top_l}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{upgrade_note}"
        f"_NGX Signal — Smart Investing 🇳🇬_\n"
        f"_Your plan: {plan_label}_"
    )


def format_price_alert(
    symbol: str,
    current_price: float,
    target_price: float,
    alert_type: str,
    name: str,
) -> str:
    direction = "risen above" if alert_type == "above" else "fallen below"
    emoji = "🚀" if alert_type == "above" else "⚠️"
    return (
        f"{emoji} *NGX Signal Price Alert*\n\n"
        f"Hi {name}!\n\n"
        f"*{symbol}* has {direction} your target:\n\n"
        f"  🎯 Target: ₦{target_price:,.2f}\n"
        f"  💰 Current: ₦{current_price:,.2f}\n\n"
        f"_NGX Signal — Smart Investing 🇳🇬_"
    )


# ── SEND MORNING BRIEFS ───────────────────────────────
def send_morning_briefs(sb, token: str, phone_id: str) -> dict:
    """Send morning AI brief to all paid subscribers with WhatsApp enabled."""
    logger.info("📤 Sending WhatsApp morning briefs...")
    today = str(date.today())

    # Get today's brief
    brief_res = sb.table("ai_briefs")\
        .select("body, brief_date, language")\
        .eq("brief_type", "morning")\
        .order("brief_date", desc=True)\
        .limit(2).execute()

    briefs = {b["language"]: b for b in (brief_res.data or [])}
    brief_en = briefs.get("en", {})
    brief_pg = briefs.get("pg", {})

    if not brief_en and not brief_pg:
        logger.warning("⚠️  No brief found — skipping morning send")
        return {"sent": 0, "failed": 0}

    # Get all paid users with WhatsApp enabled
    users_res = sb.table("profiles")\
        .select("id, full_name, phone_whatsapp, plan, brief_language, whatsapp_enabled")\
        .in_("plan", ["starter", "trader", "pro"])\
        .eq("whatsapp_enabled", True)\
        .execute()

    users = users_res.data or []
    logger.info(f"   → {len(users)} paid users with WhatsApp enabled")

    sent = failed = 0

    for user in users:
        phone_raw = user.get("phone_whatsapp", "")
        if not phone_raw:
            logger.warning(f"   ⚠️  {user.get('full_name','?')} — no phone number")
            continue

        if not is_valid_phone(phone_raw):
            logger.warning(
                f"   ⚠️  {user.get('full_name','?')} — invalid phone: {phone_raw}"
            )
            continue

        name = (user.get("full_name") or "Investor").split()[0]
        lang = user.get("brief_language", "en") or "en"

        # Pick correct language brief
        brief = briefs.get(lang) or brief_en or brief_pg
        if not brief:
            continue

        message = format_morning_brief(
            brief.get("body", ""),
            brief.get("brief_date", today),
            name,
            user.get("plan", "free"),
        )

        success, err = send_whatsapp_message(
            phone_raw, message, token, phone_id
        )
        if success:
            sent += 1
        else:
            failed += 1
            logger.error(f"   ❌ {name} ({normalize_phone(phone_raw)}): {err}")

    logger.info(f"   → Morning briefs: {sent} sent | {failed} failed")
    return {"sent": sent, "failed": failed}


# ── SEND WEEKLY DIGEST ────────────────────────────────
def send_weekly_digest(sb, token: str, phone_id: str) -> dict:
    """
    Send weekly market digest to ALL users with a phone number.
    Free users get this to encourage re-engagement.
    Paid users get it in addition to daily briefs.
    """
    logger.info("📤 Sending weekly market digest to ALL users...")
    today     = date.today()
    week_str  = today.strftime("%d %B %Y")

    # Get market summary
    summary_res = sb.table("market_summary")\
        .select("asi_index, asi_change_percent, gainers_count, losers_count")\
        .order("trading_date", desc=True)\
        .limit(1).execute()
    summary = summary_res.data[0] if summary_res.data else {}

    asi     = float(summary.get("asi_index", 201156.86) or 201156.86)
    asi_chg = float(summary.get("asi_change_percent", 0) or 0)
    total   = int(summary.get("gainers_count", 0) or 0) + \
              int(summary.get("losers_count",  0) or 0)

    # Get top gainers and losers from latest prices
    latest_res = sb.table("stock_prices")\
        .select("trading_date")\
        .order("trading_date", desc=True)\
        .limit(1).execute()
    latest_date = latest_res.data[0]["trading_date"] \
        if latest_res.data else str(today)

    prices_res = sb.table("stock_prices")\
        .select("symbol, price, change_percent")\
        .eq("trading_date", latest_date)\
        .limit(500).execute()

    all_prices = prices_res.data or []
    seen_p = set()
    unique_p = []
    for p in all_prices:
        if p["symbol"] not in seen_p:
            seen_p.add(p["symbol"])
            unique_p.append(p)

    gainers = sorted(
        [p for p in unique_p if float(p.get("change_percent") or 0) > 0],
        key=lambda x: float(x.get("change_percent", 0) or 0),
        reverse=True
    )[:5]

    losers = sorted(
        [p for p in unique_p if float(p.get("change_percent") or 0) < 0],
        key=lambda x: float(x.get("change_percent", 0) or 0)
    )[:5]

    # Get ALL users with phone numbers
    users_res = sb.table("profiles")\
        .select("id, full_name, phone_whatsapp, plan, whatsapp_enabled")\
        .not_.is_("phone_whatsapp", "null")\
        .execute()

    all_users = [
        u for u in (users_res.data or [])
        if u.get("phone_whatsapp")
    ]
    logger.info(f"   → {len(all_users)} users with phone numbers")

    sent = failed = skipped = 0

    for user in all_users:
        phone_raw = user.get("phone_whatsapp", "")
        plan      = user.get("plan", "free")

        # For free users, only send if they have a phone (even if WA not enabled)
        # For paid, always send
        if plan == "free" and not is_valid_phone(phone_raw):
            skipped += 1
            continue

        if not is_valid_phone(phone_raw):
            skipped += 1
            continue

        name    = (user.get("full_name") or "Investor").split()[0]
        message = format_weekly_digest(
            gainers, losers, asi, asi_chg,
            len(unique_p), name, plan, week_str
        )

        success, err = send_whatsapp_message(
            phone_raw, message, token, phone_id
        )
        if success:
            sent += 1
        else:
            failed += 1
            logger.error(
                f"   ❌ {name} ({normalize_phone(phone_raw)}): {err}"
            )

    logger.info(
        f"   → Weekly digest: {sent} sent | {failed} failed | {skipped} skipped"
    )
    return {"sent": sent, "failed": failed, "skipped": skipped}


# ── SEND PRICE ALERTS ─────────────────────────────────
def send_price_alerts(sb, token: str, phone_id: str) -> dict:
    """Check and fire active price alerts."""
    logger.info("⚡ Checking price alerts...")

    # Get all active alerts with user profile
    alerts_res = sb.table("price_alerts")\
        .select("id, user_id, symbol, target_price, alert_type")\
        .eq("is_active", True)\
        .execute()

    alerts = alerts_res.data or []
    logger.info(f"   → {len(alerts)} active alerts")

    if not alerts:
        return {"triggered": 0}

    # Get latest prices
    latest_res = sb.table("stock_prices")\
        .select("trading_date")\
        .order("trading_date", desc=True)\
        .limit(1).execute()
    latest_date = latest_res.data[0]["trading_date"] \
        if latest_res.data else str(date.today())

    prices_res = sb.table("stock_prices")\
        .select("symbol, price")\
        .eq("trading_date", latest_date)\
        .limit(500).execute()

    price_map = {}
    for p in (prices_res.data or []):
        if p["symbol"] not in price_map:
            price_map[p["symbol"]] = float(p["price"])

    logger.info(f"   → {len(price_map)} stocks in price map")
    triggered = 0

    for alert in alerts:
        symbol     = alert["symbol"]
        target     = float(alert["target_price"])
        alert_type = alert.get("alert_type", "above")
        user_id    = alert["user_id"]

        current = price_map.get(symbol)
        if not current:
            continue

        fired = (
            alert_type == "above" and current >= target or
            alert_type == "below" and current <= target
        )
        if not fired:
            continue

        # Get user profile
        profile_res = sb.table("profiles")\
            .select("full_name, phone_whatsapp, plan")\
            .eq("id", user_id)\
            .limit(1).execute()

        if not profile_res.data:
            continue

        profile   = profile_res.data[0]
        phone_raw = profile.get("phone_whatsapp", "")
        name      = (profile.get("full_name") or "Investor").split()[0]

        if not is_valid_phone(phone_raw):
            logger.warning(
                f"   ⚠️  Alert for {symbol}: invalid phone {phone_raw}"
            )
            continue

        message = format_price_alert(
            symbol, current, target, alert_type, name
        )

        success, err = send_whatsapp_message(
            phone_raw, message, token, phone_id
        )

        if success:
            triggered += 1
            # Deactivate alert
            sb.table("price_alerts")\
                .update({"is_active": False})\
                .eq("id", alert["id"])\
                .execute()

            # Log (handle missing columns gracefully)
            try:
                sb.table("alert_logs").insert({
                    "alert_id": alert["id"],
                    "message":  message,
                    "status":   "sent",
                }).execute()
            except Exception:
                pass  # alert_logs schema may vary

    logger.info(f"   → {triggered} price alerts triggered and sent")
    return {"triggered": triggered}


# ── SEND TEST MESSAGE ─────────────────────────────────
def send_test_alert(sb, token: str, phone_id: str,
                    phone: str = None) -> bool:
    """
    Send a test WhatsApp message to verify credentials.
    Uses the admin phone if none provided.
    """
    if not phone:
        # Fetch from DB
        admin_res = sb.table("profiles")\
            .select("phone_whatsapp, full_name")\
            .eq("plan", "pro")\
            .limit(1).execute()
        if admin_res.data:
            phone = admin_res.data[0].get("phone_whatsapp", "")
            name  = (admin_res.data[0].get("full_name") or "Admin").split()[0]
        else:
            phone = "2347061002488"
            name  = "Admin"
    else:
        name = "Admin"

    norm = normalize_phone(phone)
    logger.info(f"🧪 Sending test message to {norm}...")

    message = (
        f"✅ *NGX Signal — Test Message*\n\n"
        f"Hi {name}! 👋\n\n"
        f"Your WhatsApp integration is working correctly.\n\n"
        f"📊 *What you'll receive:*\n"
        f"  • 📈 Daily AI market brief (paid plans)\n"
        f"  • ⚡ Price alerts when your targets are hit\n"
        f"  • 📊 Weekly market digest (all users)\n\n"
        f"_Sent: {datetime.now().strftime('%d %b %Y %H:%M WAT')}_\n"
        f"_NGX Signal — Smart Investing 🇳🇬_"
    )

    success, err = send_whatsapp_message(phone, message, token, phone_id)
    if success:
        logger.info(f"✅ Test message delivered to {norm}")
    else:
        logger.error(f"❌ Test failed: {err}")

        # Diagnose common errors
        if "OAuthException" in err or "API access blocked" in err:
            logger.error(
                "🔑 TOKEN ISSUE: Your WhatsApp token is blocked or expired.\n"
                "   Fix: Go to Meta Business Suite → Settings → System Users\n"
                "   → Click your system user → Generate token\n"
                "   → Select your WhatsApp app → Set token never expires\n"
                "   → Update WHATSAPP_TOKEN in GitHub secrets"
            )
        elif "Invalid phone" in err or "not a valid" in err.lower():
            logger.error(
                f"📱 PHONE ISSUE: {phone} → normalised to {norm}\n"
                f"   Ensure the number is registered on WhatsApp\n"
                f"   and has agreed to receive messages from your app."
            )

    return success


# ── MAIN ─────────────────────────────────────────────
def main():
    logger.info("=" * 50)
    logger.info("WhatsApp sender starting...")
    logger.info("=" * 50)

    token    = os.environ.get("WHATSAPP_TOKEN", "")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")
    mode     = os.environ.get("WA_MODE", "morning")  # morning|weekly|test|alerts

    if not token or not phone_id:
        logger.error(
            "❌ WHATSAPP_TOKEN or WHATSAPP_PHONE_ID not set.\n"
            "   Add both to GitHub Actions secrets and Streamlit secrets."
        )
        sys.exit(1)

    sb = get_db()

    if mode == "test":
        test_phone = os.environ.get("TEST_PHONE", "")
        send_test_alert(sb, token, phone_id, test_phone or None)

    elif mode == "weekly":
        send_weekly_digest(sb, token, phone_id)

    elif mode == "alerts":
        send_price_alerts(sb, token, phone_id)

    else:
        # Default: morning brief + price alerts
        logger.info("📤 Sending morning briefs...")
        send_morning_briefs(sb, token, phone_id)

        logger.info("⚡ Checking price alerts...")
        send_price_alerts(sb, token, phone_id)

    logger.info("✅ WhatsApp sender complete!")


if __name__ == "__main__":
    main()
