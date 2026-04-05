"""
NGX Signal — Multi-Channel Notification Dispatcher
====================================================
Channels: Push (OneSignal) · Telegram · Email (Brevo)
Tiers:    Free (delayed 3min) · Paid (instant)
"""

import os
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("NGXDispatcher")

# ── Credentials ───────────────────────────────────────
SUPABASE_URL        = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY        = os.environ.get("SUPABASE_SERVICE_KEY", "")
ONESIGNAL_APP_ID    = os.environ.get("ONESIGNAL_APP_ID", "")
ONESIGNAL_API_KEY   = os.environ.get("ONESIGNAL_API_KEY", "")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_FREE_ID    = os.environ.get("TELEGRAM_FREE_CHANNEL_ID", "")   # e.g. @ngxsignal_free
TELEGRAM_PREM_ID    = os.environ.get("TELEGRAM_PREMIUM_CHANNEL_ID", "") # e.g. -100xxxxxxxxx
BREVO_API_KEY       = os.environ.get("BREVO_API_KEY", "")
BREVO_FROM_EMAIL    = os.environ.get("BREVO_FROM_EMAIL", "signals@ngxsignal.com")
BREVO_FROM_NAME     = "NGX Signal"

PAID_PLANS          = {"starter", "trader", "pro"}
FREE_DELAY_SECONDS  = 180   # 3-minute delay for free tier


def get_db():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ══════════════════════════════════════════════════════
# SIGNAL FORMATTER
# ══════════════════════════════════════════════════════

