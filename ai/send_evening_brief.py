"""
NGX Signal — Evening Market Close Brief
Runs at 5:30PM WAT every weekday via GitHub Actions.
Sends: AI-generated close summary → Telegram channels + Push + Pro email.
"""
import os
import sys
import logging
import requests
from datetime import date, datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("EveningBrief")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TG_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_FREE      = os.environ.get("TELEGRAM_FREE_CHANNEL_ID", "")
TG_PREM      = os.environ.get("TELEGRAM_PREMIUM_CHANNEL_ID", "")
OS_APP       = os.environ.get("ONESIGNAL_APP_ID", "")
OS_KEY       = os.environ.get("ONESIGNAL_API_KEY", "")
BREVO_KEY    = os.environ.get("BREVO_API_KEY", "")
BREVO_FROM   = os.environ.get("BREVO_FROM_EMAIL", "signals@ngxsignal.com")
GROQ_KEY     = os.environ.get("GROQ_API_KEY", "")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")
DRY_RUN      = os.environ.get("DRY_RUN", "false").lower() == "true"
PAID_PLANS   = {"starter", "trader", "pro"}


def get_db():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def call_ai(prompt: str) -> str:
    if GROQ_KEY:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={"model": "llama-3.1-8b-instant",
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 900, "temperature": 0.65},
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                timeout=30
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log.warning(f"Groq failed: {e}")
    if GEMINI_KEY:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": 900}},
                timeout=30
            )
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            log.warning(f"Gemini failed: {e}")
    return "Evening brief AI analysis temporarily unavailable."


def tg_send(chat_id: str, text: str) -> bool:
    if not TG_TOKEN or not chat_id:
        log.warning(f"Telegram skip (token={bool(TG_TOKEN)}, chat={bool(chat_id)})")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15
        )
        d = r.json()
        if r.status_code == 200 and d.get("ok"):
            log.info(f"  Telegram OK → {chat_id}")
            return True
        err = d.get("description", "")
        log.error(f"  Telegram FAIL ({chat_id}): {err}")
        if "not a member" in err or "chat not found" in err:
            log.error("  FIX: Add bot as ADMIN to the channel")
        return False
    except Exception as e:
        log.error(f"  Telegram exception: {e}")
        return False


def push_send(title: str, body: str) -> bool:
    if not OS_APP or not OS_KEY:
        log.warning("OneSignal not configured — skip")
        return False
    try:
        r = requests.post(
            "https://onesignal.com/api/v1/notifications",
            json={"app_id": OS_APP, "included_segments": ["All"],
                  "headings": {"en": title}, "contents": {"en": body},
                  "url": "https://ngxsignal.streamlit.app"},
            headers={"Authorization": f"Basic {OS_KEY}", "Content-Type": "application/json"},
            timeout=15
        )
        d = r.json()
        if r.status_code == 200 and d.get("id"):
            log.info(f"  Push OK — {d.get('recipients',0)} recipients")
            return True
        log.error(f"  Push FAIL: {d}")
        return False
    except Exception as e:
        log.error(f"  Push exception: {e}")
        return False


def send_email(to: str, name: str, subject: str, html: str) -> bool:
    if not BREVO_KEY:
        return False
    try:
        r = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json={"sender": {"email": BREVO_FROM, "name": "NGX Signal"},
                  "to": [{"email": to, "name": name}],
                  "subject": subject, "htmlContent": html,
                  "tags": ["evening_brief"]},
            headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
            timeout=15
        )
        if r.status_code in (200, 201, 202):
            log.info(f"  Email OK → {to}")
            return True
        log.error(f"  Email FAIL ({to}): {r.status_code} {r.text[:80]}")
        return False
    except Exception as e:
        log.error(f"  Email exception: {e}")
        return False


