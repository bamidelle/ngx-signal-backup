import streamlit as st
from app.utils.supabase_client import get_supabase
from app.components.inline_alert_widget import load_user_alerts, render_alert_widget, _bell_label
from app.utils.webpushr import maybe_push_signal

# ══════════════════════════════════════════════════════════════════════════════
# CACHED DB FETCHERS — signals.py
# Both Supabase calls in render() hit these cached versions.
# Filter changes, pagination, and nav reruns never re-query the database.
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def _sig_fetch_scores() -> list:
    """All signal scores rows. Cached 5 min."""
    from app.utils.supabase_client import get_supabase as _gsb
    try:
        res = _gsb().table("signal_scores") \
            .select("*") \
            .order("score_date", desc=True) \
            .order("stars", desc=True) \
            .limit(500).execute()
        return res.data or []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _sig_fetch_prices() -> list:
    """Latest stock prices for signals page. Cached 5 min."""
    from app.utils.supabase_client import get_supabase as _gsb
    try:
        res = _gsb().table("stock_prices") \
            .select("symbol, price, change_percent, volume") \
            .order("trading_date", desc=True) \
            .limit(500).execute()
        return res.data or []
    except Exception:
        return []


SIGNAL_CONFIG = {
    "STRONG_BUY":     ("#16A34A", "⭐⭐⭐⭐⭐", "STRONG BUY"),
    "BUY":            ("#22C55E", "⭐⭐⭐⭐",   "BUY"),
    "BREAKOUT_WATCH": ("#3B82F6", "⭐⭐⭐⭐",   "BREAKOUT WATCH"),
    "HOLD":           ("#D97706", "⭐⭐⭐",     "HOLD"),
    "CAUTION":        ("#EA580C", "⭐⭐",       "CAUTION"),
    "AVOID":          ("#DC2626", "⭐",         "AVOID"),
}
DEFAULT_CONFIG = ("#6B7280", "⭐⭐⭐", "HOLD")


# ══════════════════════════════════════════════════════════════
# RICH NARRATIVE GENERATOR
# ══════════════════════════════════════════════════════════════

def generate_signal_narrative(
    symbol: str,
    signal_code: str,
    stars: int,
    price: float,
    chg: float,
    volume: int,
    momentum: float,
    vol_score: float,
    composite: float,
    db_reasoning: str = "",
) -> str:
    if db_reasoning and len(db_reasoning.strip()) > 120:
        return db_reasoning.strip()

    if price <= 0:
        return (
            f"No price data has been recorded for {symbol} yet. "
            f"This stock exists on the NGX but the scraper has not yet "
            f"collected its pricing data — this typically happens for "
            f"low-liquidity or recently listed equities. "
            f"It will appear with full analysis on the next successful market data run."
        )

    abs_chg   = abs(chg)
    is_gain   = chg >= 0
    arrow     = "▲" if is_gain else "▼"
    chg_str   = "{:+.2f}".format(chg)
    price_str = "N{:,.2f}".format(price)
    m_pct     = int(min(momentum,  1.0) * 100)
    v_pct     = int(min(vol_score, 1.0) * 100)
    c_pct     = int(min(composite, 1.0) * 100)
    vol_str   = "{:,}".format(volume) if volume > 0 else "N/A"

    if m_pct >= 75:
        mom_line = (
            f"Momentum is strong at {m_pct}% — buyers have been in control "
            f"across recent sessions, with consistent upward pressure on the price."
        )
    elif m_pct >= 50:
        mom_line = (
            f"Momentum reads {m_pct}% — solidly positive. "
            f"The stock has been trending in the right direction, "
            f"with more up-days than down-days in recent trading."
        )
    elif m_pct >= 30:
        mom_line = (
            f"Momentum is moderate at {m_pct}%. "
            f"Price action has been mixed — some sessions up, some flat, "
            f"suggesting the market is still forming a view on {symbol}."
        )
    else:
        mom_line = (
            f"Momentum is weak at {m_pct}%. "
            f"Recent sessions have shown little upward conviction, "
            f"and price has been drifting or declining."
        )

    if v_pct >= 75:
        vol_line = (
            f"Volume is significantly above average ({v_pct}% score) — "
            f"{vol_str} shares changed hands today. "
            f"When volume surges like this, it usually means real money is moving, "
            f"not just noise."
        )
    elif v_pct >= 50:
        vol_line = (
            f"Trading volume is above average ({v_pct}% score, {vol_str} shares). "
            f"More participants than usual are engaging with {symbol} today, "
            f"which adds weight to the current price move."
        )
    elif v_pct >= 25:
        vol_line = (
            f"Volume is around average ({v_pct}% score, {vol_str} shares). "
            f"A normal crowd — enough for the move to be real, "
            f"but not a standout conviction day."
        )
    else:
        vol_line = (
            f"Volume is thin ({v_pct}% score, {vol_str} shares). "
            f"Few participants traded {symbol} today. "
            f"Moves on low volume are easier to reverse — treat with caution."
        )

    if abs_chg >= 9.5 and is_gain:
        move_line = (
            f"{symbol} hit the NGX daily ceiling today, surging {chg_str}% to {price_str}. "
            f"Buyers so dominated that the exchange had to cap the move. "
            f"Something significant — news, earnings, or a large order — triggered this."
        )
    elif abs_chg >= 9.5 and not is_gain:
        move_line = (
            f"{symbol} hit the NGX daily floor, falling {chg_str}% to {price_str}. "
            f"Sellers flooded out and the exchange's circuit breaker kicked in. "
            f"Watch for the catalyst — this level of selling rarely happens without cause."
        )
    elif abs_chg >= 5 and is_gain:
        move_line = (
            f"{symbol} gained {chg_str}% today to close at {price_str} — "
            f"a strong single-session move. "
            f"This kind of gain on the NGX reflects real conviction, "
            f"not just routine trading."
        )
    elif abs_chg >= 5 and not is_gain:
        move_line = (
            f"{symbol} fell {chg_str}% to {price_str} — a sharp pull-back. "
            f"Sellers have taken control and the stock is giving back recent gains. "
            f"The question is whether this is profit-taking or a shift in sentiment."
        )
    elif abs_chg >= 2 and is_gain:
        move_line = (
            f"{symbol} moved up {chg_str}% to {price_str}. "
            f"A meaningful but measured gain — the kind that suggests steady "
            f"buyer interest rather than speculative excitement."
        )
    elif abs_chg >= 2 and not is_gain:
        move_line = (
            f"{symbol} slipped {chg_str}% to {price_str}. "
            f"A moderate dip — sellers nudging the price lower to attract buyers. "
            f"Not a crisis, but worth watching for follow-through."
        )
    else:
        move_line = (
            f"{symbol} barely moved today ({chg_str}%) and is currently priced at {price_str}. "
            f"The market is taking a breath — no strong push in either direction."
        )

    if signal_code == "STRONG_BUY":
        verdict = (
            f"With {stars} stars and a composite score of {c_pct}%, "
            f"this is one of the highest-conviction signals on the NGX today. "
            f"All three scoring dimensions — momentum, volume, and composite — "
            f"are aligned. The risk/reward at current levels is favourable for "
            f"investors with a medium-term horizon."
        )
    elif signal_code == "BUY":
        verdict = (
            f"This is a BUY signal with {stars} stars and a composite score of {c_pct}%. "
            f"The setup is positive: momentum is building and volume is supporting the move. "
            f"Wait for the market to open and confirm the trend before entering."
        )
    elif signal_code == "BREAKOUT_WATCH":
        verdict = (
            f"A BREAKOUT WATCH signal with {stars} stars — the stock is approaching "
            f"a level where a decisive move is likely. "
            f"Composite score sits at {c_pct}%. "
            f"Watch for volume expansion as confirmation: if the next session "
            f"brings higher volume alongside a price push, that is your green light."
        )
    elif signal_code == "HOLD":
        verdict = (
            f"The signal is HOLD ({stars} stars, composite {c_pct}%). "
            f"There is no urgent reason to buy or sell — "
            f"the stock is in a neutral zone. "
            f"Existing holders should stay patient; new buyers should wait "
            f"for a cleaner entry or stronger signal."
        )
    elif signal_code == "CAUTION":
        verdict = (
            f"CAUTION is warranted here ({stars} stars, composite {c_pct}%). "
            f"The data shows deteriorating conditions — weakening momentum "
            f"or declining volume behind recent moves. "
            f"Tighten stop-losses if you hold, and avoid new positions until "
            f"conditions improve."
        )
    elif signal_code == "AVOID":
        verdict = (
            f"This stock is rated AVOID ({stars} star, composite {c_pct}%). "
            f"All scoring dimensions point negative. "
            f"There is no technical case for a new position at this time. "
            f"Let the stock stabilise and build a new base before reconsidering."
        )
    else:
        verdict = (
            f"Composite score: {c_pct}%. "
            f"Review the score breakdown below before making any decision."
        )

    lead = ""
    if db_reasoning and len(db_reasoning.strip()) > 10:
        lead = db_reasoning.strip().rstrip(".") + ". "

    return lead + move_line + " " + mom_line + " " + vol_line + " " + verdict