def format_signal(signal: dict, tier: str = "free") -> dict:
    """
    Format a signal dict into multi-channel message strings.
    Returns: {push_title, push_body, telegram_html, email_subject, email_html}
    """
    sym     = signal.get("symbol", "")
    price   = float(signal.get("price", 0) or 0)
    chg     = float(signal.get("percent_change", 0) or 0)
    sig     = signal.get("signal", "HOLD").upper().replace(" ", "_")
    reason  = signal.get("reasoning", "")[:200]
    entry   = signal.get("entry_price")
    target  = signal.get("target_price")
    stop    = signal.get("stop_loss")

    # Signal emoji map
    emoji = {
        "STRONG_BUY":     "🚀",
        "BUY":            "📈",
        "BREAKOUT_WATCH": "👀",
        "HOLD":           "⏸️",
        "CAUTION":        "⚠️",
        "AVOID":          "🔴",
    }.get(sig, "📊")

    sig_label = sig.replace("_", " ")
    arrow     = "▲" if chg >= 0 else "▼"
    delay_tag = "" if tier in PAID_PLANS else " [DELAYED]"

    # ── Push notification ──────────────────────────────
    push_title = f"{emoji} {sym} — {sig_label}{delay_tag}"
    push_body  = f"₦{price:,.2f}  {arrow} {abs(chg):.2f}%"
    if entry and target:
        push_body += f"  ·  Entry ₦{entry:,.2f}  Target ₦{target:,.2f}"

    # ── Telegram HTML ──────────────────────────────────
    action_lines = ""
    if tier in PAID_PLANS and entry and target and stop:
        action_lines = (
            f"\n✅ <b>Entry:</b> ₦{entry:,.2f}"
            f"\n🎯 <b>Target:</b> ₦{target:,.2f}"
            f"\n🛑 <b>Stop-loss:</b> ₦{stop:,.2f}"
        )
    elif tier not in PAID_PLANS:
        action_lines = (
            "\n\n🔒 <i>Entry, target and stop-loss available on"
            " <a href='https://ngxsignal.streamlit.app'>Premium plans</a></i>"
        )

    delay_note = (
        "\n\n⏱ <i>You received this 3 minutes after premium users."
        " <a href='https://ngxsignal.streamlit.app'>Upgrade for instant signals →</a></i>"
    ) if tier not in PAID_PLANS else ""

    telegram_html = (
        f"{emoji} <b>{sym} — {sig_label}</b>\n"
        f"💰 ₦{price:,.2f}  {arrow} {abs(chg):.2f}%\n\n"
        f"📋 {reason}"
        f"{action_lines}"
        f"{delay_note}\n\n"
        f"<i>NGX Signal · ngxsignal.streamlit.app</i>"
    )

    # ── Email ──────────────────────────────────────────
    email_subject = f"{emoji} {sym} Signal: {sig_label} — ₦{price:,.2f}"

    action_html = ""
    if tier in PAID_PLANS and entry and target and stop:
        action_html = f"""
        <table style="width:100%;border-collapse:separate;border-spacing:0 6px;margin:16px 0;">
          <tr><td style="background:#001A00;border:1px solid #003D00;border-radius:6px;padding:10px 14px;width:33%;">
            <div style="font-size:10px;color:#4B5563;text-transform:uppercase;margin-bottom:3px;">Entry</div>
            <div style="font-size:18px;font-weight:600;color:#22C55E;font-family:monospace;">₦{entry:,.2f}</div>
          </td>
          <td style="background:#001A1A;border:1px solid #003D3D;border-radius:6px;padding:10px 14px;width:33%;">
            <div style="font-size:10px;color:#4B5563;text-transform:uppercase;margin-bottom:3px;">Target</div>
            <div style="font-size:18px;font-weight:600;color:#22D3EE;font-family:monospace;">₦{target:,.2f}</div>
          </td>
          <td style="background:#1A0000;border:1px solid #3D0000;border-radius:6px;padding:10px 14px;width:33%;">
            <div style="font-size:10px;color:#4B5563;text-transform:uppercase;margin-bottom:3px;">Stop-loss</div>
            <div style="font-size:18px;font-weight:600;color:#EF4444;font-family:monospace;">₦{stop:,.2f}</div>
          </td></tr>
        </table>"""

    upgrade_cta = "" if tier in PAID_PLANS else """
        <div style="background:#1A1600;border:1px solid #3D2E00;border-radius:10px;
                    padding:16px 20px;margin-top:20px;text-align:center;">
          <div style="font-size:16px;font-weight:700;color:#F0A500;margin-bottom:6px;">
            ⚡ You missed the entry window by 3 minutes
          </div>
          <div style="font-size:13px;color:#6B7280;margin-bottom:14px;">
            Premium users received this signal instantly with full entry/target/stop details.
          </div>
          <a href="https://ngxsignal.streamlit.app?page=settings"
             style="display:inline-block;background:#F0A500;color:#0A0C0F;font-weight:700;
                    font-size:14px;padding:10px 24px;border-radius:999px;text-decoration:none;">
            Upgrade Now — from ₦3,500/mo →
          </a>
        </div>"""

    email_html = f"""
    <!DOCTYPE html><html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>{email_subject}</title></head>
    <body style="margin:0;padding:0;background:#0A0C0F;font-family:Inter,-apple-system,sans-serif;">
      <div style="max-width:560px;margin:0 auto;padding:24px 16px;">
        <div style="background:#10131A;border:1px solid #1E2229;border-radius:12px;
                    padding:24px;margin-bottom:16px;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
            <div style="font-family:monospace;font-size:28px;font-weight:700;color:#E8E2D4;">
              {sym}
            </div>
            <span style="background:{'rgba(34,197,94,0.12)' if 'BUY' in sig else 'rgba(215,119,6,0.12)'};
                         color:{'#22C55E' if 'BUY' in sig else '#D97706'};
                         font-size:11px;font-weight:700;padding:4px 12px;border-radius:999px;
                         text-transform:uppercase;letter-spacing:0.07em;">
              {sig_label}
            </span>
          </div>
          <div style="font-size:32px;font-weight:500;color:#E8E2D4;font-family:monospace;
                      margin-bottom:4px;">
            ₦{price:,.2f}
          </div>
          <div style="font-size:15px;font-weight:500;
                      color:{'#22C55E' if chg >= 0 else '#EF4444'};margin-bottom:20px;">
            {arrow} {abs(chg):.2f}% today
          </div>
          <div style="font-size:13px;color:#9CA3AF;line-height:1.7;
                      padding:14px;background:#0A0C0F;border-radius:8px;
                      border-left:3px solid {'#22C55E' if 'BUY' in sig else '#D97706'};">
            {reason}
          </div>
          {action_html}
        </div>
        {upgrade_cta}
        <div style="font-size:10px;color:#374151;text-align:center;margin-top:16px;">
          NGX Signal · Educational purposes only · Not financial advice<br>
          <a href="{{{{unsubscribe}}}}" style="color:#374151;">Unsubscribe</a>
        </div>
      </div>
    </body></html>
    """

    return {
        "push_title":      push_title,
        "push_body":       push_body,
        "telegram_html":   telegram_html,
        "email_subject":   email_subject,
        "email_html":      email_html,
    }


# ══════════════════════════════════════════════════════
# ONESIGNAL PUSH
# ══════════════════════════════════════════════════════

