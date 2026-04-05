import streamlit as st
import re
import requests
from datetime import date, datetime
from app.utils.supabase_client import get_supabase

try:
    import pytz
    WAT = pytz.timezone("Africa/Lagos")
    def now_wat(): return datetime.now(WAT)
except ImportError:
    # fallback: UTC+1 (WAT)
    from datetime import timezone, timedelta
    WAT_TZ = timezone(timedelta(hours=1))
    def now_wat(): return datetime.now(WAT_TZ)

NG_HOLIDAYS_2026 = {
    "2026-01-01","2026-01-03","2026-04-03","2026-04-06",
    "2026-05-01","2026-06-12","2026-10-01","2026-12-25","2026-12-26",
}

def get_market_status():
    now  = now_wat()
    dow  = now.weekday()
    ds   = now.strftime("%Y-%m-%d")
    hhmm = now.hour * 60 + now.minute
    OPEN, CLOSE = 10*60, 15*60
    if dow >= 5:
        return {"is_open":False,"label":"Closed — Weekend","note":"NGX is closed on weekends. Showing last closing prices.","color":"#EF4444"}
    if ds in NG_HOLIDAYS_2026:
        return {"is_open":False,"label":"Closed — Public Holiday","note":"NGX is closed today. Showing last closing prices.","color":"#EF4444"}
    if hhmm < OPEN:
        m = OPEN - hhmm
        return {"is_open":False,"label":f"Pre-Market — Opens in {m//60}h {m%60}m","note":"NGX opens 10AM WAT. Showing last closing prices.","color":"#D97706"}
    if hhmm >= CLOSE:
        return {"is_open":False,"label":"Closed — After Hours","note":"NGX closed 3PM WAT. Showing today's final prices.","color":"#A78BFA"}
    m = CLOSE - hhmm
    return {"is_open":True,"label":f"Open — Closes in {m//60}h {m%60}m","note":"Market is live.","color":"#22C55E"}

def get_greeting(name):
    h = now_wat().hour
    if 5<=h<12:   return f"Good morning, {name} 👋"
    elif 12<=h<17: return f"Good afternoon, {name} ☀️"
    elif 17<=h<21: return f"Good evening, {name} 🌆"
    else:          return f"Hello, {name} 🌙"

