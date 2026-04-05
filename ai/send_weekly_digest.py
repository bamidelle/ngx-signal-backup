"""
NGX Signal — Weekly Digest Sender
Standalone — no imports from notification_dispatcher.
Called by: python ai/send_weekly_digest.py (from repo root).
"""
import os, sys, requests, logging
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("WeeklyDigest")

SUPABASE_URL = os.environ.get("SUPABASE_URL","")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY","")
BREVO_KEY    = os.environ.get("BREVO_API_KEY","")
BREVO_FROM   = os.environ.get("BREVO_FROM_EMAIL","signals@ngxsignal.com")
TG_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN","")
TG_FREE      = os.environ.get("TELEGRAM_FREE_CHANNEL_ID","")
TG_PREM      = os.environ.get("TELEGRAM_PREMIUM_CHANNEL_ID","")
OS_APP       = os.environ.get("ONESIGNAL_APP_ID","")
OS_KEY       = os.environ.get("ONESIGNAL_API_KEY","")
DRY_RUN      = os.environ.get("DRY_RUN","false").lower()=="true"
PAID_PLANS   = {"starter","trader","pro"}


def get_db():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def tg_post(chat_id, text):
    if not TG_TOKEN or not chat_id:
        log.warning(f"Telegram skip — token={bool(TG_TOKEN)} chat={bool(chat_id)}")
        return False
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id":chat_id,"text":text,"parse_mode":"HTML","disable_web_page_preview":True}, timeout=15)
    d = r.json()
    if r.status_code==200 and d.get("ok"):
        log.info(f"  Telegram OK → {chat_id}"); return True
    err = d.get("description","")
    log.error(f"  Telegram FAIL ({chat_id}): {err}")
    if "not a member" in err or "chat not found" in err:
        log.error("  FIX: Add bot as ADMIN to the channel")
    if "not enough rights" in err or "forbidden" in err:
        log.error("  FIX: Give bot 'Post Messages' admin right")
    return False


def push_broadcast(title, body):
    if not OS_APP or not OS_KEY:
        log.warning("OneSignal skip — not configured"); return False
    r = requests.post("https://onesignal.com/api/v1/notifications",
        json={"app_id":OS_APP,"included_segments":["All"],
              "headings":{"en":title},"contents":{"en":body},
              "url":"https://ngxsignal.streamlit.app"},
        headers={"Authorization":f"Basic {OS_KEY}","Content-Type":"application/json"}, timeout=15)
    d = r.json()
    if r.status_code==200 and d.get("id"):
        log.info(f"  Push OK — {d.get('recipients',0)} recipients"); return True
    log.error(f"  Push FAIL: {d}"); return False


def send_email(to, name, subject, html):
    if not BREVO_KEY:
        log.warning("Brevo skip — BREVO_API_KEY not set"); return False
    r = requests.post("https://api.brevo.com/v3/smtp/email",
        json={"sender":{"email":BREVO_FROM,"name":"NGX Signal"},
              "to":[{"email":to,"name":name}],
              "subject":subject,"htmlContent":html,"tags":["weekly_digest"]},
        headers={"api-key":BREVO_KEY,"Content-Type":"application/json"}, timeout=15)
    if r.status_code in (200,201,202):
        log.info(f"  Email OK → {to}"); return True
    log.error(f"  Email FAIL ({to}): {r.status_code} {r.text[:100]}"); return False