def send_push_onesignal(
    title: str,
    body: str,
    player_ids: list,
    url: str = "https://ngxsignal.streamlit.app",
    data: dict = None,
    delay_seconds: int = 0,
) -> dict:
    """Send OneSignal push to a list of player_ids."""
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        log.warning("OneSignal not configured — skipping push")
        return {"success": False, "error": "not_configured"}
    if not player_ids:
        return {"success": False, "error": "no_recipients"}

    payload = {
        "app_id":           ONESIGNAL_APP_ID,
        "include_player_ids": player_ids,
        "headings":         {"en": title},
        "contents":         {"en": body},
        "url":              url,
        "web_push_topic":   "ngx_signal",
        "priority":         10,
        "data":             data or {},
    }
    if delay_seconds > 0:
        send_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        payload["send_after"] = send_at.strftime("%Y-%m-%d %H:%M:%S GMT+0000")

    headers = {
        "Authorization": f"Basic {ONESIGNAL_API_KEY}",
        "Content-Type":  "application/json",
    }
    for attempt in range(3):
        try:
            res = requests.post(
                "https://onesignal.com/api/v1/notifications",
                json=payload, headers=headers, timeout=15
            )
            data_res = res.json()
            if res.status_code == 200 and data_res.get("id"):
                log.info(f"✅ Push sent: {data_res['id']} to {len(player_ids)} devices")
                return {"success": True, "notification_id": data_res["id"]}
            log.warning(f"Push attempt {attempt+1}: {data_res}")
        except Exception as e:
            log.error(f"Push error attempt {attempt+1}: {e}")
        time.sleep(2 ** attempt)

    return {"success": False, "error": "all_retries_failed"}


def send_push_segment(
    title: str,
    body: str,
    segment: str,
    url: str = "https://ngxsignal.streamlit.app",
) -> dict:
    """Send OneSignal push to a named segment (e.g. 'Premium Users')."""
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        return {"success": False, "error": "not_configured"}

    payload = {
        "app_id":   ONESIGNAL_APP_ID,
        "included_segments": [segment],
        "headings": {"en": title},
        "contents": {"en": body},
        "url":      url,
    }
    headers = {
        "Authorization": f"Basic {ONESIGNAL_API_KEY}",
        "Content-Type":  "application/json",
    }
    try:
        res = requests.post(
            "https://onesignal.com/api/v1/notifications",
            json=payload, headers=headers, timeout=15
        )
        return res.json()
    except Exception as e:
        log.error(f"Segment push error: {e}")
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════
# TELEGRAM
# ══════════════════════════════════════════════════════

def send_telegram_message(
    chat_id: str,
    html_text: str,
    disable_preview: bool = True,
) -> bool:
    """Send an HTML message to a Telegram chat/channel."""
    if not TELEGRAM_BOT_TOKEN:
        log.warning("Telegram token not set — skipping")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":                  chat_id,
        "text":                     html_text,
        "parse_mode":               "HTML",
        "disable_web_page_preview": disable_preview,
    }
    for attempt in range(3):
        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                log.info(f"✅ Telegram sent to {chat_id}")
                return True
            log.warning(f"Telegram attempt {attempt+1}: {res.text[:200]}")
        except Exception as e:
            log.error(f"Telegram error: {e}")
        time.sleep(2 ** attempt)
    return False


def create_telegram_invite_link(
    channel_id: str,
    name: str,
    expire_hours: int = 48,
    member_limit: int = 1,
) -> Optional[str]:
    """Generate a one-time Telegram invite link for a premium user."""
    if not TELEGRAM_BOT_TOKEN:
        return None
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createChatInviteLink"
    payload = {
        "chat_id":     channel_id,
        "name":        f"NGX Premium — {name}",
        "expire_date": int((datetime.utcnow() + timedelta(hours=expire_hours)).timestamp()),
        "member_limit": member_limit,
        "creates_join_request": False,
    }
    try:
        res  = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if data.get("ok"):
            link = data["result"]["invite_link"]
            log.info(f"✅ Telegram invite link created: {link}")
            return link
    except Exception as e:
        log.error(f"Invite link error: {e}")
    return None


# ══════════════════════════════════════════════════════
# BREVO EMAIL
# ══════════════════════════════════════════════════════

