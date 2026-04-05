"""
NGX Signal — Telegram Bot
Handles /start /signal /upgrade /myplan /help commands.
Syncs Telegram user IDs to Supabase.
Called by .github/scripts/run_telegram_bot.py
"""
import os
import logging
import requests

log = logging.getLogger("TelegramBot")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PREM_CHAT = os.environ.get("TELEGRAM_PREMIUM_CHANNEL_ID", "")
FREE_CHAT = os.environ.get("TELEGRAM_FREE_CHANNEL_ID", "")
BOT_NAME  = os.environ.get("TELEGRAM_BOT_USERNAME", "NGXSignalBot")
APP_URL   = "https://ngxsignal.streamlit.app"
PAID_PLANS= {"starter", "trader", "pro"}

BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def tg_post(method: str, data: dict) -> dict:
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN not set"}
    try:
        r = requests.post(f"{BASE}/{method}", json=data, timeout=15)
        return r.json()
    except Exception as e:
        log.error(f"Telegram API error ({method}): {e}")
        return {"ok": False, "description": str(e)}


def send(chat_id, text, keyboard=None):
    payload = {
        "chat_id":                  chat_id,
        "text":                     text,
        "parse_mode":               "HTML",
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = keyboard
    return tg_post("sendMessage", payload)


def get_db():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    return create_client(url, key)


def get_profile_by_tg_id(tg_user_id: int) -> dict:
    try:
        sb  = get_db()
        res = sb.table("telegram_users")\
            .select("telegram_user_id, profile_id, profiles(id, full_name, email, plan)")\
            .eq("telegram_user_id", tg_user_id)\
            .limit(1).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        log.error(f"DB error: {e}")
        return {}


def register_tg_user(tg_user_id: int, username: str, first_name: str):
    try:
        sb = get_db()
        sb.table("telegram_users").upsert({
            "telegram_user_id": tg_user_id,
            "username":         username or "",
            "first_name":       first_name or "",
            "is_active":        True,
        }, on_conflict="telegram_user_id").execute()
    except Exception as e:
        log.error(f"Register TG user error: {e}")


def handle_start(update: dict):
    msg     = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user    = msg.get("from", {})
    tg_id   = user.get("id")
    name    = user.get("first_name", "Investor")
    uname   = user.get("username", "")

    register_tg_user(tg_id, uname, name)

    kb = {"inline_keyboard": [
        [{"text": "📊 Open Dashboard", "url": APP_URL},
         {"text": "⭐ View Signals",   "url": f"{APP_URL}?page=signals"}],
        [{"text": "🔥 Hot Stocks",     "url": f"{APP_URL}?page=hot"},
         {"text": "💎 Upgrade Plan",   "url": f"{APP_URL}?page=settings"}],
    ]}
    send(chat_id, (
        f"👋 <b>Welcome to NGX Signal, {name}!</b>\n\n"
        f"I'll deliver Nigerian stock market signals straight to you — "
        f"BUY, HOLD, and AVOID alerts powered by AI.\n\n"
        f"📊 <b>Free plan:</b> Signals with 3-minute delay\n"
        f"⚡ <b>Premium:</b> Instant signals + entry/target/stop-loss\n\n"
        f"Use the menu below to get started."
    ), keyboard=kb)


def handle_signal(update: dict):
    msg     = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    tg_id   = msg.get("from", {}).get("id")

    rec  = get_profile_by_tg_id(tg_id)
    plan = (rec.get("profiles") or {}).get("plan", "free")

    if plan not in PAID_PLANS:
        send(chat_id, (
            "🔒 <b>Premium feature</b>\n\n"
            "On-demand signals are for Premium subscribers only.\n\n"
            f"<a href='{APP_URL}?page=settings'>Upgrade from ₦3,500/month →</a>"
        ))
        return

    try:
        sb  = get_db()
        res = sb.table("signal_scores")\
            .select("symbol, signal, reasoning, stars, score_date")\
            .order("score_date", desc=True)\
            .order("stars", desc=True)\
            .limit(3).execute()
        signals = res.data or []
    except Exception:
        signals = []

    if not signals:
        send(chat_id, "No signals available right now. Check back shortly.")
        return

    text = "⭐ <b>Latest NGX Signals</b>\n\n"
    for s in signals:
        emoji = {"STRONG_BUY":"🚀","BUY":"📈","HOLD":"⏸️",
                 "CAUTION":"⚠️","AVOID":"🔴"}.get(s.get("signal",""), "📊")
        stars = "⭐" * int(s.get("stars", 3))
        text += (
            f"{emoji} <b>{s['symbol']}</b> — {(s.get('signal','') or '').replace('_',' ')}\n"
            f"{stars}\n"
            f"<i>{(s.get('reasoning') or '')[:120]}...</i>\n\n"
        )
    text += f"<a href='{APP_URL}?page=signals'>See all signals →</a>"
    send(chat_id, text)


def handle_upgrade(update: dict):
    chat_id = update.get("message", {}).get("chat", {}).get("id")
    kb = {"inline_keyboard": [[{"text": "💎 Upgrade Now", "url": f"{APP_URL}?page=settings"}]]}
    send(chat_id, (
        "💎 <b>NGX Signal Plans</b>\n\n"
        "⭐ <b>Starter</b> — ₦3,500/month\n"
        "  • Instant push + Telegram alerts\n"
        "  • 10 watchlist stocks · Daily AI brief\n\n"
        "📊 <b>Trader</b> — ₦8,000/month\n"
        "  • Everything in Starter\n"
        "  • 30 stocks · Ask AI (30/mo) · Pidgin mode\n\n"
        "💎 <b>Pro</b> — ₦18,000/month\n"
        "  • Unlimited everything\n"
        "  • Priority alerts · PDF reports\n\n"
        "Upgrade now to receive instant signals."
    ), keyboard=kb)


def handle_myplan(update: dict):
    msg     = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    tg_id   = msg.get("from", {}).get("id")

    rec     = get_profile_by_tg_id(tg_id)
    profile = rec.get("profiles") or {}
    plan    = profile.get("plan", "free")

    if plan in PAID_PLANS:
        send(chat_id, (
            f"✅ <b>Your plan: {plan.upper()}</b>\n\n"
            f"You're receiving <b>instant signals</b> with full entry/target/stop-loss.\n\n"
            f"<a href='{APP_URL}'>Open your dashboard →</a>"
        ))
    else:
        kb = {"inline_keyboard": [[{"text": "⚡ Upgrade", "url": f"{APP_URL}?page=settings"}]]}
        send(chat_id, (
            f"📊 <b>Your plan: FREE</b>\n\n"
            f"You receive signals with a <b>3-minute delay</b>.\n\n"
            f"Upgrade to receive instant alerts with entry, target, and stop-loss."
        ), keyboard=kb)


def handle_help(update: dict):
    chat_id = update.get("message", {}).get("chat", {}).get("id")
    send(chat_id, (
        "📋 <b>NGX Signal Bot Commands</b>\n\n"
        "/start   — Welcome &amp; quick links\n"
        "/signal  — Latest signals (Premium)\n"
        "/upgrade — View premium plans\n"
        "/myplan  — Check your plan\n"
        "/help    — This menu\n\n"
        f"<a href='{APP_URL}'>Open dashboard →</a>"
    ))


HANDLERS = {
    "/start":   handle_start,
    "/signal":  handle_signal,
    "/upgrade": handle_upgrade,
    "/myplan":  handle_myplan,
    "/help":    handle_help,
}


def process_update(update: dict):
    msg  = update.get("message") or update.get("edited_message") or {}
    text = msg.get("text", "")
    if not text.startswith("/"):
        return
    cmd = text.split()[0].lower().split("@")[0]
    handler = HANDLERS.get(cmd)
    if handler:
        try:
            handler(update)
        except Exception as e:
            log.error(f"Handler error ({cmd}): {e}")