# ══════════════════════════════════════════════════════════════════════════════
# MARKET SENTIMENT INTELLIGENCE ENGINE v2
# ══════════════════════════════════════════════════════════════════════════════

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta


def _sentiment_cache_key(symbol: str) -> str:
    return f"_mri_{symbol}"

def _cache_is_fresh(symbol: str, ttl_minutes: int = 30) -> bool:
    stamp = st.session_state.get(f"_mri_ts_{symbol}")
    if not stamp:
        return False
    return (datetime.utcnow() - stamp) < timedelta(minutes=ttl_minutes)

def _set_cache(symbol: str, data: dict):
    st.session_state[_sentiment_cache_key(symbol)] = data
    st.session_state[f"_mri_ts_{symbol}"]          = datetime.utcnow()

def _get_cache(symbol: str) -> dict | None:
    return st.session_state.get(_sentiment_cache_key(symbol))


_TICKER_NAME_MAP = {
    "ZENITHBANK": "Zenith Bank Nigeria",
    "GTCO": "Guaranty Trust GTCO Nigeria",
    "ACCESSCORP": "Access Holdings Nigeria",
    "FBNH": "First Bank Nigeria FBN Holdings",
    "UBA": "United Bank Africa Nigeria",
    "MTNN": "MTN Nigeria",
    "AIRTELAFRI": "Airtel Africa Nigeria",
    "DANGCEM": "Dangote Cement Nigeria",
    "BUACEMENT": "BUA Cement Nigeria",
    "NESTLE": "Nestle Nigeria",
    "SEPLAT": "Seplat Energy Nigeria",
    "STANBIC": "Stanbic IBTC Nigeria",
    "WAPCO": "Lafarge Africa Nigeria",
    "NB": "Nigerian Breweries Nigeria",
    "CADBURY": "Cadbury Nigeria",
    "FLOURMILL": "Flour Mills Nigeria",
    "TRANSCORP": "Transcorp Nigeria",
    "FIDELITYBK": "Fidelity Bank Nigeria",
    "STERLING": "Sterling Bank Nigeria",
    "JAIZBANK": "Jaiz Bank Nigeria",
    "OKOMUOIL": "Okomu Oil Nigeria",
    "PRESCO": "Presco Nigeria",
    "TOTAL": "TotalEnergies Nigeria",
    "CONOIL": "Conoil Nigeria",
    "CHAMPION": "Champion Breweries Nigeria",
    "DANGSUGAR": "Dangote Sugar Nigeria",
    "UNILEVER": "Unilever Nigeria",
    "GUINNESS": "Guinness Nigeria",
    "INTBREW": "International Breweries Nigeria",
    "BETAGLASS": "Beta Glass Nigeria",
    "LAFARGE": "Lafarge Africa Nigeria",
    "GEREGU": "Geregu Power Nigeria",
    "TRANSPOWER": "Transmission Company Nigeria",
    "WEMA": "Wema Bank Nigeria",
    "FCMB": "FCMB Group Nigeria First City Monument",
    "ETI": "Ecobank Transnational Nigeria ETI",
    "UNIONBANK": "Union Bank Nigeria",
    "ABBEYMORT": "Abbey Mortgage Bank Nigeria",
    "HONYFLOUR": "Honeywell Flour Mills Nigeria",
    "ROYALEX": "Royal Exchange Nigeria",
    "AIICO": "AIICO Insurance Nigeria",
    "NEM": "NEM Insurance Nigeria",
    "VITAFOAM": "Vitafoam Nigeria",
    "CUTIX": "Cutix Nigeria cable",
    "ELLAHLAKES": "Ellah Lakes Nigeria",
    "LINKASSURE": "Linkage Assurance Nigeria",
}

def _company_search_term(symbol: str) -> str:
    return _TICKER_NAME_MAP.get(symbol.upper(), f"{symbol} Nigeria stock NGX")