def send_email_brevo(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
    tags: list = None,
) -> bool:
    """Send a transactional email via Brevo API."""
    if not BREVO_API_KEY:
        log.warning("Brevo key not set — skipping email")
        return False

    payload = {
        "sender":      {"email": BREVO_FROM_EMAIL, "name": BREVO_FROM_NAME},
        "to":          [{"email": to_email, "name": to_name}],
        "subject":     subject,
        "htmlContent": html_content,
        "tags":        tags or ["signal_alert"],
    }
    headers = {
        "api-key":      BREVO_API_KEY,
        "Content-Type": "application/json",
    }
    for attempt in range(3):
        try:
            res = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                json=payload, headers=headers, timeout=15
            )
            if res.status_code in (200, 201):
                log.info(f"✅ Email sent to {to_email}")
                return True
            log.warning(f"Brevo attempt {attempt+1}: {res.text[:200]}")
        except Exception as e:
            log.error(f"Email error: {e}")
        time.sleep(2 ** attempt)
    return False


def send_weekly_digest_email(
    to_email: str,
    to_name: str,
    top_gainers: list,
    top_losers: list,
    asi: float,
    asi_chg: float,
    total_stocks: int,
    plan: str,
) -> bool:
    """Send weekly digest email."""
    week_str    = datetime.utcnow().strftime("%d %B %Y")
    asi_arrow   = "▲" if asi_chg >= 0 else "▼"
    plan_label  = plan.upper()
    is_free     = plan not in PAID_PLANS

    gainers_rows = "".join(
        f"<tr><td style='padding:8px 0;font-family:monospace;font-size:14px;'>{s['symbol']}</td>"
        f"<td style='padding:8px 0;font-family:monospace;text-align:right;color:#22C55E;'>"
        f"+{float(s.get('change_percent',0)):.2f}%</td></tr>"
        for s in top_gainers[:5]
    ) or "<tr><td colspan='2' style='color:#4B5563;padding:8px 0;'>No data</td></tr>"

    losers_rows = "".join(
        f"<tr><td style='padding:8px 0;font-family:monospace;font-size:14px;'>{s['symbol']}</td>"
        f"<td style='padding:8px 0;font-family:monospace;text-align:right;color:#EF4444;'>"
        f"{float(s.get('change_percent',0)):.2f}%</td></tr>"
        for s in top_losers[:5]
    ) or "<tr><td colspan='2' style='color:#4B5563;padding:8px 0;'>No data</td></tr>"

    upgrade_section = f"""
    <div style="background:#1A1600;border:1px solid #3D2E00;border-radius:12px;
                padding:20px;margin-top:24px;text-align:center;">
      <div style="font-size:18px;font-weight:700;color:#F0A500;margin-bottom:8px;">
        ⚡ You're on the Free plan
      </div>
      <div style="font-size:13px;color:#6B7280;margin-bottom:16px;line-height:1.6;">
        This week, premium subscribers received <strong style="color:#E8E2D4;">
        instant signal alerts</strong> with full entry/target/stop levels — 3 minutes
        before you. Upgrade to never miss another trade.
      </div>
      <a href="https://ngxsignal.streamlit.app?page=settings"
         style="display:inline-block;background:#F0A500;color:#0A0C0F;font-weight:700;
                font-size:14px;padding:12px 28px;border-radius:999px;text-decoration:none;">
        Start 7-Day Free Trial →
      </a>
    </div>""" if is_free else ""

    html = f"""
    <!DOCTYPE html><html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#0A0C0F;font-family:Inter,-apple-system,sans-serif;">
      <div style="max-width:560px;margin:0 auto;padding:24px 16px;">
        <div style="margin-bottom:16px;">
          <span style="font-family:monospace;font-size:20px;font-weight:800;color:#fff;">NGX</span>
          <span style="font-family:monospace;font-size:20px;font-weight:800;color:#F0A500;">Signal</span>
          <span style="font-size:11px;color:#4B5563;margin-left:8px;text-transform:uppercase;
                       letter-spacing:0.1em;">Weekly Digest · {week_str}</span>
        </div>
        <div style="background:#10131A;border:1px solid #1E2229;border-radius:12px;padding:20px 24px;">
          <h2 style="font-size:15px;color:#E8E2D4;margin:0 0 16px 0;">
            Hi {to_name.split()[0]}! Here's your weekly NGX summary.
          </h2>
          <div style="background:#0A0C0F;border-radius:8px;padding:14px 16px;margin-bottom:16px;">
            <div style="font-size:10px;color:#4B5563;text-transform:uppercase;
                        letter-spacing:0.08em;margin-bottom:6px;">NGX All-Share Index</div>
            <div style="font-size:28px;font-weight:500;color:#E8E2D4;font-family:monospace;">
              {asi:,.2f}
            </div>
            <div style="font-size:14px;color:{'#22C55E' if asi_chg>=0 else '#EF4444'};font-family:monospace;">
              {asi_arrow} {abs(asi_chg):.2f}% this week · {total_stocks} stocks tracked
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div>
              <div style="font-size:10px;color:#4B5563;text-transform:uppercase;
                          letter-spacing:0.08em;margin-bottom:8px;">Top Gainers</div>
              <table style="width:100%;border-collapse:collapse;">{gainers_rows}</table>
            </div>
            <div>
              <div style="font-size:10px;color:#4B5563;text-transform:uppercase;
                          letter-spacing:0.08em;margin-bottom:8px;">Top Losers</div>
              <table style="width:100%;border-collapse:collapse;">{losers_rows}</table>
            </div>
          </div>
        </div>
        {upgrade_section}
        <div style="font-size:10px;color:#374151;text-align:center;margin-top:16px;">
          NGX Signal · Educational purposes only · Not financial advice<br>
          Your plan: {plan_label} ·
          <a href="{{{{unsubscribe}}}}" style="color:#374151;">Unsubscribe</a>
        </div>
      </div>
    </body></html>"""

    return send_email_brevo(
        to_email, to_name,
        f"📊 NGX Signal Weekly Digest — {week_str}",
        html, tags=["weekly_digest"]
    )