def build_html(name, plan, week_str, asi, asi_chg, gainers, losers, total):
    arrow = "▲" if asi_chg>=0 else "▼"
    ac    = "#22C55E" if asi_chg>=0 else "#EF4444"
    grows = "".join(f"<tr><td style='padding:5px 0;font-family:monospace;color:#E8E2D4;'>{p['symbol']}</td><td style='text-align:right;color:#22C55E;font-family:monospace;'>+{float(p.get('change_percent',0)):.2f}%</td></tr>" for p in gainers[:5]) or "<tr><td colspan='2' style='color:#4B5563;'>No data</td></tr>"
    lrows = "".join(f"<tr><td style='padding:5px 0;font-family:monospace;color:#E8E2D4;'>{p['symbol']}</td><td style='text-align:right;color:#EF4444;font-family:monospace;'>{float(p.get('change_percent',0)):.2f}%</td></tr>" for p in losers[:5]) or "<tr><td colspan='2' style='color:#4B5563;'>No data</td></tr>"
    upsell = f"""<div style='background:#1A1600;border:1px solid #3D2E00;border-radius:10px;padding:18px;text-align:center;margin-top:20px;'><div style='color:#F0A500;font-size:15px;font-weight:700;margin-bottom:6px;'>⚡ Never Miss Another Trade</div><div style='color:#6B7280;font-size:13px;line-height:1.6;margin-bottom:12px;'>Premium users received every signal this week instantly with entry/target/stop-loss.</div><a href='https://ngxsignal.streamlit.app' style='background:#F0A500;color:#0A0C0F;font-weight:700;font-size:13px;padding:9px 22px;border-radius:999px;text-decoration:none;'>Upgrade from ₦3,500/mo →</a></div>""" if plan not in PAID_PLANS else ""
    return f"""<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body style='margin:0;padding:0;background:#0A0C0F;font-family:Inter,sans-serif;'><div style='max-width:560px;margin:0 auto;padding:24px 16px;'><div style='margin-bottom:18px;'><span style='font-family:monospace;font-size:20px;font-weight:800;color:#fff;'>NGX</span><span style='font-family:monospace;font-size:20px;font-weight:800;color:#F0A500;'>Signal</span><span style='font-size:11px;color:#4B5563;margin-left:8px;text-transform:uppercase;letter-spacing:.1em;'>Weekly Digest · {week_str}</span></div><div style='background:#10131A;border:1px solid #1E2229;border-radius:12px;padding:22px;'><p style='font-size:15px;color:#E8E2D4;margin:0 0 16px;'>Hi {name}! Your NGX week in numbers.</p><div style='background:#0A0C0F;border-radius:8px;padding:14px 16px;margin-bottom:16px;'><div style='font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;'>NGX All-Share Index</div><div style='font-size:28px;font-weight:500;color:#E8E2D4;font-family:monospace;'>{asi:,.2f}</div><div style='font-size:14px;color:{ac};font-family:monospace;'>{arrow} {abs(asi_chg):.2f}% this week · {total} stocks</div></div><table style='width:100%;border-collapse:collapse;'><tr><td style='width:50%;padding-right:10px;vertical-align:top;'><div style='font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;'>Top Gainers</div><table style='width:100%;border-collapse:collapse;'>{grows}</table></td><td style='width:50%;padding-left:10px;vertical-align:top;'><div style='font-size:10px;color:#4B5563;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;'>Top Losers</div><table style='width:100%;border-collapse:collapse;'>{lrows}</table></td></tr></table></div>{upsell}<div style='font-size:10px;color:#374151;text-align:center;margin-top:16px;'>NGX Signal · Educational only · Not financial advice</div></div></body></html>"""