def build_email_html(name: str, brief_html: str, date_str: str,
                     asi: float, asi_chg: float, gainers: list, losers: list) -> str:
    arr = "▲" if asi_chg >= 0 else "▼"
    ac  = "#22C55E" if asi_chg >= 0 else "#EF4444"

    g_rows = "".join(
        f"<tr><td style='padding:5px 0;font-family:monospace;color:#E8E2D4;'>{p['symbol']}</td>"
        f"<td style='text-align:right;color:#22C55E;font-family:monospace;'>+{float(p.get('change_percent',0)):.2f}%</td></tr>"
        for p in gainers[:5]
    )
    l_rows = "".join(
        f"<tr><td style='padding:5px 0;font-family:monospace;color:#E8E2D4;'>{p['symbol']}</td>"
        f"<td style='text-align:right;color:#EF4444;font-family:monospace;'>{float(p.get('change_percent',0)):.2f}%</td></tr>"
        for p in losers[:5]
    )
    return f"""<!DOCTYPE html><html>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'></head>
<body style='margin:0;padding:0;background:#000;font-family:Inter,sans-serif;'>
<div style='max-width:560px;margin:0 auto;padding:24px 16px;'>
  <div style='margin-bottom:18px;'>
    <span style='font-family:monospace;font-size:20px;font-weight:800;color:#fff;'>NGX</span>
    <span style='font-family:monospace;font-size:20px;font-weight:800;color:#F0A500;'>Signal</span>
    <span style='font-size:11px;color:#4B5563;margin-left:8px;text-transform:uppercase;letter-spacing:.1em;'>
      Evening Close · {date_str}
    </span>
  </div>
  <div style='background:#0D0D0D;border:1px solid #1F1F1F;border-radius:12px;padding:22px;margin-bottom:14px;'>
    <p style='font-size:15px;color:#fff;margin:0 0 16px;'>Hi {name}! Here's how today's session closed.</p>
    <div style='background:#000;border-radius:8px;padding:14px 16px;margin-bottom:16px;'>
      <div style='font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;'>NGX All-Share Index</div>
      <div style='font-size:28px;font-weight:500;color:#fff;font-family:monospace;'>{asi:,.2f}</div>
      <div style='font-size:14px;color:{ac};font-family:monospace;'>{arr} {abs(asi_chg):.2f}% today</div>
    </div>
    <table style='width:100%;border-collapse:collapse;'>
      <tr>
        <td style='width:50%;padding-right:10px;vertical-align:top;'>
          <div style='font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;'>Top Gainers</div>
          <table style='width:100%;border-collapse:collapse;'>{g_rows or "<tr><td style='color:#4B5563;'>No data</td></tr>"}</table>
        </td>
        <td style='width:50%;padding-left:10px;vertical-align:top;'>
          <div style='font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;'>Top Losers</div>
          <table style='width:100%;border-collapse:collapse;'>{l_rows or "<tr><td style='color:#4B5563;'>No data</td></tr>"}</table>
        </td>
      </tr>
    </table>
  </div>
  <div style='background:#0D0D0D;border:1px solid #1F1F1F;border-radius:12px;padding:22px;'>
    <div style='font-size:13px;color:#F0A500;font-weight:700;margin-bottom:12px;text-transform:uppercase;letter-spacing:.06em;'>
      🌆 AI Close Analysis
    </div>
    <div style='font-size:13px;color:#E0E0E0;line-height:1.75;white-space:pre-wrap;'>{brief_html}</div>
  </div>
  <div style='font-size:10px;color:#374151;text-align:center;margin-top:16px;line-height:1.6;'>
    NGX Signal · Educational only · Not financial advice<br>
    <a href='https://ngxsignal.streamlit.app' style='color:#374151;'>ngxsignal.streamlit.app</a>
  </div>
</div>
</body></html>"""