# ══════════════════════════════════════════════════════
# ALERT DISPATCHER — MAIN ENGINE
# ══════════════════════════════════════════════════════

class AlertDispatcher:
    """
    Core alert dispatch engine.
    Handles tier-based routing, delay logic, retry, and logging.
    """

    def __init__(self):
        self.sb = get_db()

    def _get_users_for_signal(self, signal: dict) -> list:
        """Fetch all active users with their devices and notification prefs."""
        try:
            res = self.sb.table("profiles")\
                .select("id, full_name, email, plan, email_alerts_enabled, "
                        "push_alerts_enabled, telegram_user_id")\
                .neq("plan", None)\
                .execute()
            return res.data or []
        except Exception as e:
            log.error(f"Failed to fetch users: {e}")
            return []

    def _get_push_tokens(self, user_ids: list) -> dict:
        """Return {user_id: [player_id, ...]} from devices table."""
        if not user_ids:
            return {}
        try:
            res = self.sb.table("devices")\
                .select("user_id, player_id")\
                .in_("user_id", user_ids)\
                .eq("is_active", True)\
                .execute()
            result = {}
            for row in (res.data or []):
                uid = row["user_id"]
                result.setdefault(uid, []).append(row["player_id"])
            return result
        except Exception as e:
            log.error(f"Failed to fetch push tokens: {e}")
            return {}

    def _log_alert(self, alert_id: str, user_id: str, channel: str,
                   status: str, error: str = None):
        """Write delivery event to alert_logs table."""
        try:
            self.sb.table("alert_logs").insert({
                "alert_id":   alert_id,
                "user_id":    user_id,
                "channel":    channel,
                "status":     status,
                "error":      error,
                "sent_at":    datetime.utcnow().isoformat() + "Z",
            }).execute()
        except Exception:
            pass  # Never let logging break delivery

    def _save_alert(self, signal: dict) -> Optional[str]:
        """Persist alert to alerts table, return generated alert_id."""
        try:
            row = {
                "symbol":         signal.get("symbol", ""),
                "signal":         signal.get("signal", "HOLD"),
                "price":          signal.get("price", 0),
                "percent_change": signal.get("percent_change", 0),
                "reasoning":      signal.get("reasoning", ""),
                "entry_price":    signal.get("entry_price"),
                "target_price":   signal.get("target_price"),
                "stop_loss":      signal.get("stop_loss"),
                "created_at":     datetime.utcnow().isoformat() + "Z",
            }
            res = self.sb.table("alerts").insert(row).execute()
            if res.data:
                return res.data[0]["id"]
        except Exception as e:
            log.error(f"Failed to save alert: {e}")
        return None

    def _dispatch_to_user(
        self,
        user: dict,
        signal: dict,
        alert_id: str,
        push_token_map: dict,
        delay: int = 0,
    ):
        """Send all enabled channels to a single user."""
        uid    = user["id"]
        plan   = user.get("plan", "free")
        name   = (user.get("full_name") or "Investor").split()[0]
        email  = user.get("email", "")
        tg_id  = user.get("telegram_user_id")
        msgs   = format_signal(signal, plan)

        # ── Push notification ──────────────────────────────
        if user.get("push_alerts_enabled", True):
            tokens = push_token_map.get(uid, [])
            if tokens:
                result = send_push_onesignal(
                    title=msgs["push_title"],
                    body=msgs["push_body"],
                    player_ids=tokens,
                    data={"signal": signal.get("signal"), "symbol": signal.get("symbol")},
                    delay_seconds=delay,
                )
                status = "sent" if result.get("success") else "failed"
                self._log_alert(alert_id, uid, "push", status,
                                result.get("error") if not result.get("success") else None)

        # ── Telegram ───────────────────────────────────────
        if tg_id:
            if delay > 0:
                time.sleep(delay)
            ok = send_telegram_message(str(tg_id), msgs["telegram_html"])
            self._log_alert(alert_id, uid, "telegram",
                            "sent" if ok else "failed")

        # ── Email (only if not push/tg or explicit email pref) ────
        if user.get("email_alerts_enabled", False) and email:
            if delay > 0:
                time.sleep(delay)
            ok = send_email_brevo(
                email, user.get("full_name", name),
                msgs["email_subject"], msgs["email_html"],
                tags=["signal_alert", plan]
            )
            self._log_alert(alert_id, uid, "email",
                            "sent" if ok else "failed")

    def dispatch(self, signal: dict):
        """
        Main dispatch entry point.
        Call this whenever a new signal is generated.

        signal = {
          symbol, price, percent_change, signal, reasoning,
          entry_price, target_price, stop_loss
        }
        """
        log.info(f"\n{'='*50}")
        log.info(f"🚨 Dispatching: {signal.get('signal')} for {signal.get('symbol')}")

        # 1. Persist the alert
        alert_id = self._save_alert(signal)
        if not alert_id:
            log.error("Failed to save alert — aborting dispatch")
            return

        # 2. Load all users
        users = self._get_users_for_signal(signal)
        if not users:
            log.warning("No users found")
            return

        paid_users = [u for u in users if u.get("plan") in PAID_PLANS]
        free_users = [u for u in users if u.get("plan") not in PAID_PLANS]
        log.info(f"   Paid: {len(paid_users)} · Free: {len(free_users)}")

        # 3. Get all push tokens in one query
        all_ids       = [u["id"] for u in users]
        push_token_map = self._get_push_tokens(all_ids)

        # 4. Send to channels
        msgs = format_signal(signal, "pro")

        # Telegram channel posts
        if TELEGRAM_PREM_ID:
            send_telegram_message(TELEGRAM_PREM_ID, msgs["telegram_html"])
            log.info("   ✅ Telegram premium channel posted")

        if TELEGRAM_FREE_ID:
            # Schedule free channel delayed post
            def _post_free_channel():
                time.sleep(FREE_DELAY_SECONDS)
                free_msg = format_signal(signal, "free")
                send_telegram_message(TELEGRAM_FREE_ID, free_msg["telegram_html"])
                log.info("   ✅ Telegram free channel posted (delayed)")

            import threading
            threading.Thread(target=_post_free_channel, daemon=True).start()

        # 5. Dispatch to paid users — instant
        for user in paid_users:
            try:
                self._dispatch_to_user(user, signal, alert_id, push_token_map, delay=0)
            except Exception as e:
                log.error(f"Dispatch error for {user.get('id')}: {e}")

        # 6. Dispatch to free users — delayed
        def _send_free():
            time.sleep(FREE_DELAY_SECONDS)
            for user in free_users:
                try:
                    self._dispatch_to_user(user, signal, alert_id, push_token_map, delay=0)
                except Exception as e:
                    log.error(f"Free dispatch error: {e}")

        import threading
        threading.Thread(target=_send_free, daemon=True).start()

        log.info(f"✅ Dispatch complete: alert_id={alert_id}")
        return alert_id


# Singleton dispatcher
_dispatcher = None

def get_dispatcher() -> AlertDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = AlertDispatcher()
    return _dispatcher


if __name__ == "__main__":
    # Test dispatch
    test_signal = {
        "symbol":         "ZENITHBANK",
        "price":          45.20,
        "percent_change": 2.72,
        "signal":         "STRONG_BUY",
        "reasoning":      (
            "Zenith Bank is approaching key resistance at ₦46 with unusually "
            "high volume (+180% above average), indicating strong buying pressure. "
            "If price breaks above ₦46, a short-term rally toward ₦49–₦50 is likely."
        ),
        "entry_price":    45.50,
        "target_price":   49.00,
        "stop_loss":      43.80,
    }
    get_dispatcher().dispatch(test_signal)