def main():
    log.info("="*55 + "\nNGX Signal — Weekly Digest\n" + "="*55)
    if DRY_RUN: log.info("DRY RUN — no messages sent")

    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("FATAL: SUPABASE_URL or SUPABASE_SERVICE_KEY missing"); sys.exit(1)

    sb = get_db()

    # Market data
    sm   = (sb.table("market_summary").select("*").order("trading_date",desc=True).limit(1).execute().data or [{}])[0]
    asi  = float(sm.get("asi_index",201156.86) or 201156.86)
    achg = float(sm.get("asi_change_percent",0) or 0)
    ldate= (sb.table("stock_prices").select("trading_date").order("trading_date",desc=True).limit(1).execute().data or [{"trading_date":str(date.today())}])[0]["trading_date"]
    pr   = sb.table("stock_prices").select("symbol,price,change_percent").eq("trading_date",ldate).limit(500).execute().data or []
    seen=set(); uniq=[]
    for p in pr:
        if p["symbol"] not in seen: seen.add(p["symbol"]); uniq.append(p)
    gainers = sorted([p for p in uniq if float(p.get("change_percent") or 0)>0], key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:5]
    losers  = sorted([p for p in uniq if float(p.get("change_percent") or 0)<0], key=lambda x:float(x.get("change_percent",0) or 0))[:5]
    total   = len(uniq)
    week_str= date.today().strftime("%d %B %Y")
    arr     = "▲" if achg>=0 else "▼"
    log.info(f"Data: ASI={asi:,.2f} ({achg:+.2f}%) · {total} stocks")

    # 1. Telegram
    log.info("\n[1] Telegram channels")
    g_lines = "\n".join(f"  📈 <b>{p['symbol']}</b>: +{float(p.get('change_percent',0)):.2f}%" for p in gainers[:3]) or "  No data"
    l_lines = "\n".join(f"  📉 <b>{p['symbol']}</b>: {float(p.get('change_percent',0)):.2f}%" for p in losers[:3]) or "  No data"
    free_msg = f"📊 <b>NGX Signal — Weekly Digest</b>\n🗓 {week_str}\n\n📈 <b>All-Share Index</b>\n  {arr} {asi:,.2f} ({achg:+.2f}%)\n  {total} stocks tracked\n\n🔥 <b>Top Gainers</b>\n{g_lines}\n\n📉 <b>Top Losers</b>\n{l_lines}\n\n⏱ <i>Free plan: 3-min delay.\n<a href='https://ngxsignal.streamlit.app'>Upgrade for instant signals →</a></i>"
    prem_msg = f"💎 <b>NGX Signal Premium — Weekly Digest</b>\n🗓 {week_str}\n\n📈 <b>All-Share Index</b>\n  {arr} {asi:,.2f} ({achg:+.2f}%)\n  {total} stocks tracked\n\n🔥 <b>Top Gainers</b>\n{g_lines}\n\n📉 <b>Top Losers</b>\n{l_lines}\n\n🚀 <a href='https://ngxsignal.streamlit.app'>Open dashboard →</a>"
    if not DRY_RUN:
        tg_post(TG_FREE, free_msg)
        tg_post(TG_PREM, prem_msg)
    else: log.info("  [DRY RUN] skipped")

    # 2. Email
    log.info("\n[2] Email digest")
    users = [u for u in (sb.table("profiles").select("id,full_name,email,plan,email_alerts_enabled").not_.is_("email","null").execute().data or []) if u.get("email")]
    log.info(f"  {len(users)} users with email")
    esent=eskip=0
    for u in users:
        if not u.get("email_alerts_enabled",False): eskip+=1; continue
        html = build_html(u.get("full_name","Investor").split()[0], u.get("plan","free"), week_str, asi, achg, gainers, losers, total)
        if not DRY_RUN:
            ok = send_email(u["email"], u.get("full_name","Investor"), f"📊 NGX Signal Weekly Digest — {week_str}", html)
            if ok: esent+=1
            else:  eskip+=1
        else: log.info(f"  [DRY RUN] would email {u['email']}"); esent+=1
    log.info(f"  Email: {esent} sent · {eskip} skipped")

    # 3. Push
    log.info("\n[3] OneSignal push")
    if not DRY_RUN:
        push_broadcast(
            "📊 NGX Signal Weekly Digest",
            f"ASI: {asi:,.2f} ({arr}{abs(achg):.2f}%) · {total} stocks · {len(gainers)} gainers this week"
        )
    else: log.info("  [DRY RUN] skipped")

    log.info("\n" + "="*55 + "\nWeekly digest complete!\n" + "="*55)


if __name__ == "__main__":
    main()