def fetch_stock_news(symbol: str, max_items: int = 5) -> list:
    import requests as _req
    search_term = _company_search_term(symbol)
    query = search_term.replace(" ", "+")
    url   = f"https://news.google.com/rss/search?q={query}&hl=en-NG&gl=NG&ceid=NG:en"
    try:
        r = _req.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        root  = ET.fromstring(r.text)
        items = root.findall(".//item")
        news  = []
        now   = datetime.utcnow()
        for item in items[:max_items]:
            title    = (item.findtext("title")   or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            source   = (item.findtext("source")  or "").strip()
            age_hours = 48
            if pub_date:
                for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"]:
                    try:
                        pub_dt    = datetime.strptime(pub_date, fmt).replace(tzinfo=None)
                        age_hours = max(0, int((now - pub_dt).total_seconds() / 3600))
                        break
                    except ValueError:
                        continue
            if title and age_hours <= 168:
                news.append({"title": title, "source": source, "age_hours": age_hours})
        return news
    except Exception:
        return []


def _build_sentiment_prompt(symbol, headlines, signal_code, chg, volume, momentum, vol_score):
    is_gain   = chg >= 0
    direction = f"UP {chg:+.2f}%" if is_gain else f"DOWN {chg:+.2f}%"
    m_pct     = int(min(momentum,  1.0) * 100)
    v_pct     = int(min(vol_score, 1.0) * 100)
    vol_str   = f"{volume:,}" if volume > 0 else "unknown"
    sig_lbl   = signal_code.replace("_", " ")
    headlines_text = "\n".join(
        f"- [{h['age_hours']}h ago | {h['source']}] {h['title']}"
        for h in headlines
    ) if headlines else "No recent headlines found."

    return f"""You are a Nigerian stock market intelligence assistant for NGX Signal.

Stock: {symbol}
Today's move: {direction}
Signal: {sig_lbl}
Momentum score: {m_pct}%
Volume score: {v_pct}% ({vol_str} shares)

Recent headlines:
{headlines_text}

Return ONLY valid JSON with these exact keys:
{{
  "situation": "CONFIRMED_MOVE" | "HYPE" | "QUIET_OPPORTUNITY" | "CONFLICT" | "NO_DATA",
  "line1": "one sentence explaining what's driving the stock",
  "line2": "one sentence adding context or a caveat (can be empty string)",
  "verdict": "plain English verdict for a retail investor",
  "tag_line1": "short phrase for what's happening (max 8 words)",
  "tag_arrow": "short phrase for what to watch (max 6 words)"
}}

No preamble. No markdown. Raw JSON only."""


def _call_ai_for_sentiment(prompt: str) -> dict | None:
    import requests as _req, json as _json

    def make_req(key: str):
        if key.startswith("gsk_"):
            url     = "https://api.groq.com/openai/v1/chat/completions"
            payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "max_tokens": 300, "temperature": 0.3}
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            extract = lambda d: d["choices"][0]["message"]["content"]
        else:
            url     = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            headers = {"Content-Type": "application/json"}
            extract = lambda d: d["candidates"][0]["content"]["parts"][0]["text"]
        return url, payload, headers, extract

    for key_name in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        try:
            key = st.secrets.get(key_name, "")
        except Exception:
            key = ""
        if not key:
            continue
        try:
            url, payload, headers, extract = make_req(key)
            r = _req.post(url, json=payload, headers=headers, timeout=20)
            if r.status_code != 200:
                continue
            raw  = extract(r.json()).strip().replace("```json", "").replace("```", "").strip()
            data = _json.loads(raw)
            if {"situation","line1","line2","verdict","tag_line1","tag_arrow"}.issubset(data.keys()):
                return data
        except Exception:
            continue
    return None


def _fallback_sentiment(symbol, signal_code, chg, vol_score, momentum, composite, volume):
    is_gain = chg >= 0
    abs_chg = abs(chg)
    no_data = (vol_score < 0.10 and composite < 0.15 and volume < 100)
    if no_data:
        return {"situation":"NO_DATA","line1":"No recent news or strong public reaction found for this stock.","line2":"","verdict":"Rely on the score breakdown above — no news signal available.","tag_line1":"No recent news found","tag_arrow":"Technical signals only","color":"#4B5563"}
    price_direction = 0.65 if chg >= 3 else 0.55 if chg >= 0.5 else 0.45 if chg > -0.5 else 0.3
    market_score    = momentum * 0.5 + vol_score * 0.3 + price_direction * 0.2
    market_strong   = market_score >= 0.55 and (chg >= 1.0 or momentum >= 0.55)
    if   abs_chg >= 5 and is_gain:    move_word = "rising sharply"
    elif abs_chg >= 2 and is_gain:    move_word = "moving up steadily"
    elif abs_chg >= 0.5 and is_gain:  move_word = "edging higher"
    elif abs_chg < 0.5:               move_word = "barely moving"
    elif abs_chg >= 5:                move_word = "falling sharply"
    elif abs_chg >= 2:                move_word = "dropping noticeably"
    else:                             move_word = "slipping lower"
    vol_word = "strong trading activity" if vol_score >= 0.65 else "above-average trading activity" if vol_score >= 0.40 else "quiet trading activity"
    if market_strong and is_gain:
        return {"situation":"QUIET_OPPORTUNITY","line1":f"No major news found — but {symbol} is {move_word} on {vol_word}.","line2":"The buying pressure looks real even without a news catalyst.","verdict":"Price is moving on its own strength — watch for a news trigger.","tag_line1":"Moving on market strength, no news","tag_arrow":"Under-the-radar buying","color":"#A78BFA"}
    elif not is_gain:
        return {"situation":"CONFIRMED_MOVE","line1":f"No major news found, but {symbol} is {move_word}.","line2":f"Selling pressure appears real — {vol_word} behind the drop.","verdict":"Price is dropping without clear news reason — use caution.","tag_line1":"Dropping without a clear news reason","tag_arrow":"Proceed with caution","color":"#EF4444"}
    else:
        return {"situation":"QUIET_OPPORTUNITY","line1":f"No major news found for {symbol} today.","line2":f"The price is {move_word} on {vol_word}.","verdict":"Moving quietly — no news catalyst yet. Watch for one.","tag_line1":"Quiet move — no news found","tag_arrow":"No news trigger yet","color":"#D97706"}


_SITUATION_COLOR = {"CONFIRMED_MOVE": None, "HYPE": "#F0A500", "QUIET_OPPORTUNITY": "#A78BFA", "CONFLICT": "#3B82F6", "NO_DATA": "#4B5563"}