def call_ai(prompt, max_tokens=500):
    for key_name, make_req in [
        ("GROQ_API_KEY", lambda k:(
            "https://api.groq.com/openai/v1/chat/completions",
            {"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,"temperature":0.7},
            {"Authorization":f"Bearer {k}","Content-Type":"application/json"},
            lambda d: d["choices"][0]["message"]["content"]
        )),
        ("GEMINI_API_KEY", lambda k:(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={k}",
            {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":max_tokens}},
            {},
            lambda d: d["candidates"][0]["content"]["parts"][0]["text"]
        )),
    ]:
        key = st.secrets.get(key_name,"")
        if not key: continue
        try:
            url,payload,headers,extract = make_req(key)
            r = requests.post(url,json=payload,headers=headers,timeout=20)
            return extract(r.json())
        except Exception: continue
    return "AI temporarily unavailable. Please try again shortly."

def get_all_latest_prices(sb):
    date_res = sb.table("stock_prices").select("trading_date").order("trading_date",desc=True).limit(1).execute()
    if not date_res.data: return [], str(date.today())
    latest = date_res.data[0]["trading_date"]
    today_res = sb.table("stock_prices").select("symbol,price,change_percent,volume").eq("trading_date",latest).limit(500).execute()
    prices = today_res.data or []
    if len(prices) < 50:
        broad = sb.table("stock_prices").select("symbol,price,change_percent,volume,trading_date").order("trading_date",desc=True).limit(5000).execute()
        sym_map = {}
        for p in (broad.data or []):
            s=p.get("symbol","")
            if s and s not in sym_map: sym_map[s]=p
        existing = {p["symbol"] for p in prices}
        prices += [p for s,p in sym_map.items() if s not in existing]
    return prices, latest


def render():
    sb           = get_supabase()
    profile      = st.session_state.get("profile", {})
    plan         = profile.get("plan", "free")
    name         = profile.get("full_name", "Investor").split()[0]
    today        = str(date.today())
    current_user = st.session_state.get("user")
    market       = get_market_status()
    now          = now_wat()

    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@600;700;800&display=swap');
.hg{font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:700;color:#FFFFFF;margin-bottom:4px;}
.hd{font-family:'DM Mono',monospace;font-size:11px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:16px;}
.mg{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px;}
.mc{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:12px;padding:16px;font-family:'DM Mono',monospace;transition:border-color .25s;}
.mc:hover{border-color:rgba(240,165,0,.3);}
.ml{font-size:10px;color:#808080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;}
.mv{font-size:22px;font-weight:500;line-height:1;margin-bottom:4px;}
.ms{font-size:11px;color:#808080;}
.sec-title{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700;color:#FFFFFF;margin:24px 0 8px 0;}
.sec-intro{font-family:'DM Mono',monospace;font-size:13px;color:#B0B0B0;line-height:1.7;margin-bottom:14px;background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:14px 16px;}
.sp-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0 16px 0;}
.sp-card{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:16px;font-family:'DM Mono',monospace;}
.ni{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px 16px;margin-bottom:8px;font-family:'DM Mono',monospace;}
.ai-chat-wrap{background:#050505;border:1px solid #1F1F1F;border-radius:16px;padding:20px;margin-bottom:20px;transition:border-color .3s,box-shadow .3s;}
.ai-chat-wrap:hover{border-color:rgba(100,180,255,.25);box-shadow:0 0 24px rgba(100,180,255,.08);}
.ai-chat-header{display:flex;align-items:center;gap:10px;margin-bottom:14px;}
.ai-chat-title{font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;color:#FFFFFF;}
.ai-chat-sub{font-family:'DM Mono',monospace;font-size:11px;color:#808080;margin-top:1px;}
.ai-msg-user{background:rgba(240,165,0,.10);border:1px solid rgba(240,165,0,.20);border-radius:12px 12px 4px 12px;padding:10px 14px;font-family:'DM Mono',monospace;font-size:13px;color:#FFFFFF;margin-bottom:10px;margin-left:20%;line-height:1.6;}
.ai-msg-bot{background:#0D0D0D;border:1px solid rgba(100,180,255,.15);border-left:3px solid rgba(100,180,255,.5);border-radius:4px 12px 12px 12px;padding:12px 16px;font-family:'DM Mono',monospace;font-size:13px;color:#D0D0D0;margin-bottom:10px;margin-right:10%;line-height:1.75;}
.ai-msg-bot strong{color:#FFFFFF;}
.ai-msg-bot table{width:100%;border-collapse:collapse;margin:8px 0;font-size:12px;}
.ai-msg-bot table th{background:#111;color:#F0A500;padding:6px 10px;text-align:left;border-bottom:1px solid #222;}
.ai-msg-bot table td{padding:5px 10px;border-bottom:1px solid #1A1A1A;color:#D0D0D0;}
@media(max-width:768px){.mg{grid-template-columns:repeat(2,1fr);}.sp-grid{grid-template-columns:1fr;}.ai-msg-user{margin-left:5%;}.ai-msg-bot{margin-right:0;}}
</style>
""", unsafe_allow_html=True)

    # GREETING
    st.markdown(f"""
<div class="hg">{get_greeting(name)}</div>
<div class="hd">{now.strftime("%A, %d %B %Y")} · {now.strftime("%I:%M %p")} WAT · Market AI</div>
""", unsafe_allow_html=True)

    # MARKET STATUS BANNER
    st.markdown(f"""
<div style="background:#0A0A0A;border:1px solid {market['color']}44;border-left:3px solid {market['color']};
            border-radius:8px;padding:10px 14px;margin-bottom:16px;
            display:flex;align-items:center;gap:10px;font-family:'DM Mono',monospace;">
  <span style="font-size:16px;">{'📈' if market['is_open'] else '🔒'}</span>
  <div>
    <span style="font-size:13px;font-weight:600;color:{market['color']};">{market['label']}</span>
    <span style="font-size:12px;color:#808080;margin-left:10px;">{market['note']}</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # DATA
    raw, latest_date = get_all_latest_prices(sb)
    seen=set(); uniq=[]
    for p in raw:
        s=p.get("symbol","")
        if s and s not in seen: seen.add(s); uniq.append(p)

    total   = len(uniq)
    gainers = sum(1 for p in uniq if float(p.get("change_percent") or 0)>0)
    losers  = sum(1 for p in uniq if float(p.get("change_percent") or 0)<0)

    sm_res = sb.table("market_summary").select("*").order("trading_date",desc=True).limit(1).execute()
    sm     = sm_res.data[0] if sm_res.data else {}
    asi    = float(sm.get("asi_index",0) or 0)
    acg    = float(sm.get("asi_change_percent",0) or 0)
    gc     = gainers if total>5 else int(sm.get("gainers_count",0) or 0)
    lc     = losers  if total>5 else int(sm.get("losers_count",0) or 0)
    acol   = "#22C55E" if acg>=0 else "#EF4444"
    aarr   = "▲" if acg>=0 else "▼"
    if acg>0.5:    mood,mcol,moji="Bullish","#22C55E","🟢"
    elif acg<-0.5: mood,mcol,moji="Bearish","#EF4444","🔴"
    else:          mood,mcol,moji="Neutral","#F0A500","🟡"
    ad         = f"{asi:,.2f}" if asi>0 else "Updating..."
    data_label = latest_date if market["is_open"] else f"Closed · Last: {latest_date}"

    brief_res = sb.table("ai_briefs").select("body,brief_date").eq("language","en").eq("brief_type","morning").order("brief_date",desc=True).limit(1).execute()
    brief_ok  = bool(brief_res.data)
    brief_color = "#F0A500" if brief_ok else "#808080"

    # 4 METRIC CARDS
    st.markdown(f"""
<div class="mg">
  <div class="mc" style="border-top:2px solid {acol};">
    <div class="ml">NGX All-Share · {data_label}</div>
    <div class="mv" style="color:{acol};">{ad}</div>
    <div class="ms">{aarr} {abs(acg):.2f}% · {total} stocks tracked</div>
  </div>
  <div class="mc" style="border-top:2px solid #1F1F1F;">
    <div class="ml">Gainers / Losers</div>
    <div class="mv"><span style="color:#22C55E;">{gc}</span><span style="color:#333;font-size:16px;"> / </span><span style="color:#EF4444;">{lc}</span></div>
    <div class="ms">{total-gc-lc} unchanged · {total} total</div>
  </div>
  <div class="mc" style="border-top:2px solid {mcol};">
    <div class="ml">Market Mood</div>
    <div class="mv" style="font-size:16px;color:{mcol};">{moji} {mood}</div>
    <div class="ms">{'Live breadth' if market['is_open'] else 'Last close breadth'}</div>
  </div>
  <div class="mc" style="border-top:2px solid {brief_color};">
    <div class="ml">AI Brief</div>
    <div class="mv" style="font-size:14px;color:{brief_color};">✨ {'Today' if brief_ok else 'Updating...'}</div>
    <div class="ms">Market {'open' if market['is_open'] else 'closed'}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════
    # MARKET AI CHAT
    # ══════════════════════════════════════════════════
    st.markdown('<div class="sec-title">✨ Market AI for NGX Stock Market</div>', unsafe_allow_html=True)

    if "mai_history" not in st.session_state: st.session_state.mai_history=[]

    CHIPS = [
        "Why is MTNN rallying today?",
        "What sectors should I watch?",
        "Is GTCO a buy right now?",
    ]

    top_g_text = ", ".join(
        f"{p['symbol']} (+{float(p.get('change_percent',0)):.1f}%)"
        for p in sorted(uniq, key=lambda x:float(x.get("change_percent",0) or 0), reverse=True)[:3]
    )

    st.markdown('<div class="ai-chat-wrap">', unsafe_allow_html=True)
    st.markdown(f"""
<div class="ai-chat-header">
  <div style="width:36px;height:36px;background:linear-gradient(135deg,#1A2040,#0D1530);
              border:1px solid rgba(100,180,255,.3);border-radius:10px;
              display:flex;align-items:center;justify-content:center;font-size:18px;">✨</div>
  <div>
    <div class="ai-chat-title">Market AI — Ask Anything</div>
    <div class="ai-chat-sub">ASI: {ad} · {moji} {mood} · {'Live' if market['is_open'] else market['label']}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Quick chips
    chip_cols = st.columns(len(CHIPS))
    for ci, chip in enumerate(CHIPS):
        with chip_cols[ci]:
            if st.button(chip, key=f"chip_{ci}", use_container_width=True):
                st.session_state.mai_pending = chip

    # Chat history
    for msg in st.session_state.mai_history[-6:]:
        if msg["role"]=="user":
            st.markdown(f'<div class="ai-msg-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            c = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', msg["content"])
            c = c.replace("\n","<br>")
            st.markdown(f'<div class="ai-msg-bot">{c}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Pending chip → pre-fill
    default_q = ""
    if "mai_pending" in st.session_state:
        default_q = st.session_state.pop("mai_pending")

    icol, bcol = st.columns([5,1])
    with icol:
        user_q = st.text_input("Market AI input", value=default_q,
            placeholder="✨ Ask about NGX stocks, sectors, signals...",
            key="mai_input", label_visibility="collapsed")
    with bcol:
        send = st.button("➤ Send", key="mai_send", type="primary", use_container_width=True)

    question = (user_q or "").strip()
    if send and question:
        system_prompt = (
            f"You are a sophisticated Nigerian stock market analyst for NGX Signal.\n\n"
            f"LIVE MARKET DATA:\n"
            f"- NGX All-Share Index: {ad} ({aarr}{abs(acg):.2f}%)\n"
            f"- Market: {'Open' if market['is_open'] else 'Closed — '+market['note']}\n"
            f"- Mood: {mood} | Gainers: {gc} | Losers: {lc} | Tracked: {total}\n"
            f"- Top gainers: {top_g_text or 'N/A'}\n"
            f"- Data as of: {latest_date}\n\n"
            f"RULES:\n"
            f"- Use **BOLD** for stock tickers like **GTCO** or **MTNN**.\n"
            f"- Use Markdown tables when comparing stocks.\n"
            f"- Use 📈 gains, 📉 dips, ✨ insights — sparingly.\n"
            f"- Under 200 words unless a table is needed.\n"
            f"- End with: _Educational only — not financial advice._\n\n"
            f"Question: {question}"
        )
        st.session_state.mai_history.append({"role":"user","content":question})
        with st.spinner("✨ Analysing..."):
            answer = call_ai(system_prompt, max_tokens=500)
        st.session_state.mai_history.append({"role":"assistant","content":answer})
        st.rerun()

    if st.session_state.mai_history:
        if st.button("🗑 Clear chat", key="mai_clear"):
            st.session_state.mai_history=[]; st.rerun()

    # TOP MOVERS
    sup = sorted([p for p in uniq if float(p.get("change_percent") or 0)>0], key=lambda x:float(x.get("change_percent",0) or 0),reverse=True)[:8]
    sdn = sorted([p for p in uniq if float(p.get("change_percent") or 0)<0], key=lambda x:float(x.get("change_percent",0) or 0))[:4]
    movers = sup+sdn

    mrows = "".join(f"""<div style="display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #111;font-size:13px;">
<div style="display:flex;align-items:center;gap:10px;"><span style="font-weight:500;color:#FFFFFF;">{s['symbol']}</span><span style="color:#808080;font-size:12px;">&#8358;{float(s.get('price',0) or 0):,.2f}</span></div>
<span style="color:{'#22C55E' if float(s.get('change_percent',0) or 0)>=0 else '#EF4444'};font-weight:500;">{'&#9650;' if float(s.get('change_percent',0) or 0)>=0 else '&#9660;'} {abs(float(s.get('change_percent',0) or 0)):.2f}%</span>
</div>""" for s in movers) or '<div style="padding:20px;text-align:center;color:#606060;font-size:12px;">No data yet</div>'

    ph = max(len(movers)*43+55,80)+48
    st.components.v1.html(f"""<!DOCTYPE html><html>
<head><link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}html,body{{background:transparent;font-family:'DM Mono',monospace;overflow:hidden;}}
.p{{background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:16px 18px;}}
.pt{{font-size:11px;font-weight:500;color:#F0A500;text-transform:uppercase;letter-spacing:.1em;margin-bottom:14px;}}</style></head>
<body><div class="p">
<div class="pt">&#128293; Top Movers · {latest_date} {'📈 Live' if market['is_open'] else '🔒 Last Close'}</div>
{mrows}
</div></body></html>""", height=ph, scrolling=False)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("📊 View All Live Stocks →", key="btn_all_stocks", type="primary"):
        st.session_state.current_page="all_stocks"; st.rerun()

    # SIGNAL CARDS
    st.markdown('<div class="sec-title">📊 Today\'s Biggest Movers on the NGX</div>', unsafe_allow_html=True)
    st.markdown("""<div class="sec-intro">
Three stocks that deserve your attention today — one to consider buying, one to hold, one to approach with caution.
Based on today's live signal scores. Always do your own research.
</div>""", unsafe_allow_html=True)

    sig_res = sb.table("signal_scores").select("symbol,signal,stars,reasoning").order("score_date",desc=True).order("stars",desc=True).limit(300).execute()
    seen_sig=set(); buy_s=hold_s=caut_s=None
    for s in (sig_res.data or []):
        sym=s.get("symbol",""); sig=s.get("signal","").upper().replace(" ","_")
        if sym in seen_sig: continue
        seen_sig.add(sym)
        if not buy_s  and sig in ("STRONG_BUY","BUY"): buy_s=s
        elif not hold_s and sig=="HOLD":                hold_s=s
        elif not caut_s and sig=="CAUTION":             caut_s=s
        if buy_s and hold_s and caut_s: break

    def sp_card(stock,lbl,ac,bg,bd):
        if not stock:
            return f'<div class="sp-card" style="border-color:{bd};background:{bg};"><span style="background:{ac}22;color:{ac};font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;">{lbl}</span><div style="font-size:15px;font-weight:600;color:#606060;margin-top:8px;">—</div><div style="font-size:11px;color:#606060;margin-top:4px;">No signal data yet.</div></div>'
        sym=stock.get("symbol","—"); reason=(stock.get("reasoning") or "No analysis.")[:120]+"…"; stars="⭐"*int(stock.get("stars",3))
        return f'<div class="sp-card" style="border-color:{bd};background:{bg};border-left:3px solid {ac};"><span style="background:{ac}22;color:{ac};font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;">{lbl}</span><div style="font-size:16px;font-weight:600;color:#FFFFFF;margin-top:8px;">{sym} <span style="font-size:12px;">{stars}</span></div><div style="font-size:11px;color:#B0B0B0;margin-top:6px;line-height:1.5;">{reason}</div></div>'

    st.markdown(f"""<div class="sp-grid">
{sp_card(buy_s,"✅ BUY TODAY","#22C55E","#001A00","#003D00")}
{sp_card(hold_s,"⏸️ HOLD","#D97706","#1A1200","#3D2800")}
{sp_card(caut_s,"⚠️ CAUTION","#EA580C","#1A0800","#3D1500")}
</div>""", unsafe_allow_html=True)

    if st.button("🔥 See Hot Stocks Today →", key="btn_hot", type="primary"):
        st.session_state.current_page="hot"; st.rerun()

    # AI BRIEF EXPANDER
    with st.expander("✨  MARKET AI BRIEF", expanded=False):
        lang_display="en"
        if plan in ("trader","pro"):
            if st.toggle("🇳🇬 Switch to Pidgin", key="home_lang"): lang_display="pg"
        else:
            st.caption("🇳🇬 Pidgin mode available on Trader plan")

        if brief_ok:
            raw2  = brief_res.data[0].get("body","")
            bdate = brief_res.data[0].get("brief_date",today)
            clean = re.sub(r'\*\*(.+?)\*\*',r'\1',raw2)
            closed_note = "" if market["is_open"] else f" <span style='color:#EF4444;font-size:11px;'>(Market closed — last session data)</span>"
            st.caption(f"📅 AI Market Brief — {bdate}{closed_note}")
            for sec in clean.strip().split("\n\n"):
                if sec.strip():
                    st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:13px;color:#D0D0D0;line-height:1.8;margin-bottom:8px;padding:8px 0;border-bottom:1px solid #1A1A1A;'>{sec.strip()}</div>",unsafe_allow_html=True)
        else:
            msg = f"📭 {market['note']} Morning brief generates at weekday market open." if not market["is_open"] else "📭 Brief being generated. Check back shortly."
            st.info(msg)

    # SECTOR SNAPSHOT
    with st.expander("🚦  SECTOR SNAPSHOT", expanded=False):
        st.markdown("""<div class="sec-intro">
🟢 Bullish sectors — consider stocks within them. 🟡 Mixed — wait for direction. 🔴 Weakening — caution.
</div>""", unsafe_allow_html=True)
        sec_res = sb.table("sector_performance").select("sector_name,traffic_light,change_percent,verdict").order("change_percent",desc=True).execute()
        if sec_res.data:
            seen_s={}
            for s in sec_res.data:
                sn=s.get("sector_name","").strip()
                if sn and sn not in seen_s: seen_s[sn]=s
            cols=st.columns(3)
            for i,s in enumerate(sorted(seen_s.values(),key=lambda x:float(x.get("change_percent",0) or 0),reverse=True)):
                light=s.get("traffic_light","amber"); emoji="🟢" if light=="green" else "🔴" if light=="red" else "🟡"
                chg=float(s.get("change_percent",0) or 0); cc="#22C55E" if chg>=0 else "#EF4444"
                with cols[i%3]:
                    st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:8px;padding:12px;margin-bottom:8px;font-family:DM Mono,monospace;"><div style="font-size:13px;font-weight:500;color:#FFFFFF;margin-bottom:4px;">{emoji} {s["sector_name"]}</div><div style="font-size:13px;color:{cc};font-weight:500;">{chg:+.2f}%</div><div style="font-size:11px;color:#808080;margin-top:3px;">{s.get("verdict","")}</div></div>',unsafe_allow_html=True)
        else:
            st.info("No sector data yet.")
        if st.button("⭐ See Today's Stock Signals →", key="btn_signals", type="primary"):
            st.session_state.current_page="signals"; st.rerun()

    # TRADE GAME LEADERBOARD
    st.markdown('<div class="sec-title">🎮 NGX Trade Game</div>', unsafe_allow_html=True)
    st.markdown("""<div class="sec-intro">Practice stock trading with <strong style="color:#F0A500;">₦1,000,000 in virtual cash</strong> — no real money, all real learning.</div>""", unsafe_allow_html=True)

    board_res = sb.table("leaderboard_snapshots").select("display_name,return_percent,user_id").order("return_percent",desc=True).limit(5).execute()
    board=board_res.data or []; medals=["🥇","🥈","🥉"]
    if board:
        for i,e in enumerate(board[:5]):
            ret=float(e.get("return_percent",0) or 0); dname=(e.get("display_name") or "Investor")[:22]
            medal=medals[i] if i<3 else f"#{i+1}"; is_me=current_user and e.get("user_id")==current_user.id
            ncol="#F0A500" if is_me else "#FFFFFF"; rcol="#22C55E" if ret>=0 else "#EF4444"
            you='<span style="background:#1A1600;border:1px solid #3D2E00;color:#F0A500;font-size:9px;padding:1px 5px;border-radius:3px;margin-left:6px;">YOU</span>' if is_me else ""
            st.markdown(f'<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:14px 18px;margin-bottom:8px;display:flex;align-items:center;gap:12px;font-family:DM Mono,monospace;"><span style="font-size:22px;min-width:30px;">{medal}</span><span style="flex:1;font-size:14px;color:{ncol};">{dname}{you}</span><span style="font-size:16px;font-weight:600;color:{rcol};">{"+"if ret>=0 else ""}{ret:.1f}%</span></div>',unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#0A0A0A;border:1px solid #1F1F1F;border-radius:10px;padding:24px;text-align:center;font-family:DM Mono,monospace;color:#606060;">No traders yet. Be the first to start!</div>',unsafe_allow_html=True)
    if st.button("🎮 Practice Stock Trading →", key="btn_game", type="primary"):
        st.session_state.current_page="game"; st.rerun()

    # LATEST NEWS
    with st.expander("📰  LATEST MARKET NEWS", expanded=False):
        st.markdown("""<div class="sec-intro">🟢 Positive news often precedes price gains. 🔴 Negative may signal pressure. Cross-reference with signal scores.</div>""", unsafe_allow_html=True)
        news_res = sb.table("news").select("headline,url,sentiment,scraped_at").order("scraped_at",desc=True).limit(20).execute()
        if news_res.data:
            seen_h=set(); cnt=0
            for art in news_res.data:
                hk=(art.get("headline") or "")[:60].lower()
                if hk in seen_h or cnt>=12: continue
                seen_h.add(hk); cnt+=1
                sent=art.get("sentiment","neutral")
                if sent=="positive":   dot,st_txt="🟢","Positive — market-friendly"
                elif sent=="negative": dot,st_txt="🔴","Negative — may pressure stocks"
                else:                  dot,st_txt="🟡","Neutral — informational"
                st.markdown(f'<div class="ni"><div style="color:#FFFFFF;font-size:13px;font-weight:500;line-height:1.6;margin-bottom:5px;">{art.get("headline","")}</div><div style="font-size:11px;color:#808080;">{dot} {st_txt}</div></div>',unsafe_allow_html=True)
        else:
            st.info("No news yet. Sources: NGX Pulse, Nairametrics, BusinessDay, TechCabal, Vanguard.")
        col1,col2=st.columns(2)
        with col1:
            if st.button("📅 This Week's Events →", key="btn_cal1", use_container_width=True): st.session_state.current_page="calendar"; st.rerun()
        with col2:
            if st.button("📊 Full Calendar →", key="btn_cal2", type="primary", use_container_width=True): st.session_state.current_page="calendar"; st.rerun()

    if plan=="free":
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("""<div style="background:linear-gradient(135deg,#1A1600,#2A2200);border:1px solid #3D2E00;border-radius:12px;padding:20px 24px;font-family:DM Mono,monospace;"><div style="font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;color:#F0A500;margin-bottom:6px;">🚀 Unlock Full NGX Signal</div><div style="font-size:12px;color:#B0B0B0;margin-bottom:14px;">Instant signals · Price alerts · Telegram · AI chat · Morning &amp; evening briefs</div></div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("Upgrade from ₦3,500/mo →", key="home_upgrade", type="primary"): st.session_state.current_page="settings"; st.rerun()