def main():
    log.info("=" * 55)
    log.info("NGX Signal — Evening Market Close Brief")
    log.info("=" * 55)
    if DRY_RUN:
        log.info("DRY RUN — no messages sent")

    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("FATAL: Missing Supabase credentials")
        sys.exit(1)

    sb       = get_db()
    today    = str(date.today())
    date_str = date.today().strftime("%A, %d %B %Y")

    # ── Pull market data ──────────────────────────────
    log.info("Fetching market data...")
    sm_res   = sb.table("market_summary").select("*").order("trading_date", desc=True).limit(1).execute()
    sm       = sm_res.data[0] if sm_res.data else {}
    asi      = float(sm.get("asi_index", 201156.86) or 201156.86)
    asi_chg  = float(sm.get("asi_change_percent", 0) or 0)
    gainers_c= int(sm.get("gainers_count", 0) or 0)
    losers_c = int(sm.get("losers_count", 0) or 0)

    lat_res  = sb.table("stock_prices").select("trading_date").order("trading_date", desc=True).limit(1).execute()
    lat_date = lat_res.data[0]["trading_date"] if lat_res.data else today

    pr_res   = sb.table("stock_prices").select("symbol,price,change_percent,volume").eq("trading_date", lat_date).limit(300).execute()
    prices   = pr_res.data or []
    seen = set(); uniq = []
    for p in prices:
        if p["symbol"] not in seen:
            seen.add(p["symbol"]); uniq.append(p)

    gainers = sorted([p for p in uniq if float(p.get("change_percent") or 0) > 0],
                     key=lambda x: float(x.get("change_percent", 0) or 0), reverse=True)[:5]
    losers  = sorted([p for p in uniq if float(p.get("change_percent") or 0) < 0],
                     key=lambda x: float(x.get("change_percent", 0) or 0))[:5]
    total   = len(uniq)

    # ── Signal scores for today ───────────────────────
    sig_res = sb.table("signal_scores").select("symbol,signal,stars,reasoning")\
        .eq("score_date", today).order("stars", desc=True).limit(6).execute()
    signals = sig_res.data or []

    g_text = ", ".join(f"{p['symbol']} (+{float(p.get('change_percent',0)):.1f}%)" for p in gainers)
    l_text = ", ".join(f"{p['symbol']} ({float(p.get('change_percent',0)):.1f}%)" for p in losers)
    s_text = "\n".join(f"- {s['symbol']}: {s.get('signal','')} ({s.get('stars',3)}★) — {(s.get('reasoning') or '')[:60]}" for s in signals[:4])

    arr = "▲" if asi_chg >= 0 else "▼"
    log.info(f"ASI: {asi:,.2f} ({asi_chg:+.2f}%) · {total} stocks · {gainers_c}↑ {losers_c}↓")

    # ── Generate AI analysis ──────────────────────────
    log.info("Generating AI evening brief...")
    prompt = f"""You are an NGX Signal post-market analyst. Write a concise evening close brief for Nigerian stock market investors.

Today's data ({date_str}):
- NGX All-Share Index: {asi:,.2f} ({asi_chg:+.2f}%)
- Total stocks traded: {total}
- Gainers: {gainers_c} | Losers: {losers_c}
- Top gainers: {g_text or 'N/A'}
- Top losers: {l_text or 'N/A'}
- Today's top signals:
{s_text or 'No signals today'}

Write the brief in this structure (plain text, no markdown headers, keep it tight):

MARKET CLOSE SUMMARY
(2-3 sentences: how the day ended, ASI direction, overall mood)

WHAT HAPPENED TODAY
(2-3 sentences: key movers and why, volume observations)

WINNERS TODAY
(1 line each for top 2-3 gainers — brief explanation of why they rose)

WATCHLIST FOR TOMORROW
(2-3 stocks to watch at tomorrow's open — with specific price levels)

SMART MONEY TAKE
(1 insight that experienced traders would be thinking about tonight)

Keep total length under 300 words. Write for Nigerian investors. No markdown. Professional but accessible."""

    brief_text = call_ai(prompt)
    log.info(f"AI brief generated ({len(brief_text)} chars)")

    # ══════════════════════════════════════════════════
    # 1. TELEGRAM — Premium channel (full brief + data)
    # ══════════════════════════════════════════════════
    log.info("\n[1] Telegram channels")

    g_lines = "\n".join(f"  📈 <b>{p['symbol']}</b>: +{float(p.get('change_percent',0)):.2f}%" for p in gainers[:3]) or "  No data"
    l_lines = "\n".join(f"  📉 <b>{p['symbol']}</b>: {float(p.get('change_percent',0)):.2f}%"  for p in losers[:3])  or "  No data"

    prem_msg = (
        f"🌆 <b>NGX Signal — Evening Close Brief</b>\n"
        f"📅 {date_str}\n\n"
        f"📊 <b>NGX All-Share Index</b>\n"
        f"  {arr} {asi:,.2f} ({asi_chg:+.2f}%)\n"
        f"  {total} stocks · {gainers_c} up · {losers_c} down\n\n"
        f"🔥 <b>Top Gainers</b>\n{g_lines}\n\n"
        f"📉 <b>Top Losers</b>\n{l_lines}\n\n"
        f"🧠 <b>AI Close Analysis</b>\n"
        f"<i>{brief_text[:600]}{'...' if len(brief_text) > 600 else ''}</i>\n\n"
        f"<a href='https://ngxsignal.streamlit.app'>Open full dashboard →</a>"
    )

    # Free channel — teaser only, no AI analysis
    free_msg = (
        f"🌆 <b>NGX Market Closed</b> — {date_str}\n\n"
        f"📊 ASI: {arr} {asi:,.2f} ({asi_chg:+.2f}%)\n"
        f"  {gainers_c} gainers · {losers_c} losers\n\n"
        f"🔥 Top movers: {g_text[:80] or 'N/A'}\n\n"
        f"🔒 <i>Full AI close analysis + tomorrow's watchlist available on Premium.\n"
        f"<a href='https://ngxsignal.streamlit.app'>Upgrade →</a></i>"
    )

    if not DRY_RUN:
        if TG_PREM:
            tg_send(TG_PREM, prem_msg)
        if TG_FREE:
            tg_send(TG_FREE, free_msg)
    else:
        log.info("  [DRY RUN] Telegram skipped")

    # ══════════════════════════════════════════════════
    # 2. ONESIGNAL PUSH
    # ══════════════════════════════════════════════════
    log.info("\n[2] OneSignal push")
    push_title = f"🌆 NGX Market Closed — {date_str}"
    push_body  = f"ASI: {arr} {asi:,.2f} ({asi_chg:+.2f}%) · {gainers_c} gainers · {losers_c} losers. Tap for your evening brief."

    if not DRY_RUN:
        push_send(push_title, push_body)
    else:
        log.info("  [DRY RUN] Push skipped")

    # ══════════════════════════════════════════════════
    # 3. EMAIL — Pro users only
    # ══════════════════════════════════════════════════
    log.info("\n[3] Email (Pro users)")
    try:
        users_res = sb.table("profiles")\
            .select("id, full_name, email, plan, email_alerts_enabled")\
            .not_.is_("email", "null").execute()
        pro_users = [
            u for u in (users_res.data or [])
            if u.get("email") and u.get("plan") == "pro" and u.get("email_alerts_enabled", False)
        ]
        log.info(f"  {len(pro_users)} Pro users with email enabled")

        sent = 0
        for user in pro_users:
            name = (user.get("full_name") or "Investor").split()[0]
            html = build_email_html(
                name, brief_text, date_str,
                asi, asi_chg, gainers, losers
            )
            if not DRY_RUN:
                ok = send_email(
                    user["email"], user.get("full_name", name),
                    f"🌆 NGX Evening Close Brief — {date_str}", html
                )
                if ok: sent += 1
            else:
                log.info(f"  [DRY RUN] Would email {user['email']}")
                sent += 1

        log.info(f"  Email: {sent} sent")
    except Exception as e:
        log.error(f"  Email error: {e}")

    # ══════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════
    log.info("\n" + "=" * 55)
    log.info("Evening brief complete!")
    log.info(f"  ASI:     {asi:,.2f} ({asi_chg:+.2f}%)")
    log.info(f"  Movers:  {gainers_c} up · {losers_c} down")
    log.info(f"  Stocks:  {total} tracked")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