def generate_market_reality_block(symbol: str, signal_code: str, chg: float, volume: int, momentum: float, vol_score: float, composite: float, stars: int) -> dict:
    if _cache_is_fresh(symbol):
        cached = _get_cache(symbol)
        if cached:
            return cached

    headlines = fetch_stock_news(symbol, max_items=5)
    result = None
    prompt  = _build_sentiment_prompt(symbol, headlines, signal_code, chg, volume, momentum, vol_score)
    ai_data = _call_ai_for_sentiment(prompt)

    if ai_data:
        situation = ai_data.get("situation", "NO_DATA")
        is_gain   = chg >= 0
        color     = ("#22C55E" if is_gain else "#EF4444") if situation == "CONFIRMED_MOVE" else _SITUATION_COLOR.get(situation, "#4B5563")
        result = {
            "situation":  situation,
            "line1":      ai_data.get("line1",     ""),
            "line2":      ai_data.get("line2",     ""),
            "verdict":    ai_data.get("verdict",   ""),
            "tag_line1":  ai_data.get("tag_line1", ""),
            "tag_arrow":  ai_data.get("tag_arrow", ""),
            "color":      color,
            "news_count": len(headlines),
            "ai_powered": True,
        }

    if not result:
        result = _fallback_sentiment(symbol, signal_code, chg, vol_score, momentum, composite, volume)
        result["news_count"] = len(headlines)
        result["ai_powered"] = False

    _set_cache(symbol, result)
    return result


def render_market_reality_html(mri: dict, accent: str) -> str:
    situation  = mri["situation"]
    line1      = mri["line1"]
    line2      = mri["line2"]
    verdict    = mri["verdict"]
    color      = mri["color"]
    news_count = mri.get("news_count", 0)
    ai_powered = mri.get("ai_powered", False)

    badge_copy = {
        "CONFIRMED_MOVE":    ("✅", "Confirmed Move",   color),
        "HYPE":              ("⚠️", "Hype Alert",        "#F0A500"),
        "QUIET_OPPORTUNITY": ("🔍", "Quiet Opportunity", "#A78BFA"),
        "CONFLICT":          ("⚖️", "Mixed Signals",      "#3B82F6"),
        "NO_DATA":           ("—",  "No Strong Data",    "#4B5563"),
    }
    b_icon, b_label, b_color = badge_copy.get(situation, ("—", situation, "#4B5563"))

    if ai_powered and news_count > 0:
        source_html = (
            f'<div class="mri-source">'
            f'📰 Based on {news_count} recent headline{"s" if news_count != 1 else ""} · AI-analysed'
            f'</div>'
        )
    elif ai_powered and news_count == 0:
        source_html = '<div class="mri-source">🤖 AI analysis · No recent headlines found</div>'
    else:
        source_html = '<div class="mri-source">📊 Based on market signals · News unavailable</div>'

    if situation == "NO_DATA":
        return f"""
<div class="mri-wrap">
  <div class="mri-header">
    <span class="mri-title">What's Really Driving This</span>
    <span class="mri-badge" style="background:{b_color}18;border-color:{b_color}44;color:{b_color};">{b_icon} {b_label}</span>
  </div>
  <div class="mri-no-data">{line1}</div>
  {source_html}
</div>"""

    line2_html = f'<div class="mri-line">{line2}</div>' if line2 else ""

    return f"""
<div class="mri-wrap">
  <div class="mri-header">
    <span class="mri-title">What's Really Driving This</span>
    <span class="mri-badge" style="background:{b_color}18;border-color:{b_color}44;color:{b_color};">{b_icon} {b_label}</span>
  </div>
  <div class="mri-body">
    <div class="mri-line">{line1}</div>
    {line2_html}
    <div class="mri-verdict">
      <span class="mri-verdict-label">Simple verdict:</span>
      <span class="mri-verdict-text" style="color:{color};">{verdict}</span>
    </div>
  </div>
  {source_html}
</div>"""


MRI_CSS = """
  .mri-wrap {
    background: #080A0D;
    border: 1px solid #1E2229;
    border-left: 3px solid #F0A500;
    border-radius: 8px;
    padding: 10px 13px;
    margin: 8px 0;
  }
  .mri-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .mri-title {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #4B5563;
    font-weight: 600;
  }
  .mri-badge {
    font-size: 9px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid;
    letter-spacing: 0.04em;
    white-space: nowrap;
  }
  .mri-body {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .mri-line {
    font-size: 11px;
    color: #C8C4BC;
    line-height: 1.6;
  }
  .mri-line::before {
    content: '· ';
    color: #4B5563;
  }
  .mri-verdict {
    margin-top: 6px;
    padding-top: 7px;
    border-top: 1px solid #1A1D24;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .mri-verdict-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #4B5563;
  }
  .mri-verdict-text {
    font-size: 12px;
    font-weight: 600;
    line-height: 1.5;
  }
  .mri-no-data {
    font-size: 11px;
    color: #4B5563;
    line-height: 1.6;
    font-style: italic;
  }
  .mri-source {
    font-size: 9px;
    color: #374151;
    margin-top: 7px;
    padding-top: 5px;
    border-top: 1px solid #12151A;
    letter-spacing: 0.02em;
  }
"""


def generate_trending_sentiment_tag(
    symbol:    str,
    signal_code: str,
    chg:       float,
    volume:    int,
    momentum:  float,
    vol_score: float,
    composite: float,
    stars:     int,
) -> str:
    mri        = generate_market_reality_block(
        symbol=symbol, signal_code=signal_code,
        chg=chg, volume=volume, momentum=momentum,
        vol_score=vol_score, composite=composite, stars=stars,
    )
    color      = mri["color"]
    tag1       = mri["tag_line1"]
    tag_arr    = mri["tag_arrow"]
    news_count = mri.get("news_count", 0)
    ai_powered = mri.get("ai_powered", False)

    source_note = (
        f'<span style="color:#374151;font-size:9px;"> · {news_count} headline{"s" if news_count!=1 else ""}</span>'
        if ai_powered and news_count > 0 else ""
    )

    return (
        f'<div style="font-family:\'DM Mono\',monospace;font-size:10px;'
        f'color:#9CA3AF;line-height:1.6;margin-top:6px;padding-top:6px;'
        f'border-top:1px solid #1A1D24;">'
        f'{tag1}<br>'
        f'<span style="color:{color};font-weight:600;">→ {tag_arr}</span>'
        f'{source_note}'
        f'</div>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# LOCKED VERDICT GATE — renders the blurred verdict box for free/visitor users
# This is the core of TIER 1 FIX 1: gate the signal verdict, show scores free
# ══════════════════════════════════════════════════════════════════════════════

def _render_locked_verdict_html(symbol: str, accent: str, stars_display: str) -> str:
    """
    Returns HTML for the blurred verdict gate shown to free/visitor users.
    Shows: blurred signal badge + stars + a compelling free trial CTA.
    The blur proves something exists without revealing what it is.
    """
    return f"""
<div class="verdict-gate">
  <!-- Blurred ghost of the actual verdict — proves it exists -->
  <div class="verdict-ghost">
    <div class="ghost-badge" style="background:{accent}33;border:1px solid {accent}55;">
      <span style="filter:blur(5px);user-select:none;pointer-events:none;color:{accent};font-size:11px;font-weight:700;">STRONG BUY</span>
    </div>
    <div class="ghost-stars" style="filter:blur(3px);user-select:none;pointer-events:none;font-size:16px;">⭐⭐⭐⭐⭐</div>
  </div>
  <!-- Lock overlay -->
  <div class="gate-lock">
    <div class="gate-lock-icon">🔒</div>
    <div class="gate-lock-text">Signal Ready — direction &amp; strength locked</div>
  </div>
  <!-- CTA -->
  <a href="#" class="gate-cta">Start Free 14-Day Trial →</a>
  <div class="gate-sub">No card required · Cancel any time</div>
</div>"""


def render():
    sb = get_supabase()

    profile  = st.session_state.get("profile", {})
    plan     = (profile.get("plan") or "free").lower().strip()
    user     = st.session_state.get("user")
    alerts_by_symbol = load_user_alerts(sb, user)

    TIER_ORDER = ["visitor", "free", "trial", "starter", "trader", "pro"]
    PAID_TIERS = {"starter", "trader", "pro", "trial"}
    if not user:
        tier = "visitor"
    elif plan in TIER_ORDER:
        tier = plan
    else:
        tier = "free"
    is_paid       = tier in PAID_TIERS
    show_prices   = is_paid
    show_full_nar = is_paid
    show_mri      = is_paid
    show_scores   = True
    STARTER_RANK  = TIER_ORDER.index("starter")
    show_conf_lbl = TIER_ORDER.index(tier) >= STARTER_RANK

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
    .sig-header { font-family:'Syne',sans-serif; font-size:22px; font-weight:800; color:#E8E2D4; margin-bottom:4px; }
    .sig-sub { font-family:'DM Mono',monospace; font-size:11px; color:#4B5563; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:12px; }
    .sig-count { font-family:'DM Mono',monospace; font-size:12px; color:#6B7280; margin-bottom:12px; }
    .sig-seo-intro { font-family:'DM Mono',monospace; font-size:12px; color:#6B7280; line-height:1.7;
                     background:#0A0A0A; border:1px solid #1F1F1F; border-radius:8px;
                     padding:10px 14px; margin-bottom:14px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="sig-header">⭐ NGX Signal Scores</div>
    <div class="sig-sub">AI-powered NGX stock signals · All 144+ listed equities · Updated daily</div>
    <div class="sig-seo-intro">
      Daily AI-generated momentum, volume and composite scores for every stock on the Nigerian Exchange (NGX).
      Signals cover Banking (ZENITHBANK, GTCO, UBA, ACCESSCORP), Telecoms (MTNN, AIRTELAFRI),
      Consumer Goods, Cement, Oil &amp; Gas, Insurance and all other NGX sectors.
      <strong style="color:#F0A500;">See the scores for free.
      Start a free trial to unlock signal direction, entry price, target and stop-loss.</strong>
    </div>
    """, unsafe_allow_html=True)

    # ── FILTERS ──────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_signal = st.selectbox(
            "Filter by signal",
            ["All", "STRONG BUY", "BUY", "BREAKOUT WATCH",
             "HOLD", "CAUTION", "AVOID"],
            key="sig_filter"
        )
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Signal strength ↓", "Best % gain today",
             "Worst % loss today", "Highest volume", "Symbol A–Z"],
            key="sig_sort"
        )
    with col3:
        search = st.text_input(
            "Search symbol",
            placeholder="e.g. GTCO",
            key="sig_search"
        ).upper().strip()

    # ── FETCH (CACHED — no DB hit on filter/sort reruns) ──────────────────────
    scores_data = _sig_fetch_scores()
    prices_data = _sig_fetch_prices()

    price_map = {}
    for p in prices_data:
        if p["symbol"] not in price_map:
            price_map[p["symbol"]] = p

    seen = set()
    all_scores = []
    for s in scores_data:
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            all_scores.append(s)

    label_to_code = {
        "STRONG BUY": "STRONG_BUY",
        "BUY": "BUY",
        "BREAKOUT WATCH": "BREAKOUT_WATCH",
        "HOLD": "HOLD",
        "CAUTION": "CAUTION",
        "AVOID": "AVOID",
    }

    # ── APPLY FILTERS ─────────────────────────────────
    filtered = all_scores[:]

    if filter_signal != "All":
        code = label_to_code.get(filter_signal, filter_signal)
        filtered = [
            s for s in filtered
            if s.get("signal", "").upper().replace(" ", "_") == code
            or s.get("signal", "") == filter_signal
        ]

    if search:
        filtered = [s for s in filtered if search in s.get("symbol", "")]

    if sort_by == "Best % gain today":
        filtered = sorted(
            filtered,
            key=lambda x: float(price_map.get(x["symbol"], {}).get("change_percent", 0) or 0),
            reverse=True
        )
    elif sort_by == "Worst % loss today":
        filtered = sorted(
            filtered,
            key=lambda x: float(price_map.get(x["symbol"], {}).get("change_percent", 0) or 0)
        )
    elif sort_by == "Highest volume":
        filtered = sorted(
            filtered,
            key=lambda x: int(price_map.get(x["symbol"], {}).get("volume", 0) or 0),
            reverse=True
        )
    elif sort_by == "Symbol A–Z":
        filtered = sorted(filtered, key=lambda x: x.get("symbol", ""))

    # ── DISTRIBUTION BAR ──────────────────────────────
    if all_scores:
        color_map = {
            "STRONG_BUY": "#16A34A", "STRONG BUY": "#16A34A",
            "BUY": "#22C55E",
            "BREAKOUT_WATCH": "#3B82F6", "BREAKOUT WATCH": "#3B82F6",
            "HOLD": "#D97706", "CAUTION": "#EA580C", "AVOID": "#DC2626",
        }
        dist = {}
        for s in all_scores:
            sig = s.get("signal", "HOLD")
            dist[sig] = dist.get(sig, 0) + 1

        parts = []
        for sig, cnt in sorted(dist.items(), key=lambda x: -x[1]):
            c = color_map.get(sig, "#6B7280")
            parts.append(
                f"<span style='color:{c};font-weight:600;'>{sig}</span>"
                f" <span style='color:#4B5563;'>{cnt}</span>"
            )
        st.markdown(
            "<div style='font-family:DM Mono,monospace;font-size:12px;"
            "margin-bottom:16px;display:flex;gap:16px;flex-wrap:wrap;'>"
            + " &nbsp;·&nbsp; ".join(parts) + "</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        f"<div class='sig-count'>Showing "
        f"<strong style='color:#F0A500;'>{len(filtered)}</strong> stocks</div>",
        unsafe_allow_html=True
    )

    if not filtered:
        st.info("No signals match your filter.")
        return

    # ── TIER 1 FIX 1+3: Gate notice with FREE TRIAL language ─────────────────
    if not is_paid:
        st.components.v1.html(f"""
<!DOCTYPE html><html>
<head>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:transparent;font-family:'DM Mono',monospace;overflow:hidden;padding:0 0 8px 0;}}
.gate-banner{{
  background:linear-gradient(135deg,#0D0A00,#0A0A0A);
  border:1px solid rgba(240,165,0,.3);
  border-left:4px solid #F0A500;
  border-radius:10px;
  padding:14px 18px;
  display:flex;align-items:center;gap:14px;flex-wrap:wrap;
}}
.gate-icon{{font-size:18px;flex-shrink:0;}}
.gate-body{{flex:1;min-width:180px;}}
.gate-title{{font-size:12px;color:#E8E2D4;margin-bottom:3px;line-height:1.5;}}
.gate-title strong{{color:#F0A500;}}
.gate-sub{{font-size:10px;color:#4B5563;}}
.gate-btn{{
  background:#F0A500;color:#000;
  font-size:11px;font-weight:700;
  padding:9px 18px;border-radius:8px;
  text-decoration:none;white-space:nowrap;
  font-family:'Space Grotesk',sans-serif;
  letter-spacing:.02em;flex-shrink:0;
  display:inline-block;
}}
@media(max-width:480px){{
  .gate-banner{{flex-direction:column;align-items:flex-start;gap:8px;}}
  .gate-btn{{width:100%;text-align:center;}}
}}
</style>
</head>
<body>
<div class="gate-banner">
  <div class="gate-icon">📊</div>
  <div class="gate-body">
    <div class="gate-title">
      <strong>Score bars, sector &amp; price data are free.</strong>
      Signal direction, entry price, target &amp; stop-loss require a free trial.
    </div>
    <div class="gate-sub">14 days free · No credit card required</div>
  </div>
  <a href="#" class="gate-btn">Start Free 14-Day Trial →</a>
</div>
</body></html>
""", height=82, scrolling=False)

    # ── SIGNAL CARDS with TIER 2 FIX 5: Alternating reveal pattern ────────────
    # Pattern: 1 open → 3 blurred → 1 open → 3 blurred → ...
    # Position 0 = open (trust builder), positions 1-3 = blurred (FOMO), position 4 = open, etc.
    REVEAL_PATTERN = [True, False, False, False, True, False, False, False]  # repeating

    for card_idx, s in enumerate(filtered):
        # Alternating reveal for free users: position in cycle determines visibility
        is_open_card = REVEAL_PATTERN[card_idx % len(REVEAL_PATTERN)] if not is_paid else True

        symbol     = s.get("symbol", "")
        stars_num  = int(s.get("stars", 3))
        signal_raw = s.get("signal", "HOLD")
        reasoning  = s.get("reasoning", "")
        score_date = s.get("score_date", "")

        signal_code = signal_raw.upper().replace(" ", "_")
        cfg = SIGNAL_CONFIG.get(signal_code, DEFAULT_CONFIG)
        accent, stars_display, label = cfg

        price_data = price_map.get(symbol, {})
        price  = float(price_data.get("price", 0) or 0)
        chg    = float(price_data.get("change_percent", 0) or 0)
        volume = int(price_data.get("volume", 0) or 0)
        chg_color = "#22C55E" if chg >= 0 else "#EF4444"
        arrow     = "▲" if chg >= 0 else "▼"

        momentum  = float(s.get("momentum_score", 0) or 0)
        vol_score = float(s.get("volume_score", 0) or 0)
        composite = float(s.get("news_score", 0) or 0)

        db_short = (s.get("reasoning", "") or "").strip()
        db_short_display = db_short if len(db_short) <= 140 else db_short[:137] + "…"

        rich_narrative = generate_signal_narrative(
            symbol       = symbol,
            signal_code  = signal_code,
            stars        = stars_num,
            price        = price,
            chg          = chg,
            volume       = volume,
            momentum     = momentum,
            vol_score    = vol_score,
            composite    = composite,
            db_reasoning = db_short,
        )

        maybe_push_signal(
            symbol      = symbol,
            signal_code = signal_code,
            narrative   = rich_narrative,
            price       = price,
            chg         = chg,
        )

        # Entry / Target / Stop Loss — paid plans only
        entry_price = target_price = stop_loss = potential = None
        if show_prices and signal_code in ("STRONG_BUY", "BUY", "BREAKOUT_WATCH") and price > 0:
            entry_price  = round(price * 1.002, 2)
            multiplier   = 1.12 if stars_num >= 5 else 1.08 if stars_num >= 4 else 1.06
            target_price = round(price * multiplier, 2)
            stop_loss    = round(price * 0.95, 2)
            potential    = round(((target_price - entry_price) / entry_price) * 100, 1)

        price_display = f"N{price:,.2f}" if price > 0 else "No price data"
        vol_display   = f"Vol: {volume:,}" if volume > 0 else ""

        m_pct = int(min(momentum,  1.0) * 100)
        v_pct = int(min(vol_score, 1.0) * 100)
        c_pct = int(min(composite, 1.0) * 100)

        # For free/visitor users:
        # - Open cards (trust builders): show score bars + 1-sentence snippet, reveal the label
        # - Blurred cards (FOMO): show score bars + snippet, but gate the verdict/label
        show_verdict = is_paid or is_open_card

        if not show_full_nar:
            _first_sent = rich_narrative.split(". ")[0] + "." if ". " in rich_narrative else rich_narrative[:120] + "…"
            narrative_display = _first_sent
        else:
            narrative_display = rich_narrative

        # MRI block — paid only
        if show_mri:
            mri_data     = generate_market_reality_block(
                symbol=symbol, signal_code=signal_code,
                chg=chg, volume=volume, momentum=momentum,
                vol_score=vol_score, composite=composite, stars=stars_num,
            )
            mri_html     = render_market_reality_html(mri_data, accent)
            mri_text_len = len(mri_data["line1"]) + len(mri_data["line2"]) + len(mri_data["verdict"])
        else:
            mri_html     = ""
            mri_text_len = 0

        # Dynamic height
        CHARS_PER_LINE = 55
        def est_height(text: str, font_px: int = 11, lh: float = 1.75) -> int:
            if not text:
                return 0
            lines = max(1, len(text) // CHARS_PER_LINE + text.count("\n"))
            return int(lines * font_px * lh) + 10

        h_badge      = 30
        h_db_short   = est_height(db_short_display, 11, 1.55) if db_short_display else 0
        h_action     = 90 if entry_price else 0
        h_scores     = 70
        h_mri        = est_height(mri_text_len * "x", 11, 1.6) + 60 if show_mri else 0
        h_narrative  = est_height(narrative_display, 11, 1.75)
        h_verdict_gate = 100 if not show_verdict else 0
        h_disclaimer = 24
        h_padding    = 40

        card_height = (
            h_badge + h_db_short + h_action +
            h_scores + h_mri + h_narrative + h_verdict_gate + h_disclaimer + h_padding
        )
        card_height = max(320, min(card_height, 1400))

        # Build expander label — for blurred cards, hide the verdict label from non-paid
        if show_verdict:
            expander_label = (
                f"{stars_display}  {symbol}  —  {label}  ·  {price_display}"
                f"  {_bell_label(symbol, alerts_by_symbol)}"
            )
        else:
            # Show stock name + score bars summary, hide the label
            expander_label = (
                f"📊  {symbol}  ·  {price_display}  ·  {arrow} {abs(chg):.2f}%  "
                f"·  Momentum {m_pct}%  ·  🔒 Signal Ready"
                f"  {_bell_label(symbol, alerts_by_symbol)}"
            )

        with st.expander(expander_label, expanded=False):
            st.components.v1.html(f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@600;700;800&display=swap"
                  rel="stylesheet">
            <style>
              *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
              html {{ font-size:13px; }}
              body {{
                background: transparent;
                font-family: 'DM Mono', monospace;
                color: #E8E2D4;
                overflow-x: hidden;
                overflow-y: visible;
                padding: 4px 0 10px 0;
              }}

              /* ── Badge row ── */
              .badge-row {{
                display:flex; align-items:center; gap:8px;
                flex-wrap:wrap; margin-bottom:8px;
              }}
              .signal-badge {{
                font-size:10px; font-weight:700;
                padding:3px 10px; border-radius:20px;
                text-transform:uppercase; letter-spacing:0.05em;
                color:#fff; background:{accent};
              }}
              .chg-val {{ font-size:12px; font-weight:600; color:{chg_color}; }}
              .vol-val {{ font-size:10px; color:#4B5563; }}
              .date-val {{ font-size:10px; color:#374151; margin-left:auto; }}

              /* ── Short DB text ── */
              .db-text {{
                font-size:11px; color:#9CA3AF; line-height:1.55;
                margin-bottom:8px;
              }}

              /* ── Action grid ── */
              .action-grid {{
                display:grid; grid-template-columns:repeat(3,1fr);
                gap:6px; margin:8px 0;
              }}
              .action-cell {{
                border-radius:7px; padding:9px 6px; text-align:center;
              }}
              .action-lbl {{
                font-size:9px; text-transform:uppercase;
                letter-spacing:0.07em; margin-bottom:4px; color:#4B5563;
              }}
              .action-val {{ font-size:15px; font-weight:500; }}
              .action-sub {{ font-size:10px; margin-top:2px; }}

              /* ── Score bars ── */
              .scores {{
                margin:8px 0 0 0; padding-top:8px;
                border-top:1px solid #1E2229;
              }}
              .scores-title {{
                font-size:9px; color:#4B5563; text-transform:uppercase;
                letter-spacing:0.08em; margin-bottom:7px;
              }}
              .scores-grid {{
                display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;
              }}
              .score-lbl {{ font-size:9px; color:#4B5563; margin-bottom:4px; }}
              .bar-track {{
                background:#1A1D24; border-radius:4px;
                height:4px; margin-bottom:2px;
              }}
              .bar-fill {{ border-radius:4px; height:4px; }}
              .score-num {{ font-size:10px; }}

              /* ── Rich narrative ── */
              .narrative {{
                background:#0A0C0F; border:1px solid #1E2229;
                border-left:3px solid {accent}; border-radius:7px;
                padding:10px 12px; font-size:11px; color:#E8E2D4;
                line-height:1.75; margin-top:8px;
              }}

              /* ── TIER 1 FIX 1: Verdict Gate (blurred verdict for free users) ── */
              .verdict-gate {{
                background:linear-gradient(135deg,#0D0A00 0%,#090A0D 100%);
                border:1px solid rgba(240,165,0,.2);
                border-radius:10px;
                padding:14px 16px;
                margin:10px 0;
                text-align:center;
                position:relative;
                overflow:hidden;
              }}
              .verdict-gate::before {{
                content:'';
                position:absolute;top:0;left:0;right:0;
                height:1px;
                background:linear-gradient(90deg,transparent,{accent}66,transparent);
              }}
              .verdict-ghost {{
                display:flex;align-items:center;justify-content:center;gap:10px;
                margin-bottom:10px;
              }}
              .ghost-badge {{
                padding:4px 14px;border-radius:20px;
                display:inline-flex;align-items:center;
              }}
              .gate-lock {{
                display:flex;align-items:center;justify-content:center;gap:6px;
                margin-bottom:10px;
              }}
              .gate-lock-icon {{ font-size:14px; }}
              .gate-lock-text {{
                font-size:11px;color:#6B7280;
              }}
              .gate-cta {{
                display:inline-block;
                background:{accent};
                color:#000;
                font-size:12px;font-weight:700;
                padding:10px 22px;border-radius:8px;
                text-decoration:none;
                font-family:'Space Grotesk',sans-serif;
                letter-spacing:.02em;
                cursor:pointer;
                transition:opacity .15s;
              }}
              .gate-cta:hover{{ opacity:.85; }}
              .gate-sub {{
                font-size:9px;color:#374151;margin-top:7px;
              }}

              /* ── Disclaimer ── */
              .disclaimer {{
                font-size:9px; color:#374151; margin-top:8px;
                padding-top:6px; border-top:1px solid #1A1D24;
              }}

              @media (max-width:400px) {{
                html {{ font-size:12px; }}
                .action-val {{ font-size:13px; }}
                .narrative {{ font-size:10.5px; line-height:1.7; }}
                .gate-cta {{ font-size:11px; padding:9px 18px; width:100%; }}
              }}

              {MRI_CSS}
            </style>
            <script>
              function resize() {{
                var h = document.body.scrollHeight + 16;
                window.parent.postMessage({{type:'streamlit:setFrameHeight', height:h}}, '*');
              }}
              window.addEventListener('load', function(){{ resize(); setTimeout(resize, 600); }});
              new MutationObserver(resize).observe(document.body, {{subtree:true, childList:true}});
            </script>
            </head>
            <body>

              <!-- 1. Badge + change row — only shown on open/paid cards -->
              {'<div class="badge-row"><span class="signal-badge">' + label + '</span><span class="chg-val">' + arrow + ' ' + str(abs(chg)) + '% today</span>' + ('<span class="vol-val">' + vol_display + '</span>' if vol_display else '') + '<span class="date-val">' + score_date + '</span></div>' if show_verdict else '<div class="badge-row"><span class="chg-val">' + arrow + ' ' + f"{abs(chg):.2f}%" + ' today</span>' + ('<span class="vol-val">' + vol_display + '</span>' if vol_display else '') + '<span class="date-val">' + score_date + '</span></div>'}

              <!-- 2. Short DB text -->
              {f'<div class="db-text">{db_short_display}</div>' if db_short_display and show_verdict else ''}

              <!-- 3. Entry / Target / Stop Loss (paid only) -->
              {f'''<div class="action-grid">
                <div class="action-cell" style="background:#001A00;border:1px solid #003D00;">
                  <div class="action-lbl">&#10003; Entry</div>
                  <div class="action-val" style="color:#22C55E;">N{entry_price:,.2f}</div>
                </div>
                <div class="action-cell" style="background:#001A1A;border:1px solid #003D3D;">
                  <div class="action-lbl">&#127919; Target</div>
                  <div class="action-val" style="color:#22D3EE;">N{target_price:,.2f}</div>
                  <div class="action-sub" style="color:#22D3EE;">+{potential}%</div>
                </div>
                <div class="action-cell" style="background:#1A0000;border:1px solid #3D0000;">
                  <div class="action-lbl">&#128721; Stop Loss</div>
                  <div class="action-val" style="color:#EF4444;">N{stop_loss:,.2f}</div>
                </div>
              </div>''' if entry_price and target_price and stop_loss else ''}

              <!-- 4. Score bars (always visible — free users can see these) -->
              <div class="scores">
                <div class="scores-title">Score Breakdown — Free to view</div>
                <div class="scores-grid">
                  <div>
                    <div class="score-lbl">Momentum</div>
                    <div class="bar-track">
                      <div class="bar-fill" style="background:#F0A500;width:{m_pct}%;"></div>
                    </div>
                    <div class="score-num" style="color:#F0A500;">{m_pct}%</div>
                  </div>
                  <div>
                    <div class="score-lbl">Volume</div>
                    <div class="bar-track">
                      <div class="bar-fill" style="background:#22D3EE;width:{v_pct}%;"></div>
                    </div>
                    <div class="score-num" style="color:#22D3EE;">{v_pct}%</div>
                  </div>
                  <div>
                    <div class="score-lbl">Composite</div>
                    <div class="bar-track">
                      <div class="bar-fill" style="background:#A78BFA;width:{c_pct}%;"></div>
                    </div>
                    <div class="score-num" style="color:#A78BFA;">{c_pct}%</div>
                  </div>
                </div>
              </div>

              <!-- 5. Market Reality Intelligence block (paid only) -->
              {mri_html}

              <!-- 6. TIER 1 FIX 1: Verdict gate OR full narrative -->
              {'<div class="narrative">' + narrative_display + '</div>' if show_verdict else _render_locked_verdict_html(symbol, accent, stars_display)}

              <!-- 7. Upgrade lock for free/visitor on open cards (softer CTA) -->
              {'<div style="background:#0C0A00;border:1px solid rgba(240,165,0,.3);border-radius:8px;padding:10px 12px;margin-top:8px;text-align:center;font-family:DM Mono,monospace;font-size:11px;color:#9CA3AF;">🔒 <strong style="color:#F0A500;">Start Free 14-Day Trial:</strong> entry price · target · stop-loss · full AI analysis · Market Intelligence</div>' if not is_paid and show_verdict else ''}

              <!-- 8. Disclaimer -->
              <div class="disclaimer">
                &#9888;&#65039; Signal scores are educational only —
                not financial advice. Always do your own research.
              </div>

            </body>
            </html>
            """, height=card_height, scrolling=True)

            if is_paid:
                render_alert_widget(sb, user, plan, symbol, price, alerts_by_symbol)

    # ── SEO FOOTER ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="font-family:DM Mono,monospace;font-size:11px;color:#374151;
                margin-top:24px;padding-top:12px;border-top:1px solid #1E2229;line-height:1.8;">
      <strong style="color:#4B5563;">About NGX Signal Scores:</strong>
      Daily AI-generated momentum, volume and composite scores for all {len(all_scores)} stocks listed on the
      Nigerian Exchange (NGX). Each signal is scored across three dimensions — momentum, volume
      and composite market data — and updated after every trading session.
      Signals are available for Banking stocks (ZENITHBANK BUY signal, GTCO signal today,
      UBA signal, ACCESSCORP, FBNH), Telecoms (MTNN signal, AIRTELAFRI),
      Consumer Goods (NESTLE, DANGSUGAR, GUINNESS), Cement (DANGCEM, BUACEMENT, WAPCO),
      Oil &amp; Gas (SEPLAT, TOTAL, CONOIL), Insurance, Agriculture and all other NGX sectors.
      Free users see score bars, price data and sector information.
      Start a free 14-day trial to unlock signal direction (BUY/HOLD/AVOID),
      entry prices, targets, stop-losses and full AI analysis.
      All signals are educational only — not financial advice. Always do your own research
      before investing.
    </div>
    """, unsafe_allow_html=True)
