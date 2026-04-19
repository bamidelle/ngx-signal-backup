"""
NGX Signal — Global Pulse  v1.0
================================
Watches 4 global signals every morning and translates them into plain-English
Nigerian-context intelligence.

Signals tracked:
  1. Brent Crude Oil price + % change   (Yahoo Finance — free, no key)
  2. US Dollar strength (DXY index)     (Yahoo Finance — free, no key)
  3. Bitcoin price + % change           (CoinGecko — free, no key)
  4. Global Fear/Greed mood score       (CNN Fear & Greed — free)

AI Summary chain:
  Layer 1 — Gemini 1.5 Flash (primary)
  Layer 2 — Groq / Llama-3.3-70b (fallback)
  Layer 3 — News RSS headlines for context (Reuters, FT — free)
  Layer 4 — Strong deterministic rules (always works, zero cost)

Tier access:
  • Four tiles + direction arrows      → ALL tiers (visitor, free, trial, paid)
  • Naira impact labels + summary      → Paid only (trial, starter, trader, pro)
  • Silent AI injection into Ask AI    → All tiers that can use Ask AI

Caching:
  Market data  → 30-minute TTL  (external APIs, rate-limit safe)
  AI summary   → daily seed key (one AI call per day per user session)
  News context → 60-minute TTL
"""

import streamlit as st
import requests
import json
from datetime import datetime, date, timedelta, timezone

# ── Timezone helpers (mirrors home.py pattern) ────────────────────────────────
try:
    import pytz
    _WAT = pytz.timezone("Africa/Lagos")
    def _now_wat(): return datetime.now(_WAT)
except ImportError:
    _WAT_TZ = timezone(timedelta(hours=1))
    def _now_wat(): return datetime.now(_WAT_TZ)

# ── Tier config ───────────────────────────────────────────────────────────────
_PAID_TIERS = {"trial", "starter", "trader", "pro"}

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — MARKET DATA FETCHERS  (all free APIs, no keys needed)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800)   # 30 minutes — safe for all free-tier rate limits
def _fetch_yahoo_quote(symbol: str) -> dict:
    """
    Fetch a single quote from Yahoo Finance unofficial JSON endpoint.
    Returns dict with keys: price, change_pct, name  — or empty dict on failure.
    """
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = requests.get(
            url,
            params={"interval": "1d", "range": "2d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        price      = float(meta.get("regularMarketPrice", 0) or 0)
        prev_close = float(meta.get("chartPreviousClose", 0) or
                          meta.get("previousClose", 0) or price)
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
        return {"price": price, "change_pct": round(change_pct, 2),
                "name": meta.get("shortName", symbol)}
    except Exception:
        return {}


@st.cache_data(ttl=1800)
def _fetch_bitcoin() -> dict:
    """CoinGecko free API — no key, very stable."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd",
                    "include_24hr_change": "true"},
            timeout=10,
        )
        if r.status_code != 200:
            return {}
        d = r.json().get("bitcoin", {})
        return {
            "price":      float(d.get("usd", 0)),
            "change_pct": round(float(d.get("usd_24h_change", 0)), 2),
        }
    except Exception:
        return {}


@st.cache_data(ttl=1800)
def _fetch_fear_greed() -> dict:
    """
    CNN Fear & Greed Index — unofficial but widely reliable endpoint.
    Returns score 0-100 and label.
    """
    try:
        r = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0",
                     "Referer": "https://www.cnn.com/markets/fear-and-greed"},
            timeout=10,
        )
        if r.status_code != 200:
            return {}
        d = r.json()
        score = float(d.get("fear_and_greed", {}).get("score", 50))
        label = d.get("fear_and_greed", {}).get("rating", "Neutral")
        return {"score": round(score), "label": label}
    except Exception:
        return {}


@st.cache_data(ttl=1800)
def fetch_global_pulse_data() -> dict:
    """
    Master data fetch — all four signals in one cached call.
    Returns a dict with keys: oil, dxy, btc, fg  (fear/greed)
    Each sub-dict always has at least {"ok": bool}.
    """
    oil = _fetch_yahoo_quote("BZ=F")     # Brent Crude Futures
    dxy = _fetch_yahoo_quote("DX-Y.NYB") # US Dollar Index
    btc = _fetch_bitcoin()
    fg  = _fetch_fear_greed()

    return {
        "oil": {**oil, "ok": bool(oil.get("price"))},
        "dxy": {**dxy, "ok": bool(dxy.get("price"))},
        "btc": {**btc, "ok": bool(btc.get("price"))},
        "fg":  {**fg,  "ok": bool(fg.get("score") is not None)},
        "fetched_at": _now_wat().strftime("%I:%M %p WAT"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — NEWS CONTEXT FETCHER  (Reuters / FT RSS — free)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)   # 60 minutes
def _fetch_global_news_headlines(max_items: int = 6) -> list[str]:
    """
    Fetch top financial headlines from Reuters RSS for AI context.
    Returns list of headline strings — empty list on failure.
    """
    import xml.etree.ElementTree as ET
    feeds = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/reuters/UKBusinessNews",
    ]
    headlines = []
    for url in feeds:
        if len(headlines) >= max_items:
            break
        try:
            r = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.text)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                if title and len(title) > 20:
                    headlines.append(title)
                if len(headlines) >= max_items:
                    break
        except Exception:
            continue
    return headlines


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — DETERMINISTIC NAIRA IMPACT RULES  (always works, zero API cost)
# ══════════════════════════════════════════════════════════════════════════════

def _rule_based_naira_impact(data: dict) -> dict:
    """
    Pure logic — derives Nigerian market context from the raw numbers.
    Returns a dict with keys matching all four tiles + a summary sentence.
    Always produces output regardless of AI availability.
    """
    oil  = data.get("oil", {})
    dxy  = data.get("dxy", {})
    btc  = data.get("btc", {})
    fg   = data.get("fg", {})

    oil_chg = oil.get("change_pct", 0)
    dxy_chg = dxy.get("change_pct", 0)
    btc_chg = btc.get("change_pct", 0)
    fg_score = fg.get("score", 50)

    # ── Oil impact ────────────────────────────────────────────────────────────
    if oil_chg >= 2.0:
        oil_impact = "Strong positive for Nigeria. Higher oil revenue eases Naira pressure. Energy stocks like Seplat and Oando may rally."
        oil_mood   = "positive"
    elif oil_chg >= 0.5:
        oil_impact = "Mild positive for Nigeria. Slightly higher oil revenue — watch energy stocks for upside."
        oil_mood   = "positive"
    elif oil_chg <= -2.0:
        oil_impact = "Negative signal for Nigeria. Lower oil prices reduce government revenue and increase Naira pressure."
        oil_mood   = "negative"
    elif oil_chg <= -0.5:
        oil_impact = "Mild negative. Slightly lower oil revenue — energy stocks may face headwinds today."
        oil_mood   = "negative"
    else:
        oil_impact = "Oil is steady — no immediate Naira pressure from crude prices today."
        oil_mood   = "neutral"

    # ── Dollar / DXY impact ───────────────────────────────────────────────────
    if dxy_chg >= 1.0:
        dxy_impact = "Dollar strengthening significantly. Naira under pressure. Companies that import heavily (Nestle, Unilever) may face margin stress."
        dxy_mood   = "negative"
    elif dxy_chg >= 0.3:
        dxy_impact = "Dollar edging higher. Mild Naira pressure. Watch importers and companies with dollar-denominated debt."
        dxy_mood   = "negative"
    elif dxy_chg <= -1.0:
        dxy_impact = "Dollar weakening. Positive for the Naira — import costs ease and foreign investors may look at emerging markets like Nigeria."
        dxy_mood   = "positive"
    elif dxy_chg <= -0.3:
        dxy_impact = "Dollar slightly weaker. Small positive for the Naira and NGX foreign investor flows."
        dxy_mood   = "positive"
    else:
        dxy_impact = "Dollar is stable. No significant Naira pressure from currency markets today."
        dxy_mood   = "neutral"

    # ── Bitcoin impact ────────────────────────────────────────────────────────
    if btc_chg >= 5.0:
        btc_impact = "Bitcoin surging — global investors are in full risk-on mode. This positive sentiment often flows into stock markets including NGX."
        btc_mood   = "positive"
    elif btc_chg >= 2.0:
        btc_impact = "Bitcoin rising — risk appetite is growing globally. Good sign for equity markets and growth stocks."
        btc_mood   = "positive"
    elif btc_chg <= -5.0:
        btc_impact = "Bitcoin dropping sharply — risk-off mood globally. Investors may be cautious. Watch NGX for reduced buying activity."
        btc_mood   = "negative"
    elif btc_chg <= -2.0:
        btc_impact = "Bitcoin falling — some risk-off sentiment building. Could dampen enthusiasm for growth stocks today."
        btc_mood   = "negative"
    else:
        btc_impact = "Bitcoin is quiet — no strong global risk signal from crypto markets today."
        btc_mood   = "neutral"

    # ── Fear & Greed impact ───────────────────────────────────────────────────
    if fg_score >= 75:
        fg_label   = "Extreme Greed"
        fg_impact  = "Extreme greed globally — big investors are very confident and buying aggressively. Strong environment for NGX growth stocks."
        fg_mood    = "positive"
    elif fg_score >= 55:
        fg_label   = "Greed"
        fg_impact  = "Greed mode globally — investors are confident. Positive conditions for NGX stocks today."
        fg_mood    = "positive"
    elif fg_score >= 45:
        fg_label   = "Neutral"
        fg_impact  = "Global mood is balanced — neither fearful nor greedy. Normal trading conditions for NGX."
        fg_mood    = "neutral"
    elif fg_score >= 25:
        fg_label   = "Fear"
        fg_impact  = "Fear in global markets — investors are cautious. This can lead to reduced risk appetite on NGX too."
        fg_mood    = "negative"
    else:
        fg_label   = "Extreme Fear"
        fg_impact  = "Extreme fear globally — investors are pulling back. Be extra cautious with new positions on NGX today."
        fg_mood    = "negative"

    # Use raw label if available
    if fg.get("label"):
        fg_label = fg["label"].title()

    # ── Master summary sentence ───────────────────────────────────────────────
    positives = sum(1 for m in [oil_mood, dxy_mood, btc_mood, fg_mood] if m == "positive")
    negatives = sum(1 for m in [oil_mood, dxy_mood, btc_mood, fg_mood] if m == "negative")

    if positives >= 3:
        summary = (
            f"Oil {'up' if oil_chg > 0 else 'stable'} and global confidence is high — "
            f"NGX may open positively today. Good conditions to watch your growth stocks."
        )
    elif negatives >= 3:
        summary = (
            f"Multiple global headwinds today — {'oil falling, ' if oil_chg < -0.5 else ''}"
            f"{'dollar strengthening, ' if dxy_chg > 0.3 else ''}"
            f"risk appetite is low. Exercise extra caution with new positions on NGX."
        )
    elif oil_mood == "positive" and dxy_mood == "negative":
        summary = (
            "Oil rising and dollar weakening — the best combination for Nigeria. "
            "Naira pressure easing and export revenue growing. Strong environment for NGX today."
        )
    elif oil_mood == "negative" and dxy_mood == "positive":
        summary = (
            "Oil falling with a stronger dollar — double headwind for the Naira. "
            "Focus on defensive stocks and avoid over-extending positions today."
        )
    elif positives >= 2:
        summary = (
            "Global conditions are mostly positive today. "
            "Cautious optimism is reasonable — check individual signal scores before acting."
        )
    elif negatives >= 2:
        summary = (
            "Mixed global signals with a cautious lean. "
            "Stick to strong BUY signals today and avoid speculative positions."
        )
    else:
        summary = (
            "Global markets are quiet today — no strong tailwinds or headwinds for NGX. "
            "Follow individual stock signals rather than broad market trends."
        )

    return {
        "oil_impact":  oil_impact,
        "oil_mood":    oil_mood,
        "dxy_impact":  dxy_impact,
        "dxy_mood":    dxy_mood,
        "btc_impact":  btc_impact,
        "btc_mood":    btc_mood,
        "fg_impact":   fg_impact,
        "fg_mood":     fg_mood,
        "fg_label":    fg_label,
        "summary":     summary,
        "source":      "rules",
    }


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — AI SUMMARY GENERATOR  (Gemini → Groq → rules fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _build_global_pulse_prompt(data: dict, headlines: list[str]) -> str:
    """Build the AI prompt for global pulse Naira-context analysis."""
    oil  = data.get("oil", {})
    dxy  = data.get("dxy", {})
    btc  = data.get("btc", {})
    fg   = data.get("fg", {})

    news_text = "\n".join(f"- {h}" for h in headlines[:6]) if headlines else "No headlines available."

    return f"""You are NGX Signal AI — a Nigerian stock market intelligence assistant.

Today's global market data:
- Brent Crude Oil: ${oil.get('price', 'N/A'):.2f} | Change: {oil.get('change_pct', 0):+.2f}%
- US Dollar Index (DXY): {dxy.get('price', 'N/A'):.2f} | Change: {dxy.get('change_pct', 0):+.2f}%
- Bitcoin: ${btc.get('price', 0):,.0f} | Change: {btc.get('change_pct', 0):+.2f}%
- Global Fear & Greed Score: {fg.get('score', 50)}/100 — {fg.get('label', 'Neutral')}

Recent global financial headlines:
{news_text}

YOUR TASK — Write a Global Pulse analysis for Nigerian investors. Respond ONLY with a valid JSON object, no markdown, no extra text:

{{
  "oil_impact": "One sentence: what does today's oil move mean for Nigeria, the Naira, and specific NGX sectors (mention Seplat/Oando if relevant). Max 25 words.",
  "dxy_impact": "One sentence: what does today's dollar move mean for the Naira and Nigerian importers/exporters. Max 25 words.",
  "btc_impact": "One sentence: what does Bitcoin's move signal about global investor mood and what that means for NGX. Max 25 words.",
  "fg_impact": "One sentence: what does today's Fear & Greed score mean for Nigerian investors and NGX trading conditions. Max 25 words.",
  "summary": "One powerful summary sentence (max 35 words) that tells a Nigerian investor exactly what the global picture means for their NGX portfolio today. Make it actionable and specific."
}}

RULES:
- Never use jargon (no 'bullish', 'bearish', 'RSI', 'support levels')
- Always tie back to Nigeria, the Naira, or specific NGX stocks/sectors
- Sound like a smart Nigerian financial friend, not a robot
- Each sentence must be genuinely different — no repetition
- The summary must be the most useful single sentence a Nigerian investor could read this morning
"""


def _call_gemini(prompt: str, max_tokens: int = 400) -> str | None:
    """Call Gemini 1.5 Flash — primary AI layer."""
    key = st.secrets.get("GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
            },
            timeout=20,
        )
        if r.status_code != 200:
            return None
        parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
        return parts[0].get("text", "").strip() if parts else None
    except Exception:
        return None


def _call_groq(prompt: str, max_tokens: int = 400) -> str | None:
    """Call Groq Llama — fallback AI layer."""
    key = st.secrets.get("GROQ_API_KEY", "")
    if not key:
        return None
    for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
                timeout=20,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            continue
    return None


def _parse_ai_json(raw: str) -> dict | None:
    """Safely extract and parse JSON from AI response."""
    if not raw:
        return None
    try:
        # Strip markdown fences if present
        clean = raw.replace("```json", "").replace("```", "").strip()
        # Find the JSON object
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        parsed = json.loads(clean[start:end])
        required = {"oil_impact", "dxy_impact", "btc_impact", "fg_impact", "summary"}
        if required.issubset(parsed.keys()):
            return parsed
    except Exception:
        pass
    return None


def _generate_ai_impacts(data: dict) -> dict | None:
    """
    Try Gemini → Groq in sequence.
    Returns parsed impact dict or None if both fail.
    """
    headlines = _fetch_global_news_headlines()
    prompt    = _build_global_pulse_prompt(data, headlines)

    # Layer 1: Gemini
    raw = _call_gemini(prompt)
    parsed = _parse_ai_json(raw)
    if parsed:
        parsed["source"] = "gemini"
        return parsed

    # Layer 2: Groq
    raw = _call_groq(prompt)
    parsed = _parse_ai_json(raw)
    if parsed:
        parsed["source"] = "groq"
        return parsed

    return None


# ══════════════════════════════════════════════════════════════════════════════
# MASTER FUNCTION — get_global_pulse()
# ══════════════════════════════════════════════════════════════════════════════

def get_global_pulse() -> dict:
    """
    Public entry point. Returns the full Global Pulse dict.

    Always returns a result — never raises or crashes.
    AI impacts are cached in session_state with a daily seed key so the
    AI is only called once per day per user session, not on every rerender.

    Keys in returned dict:
      data         → raw market data (oil, dxy, btc, fg)
      impacts      → impact text for each signal (source: gemini/groq/rules)
      tier_ok      → bool — True if caller is on a paid plan (set externally)
      fetched_at   → time string
    """
    # Step 1: Get raw market data (cached 30 min)
    data = fetch_global_pulse_data()

    # Step 2: Check session cache for today's AI impacts
    _daily_key = f"_gp_impacts_{date.today().isoformat()}"
    impacts = st.session_state.get(_daily_key)

    if not impacts:
        # Step 3a: Try AI (Gemini → Groq)
        ai_result = None
        try:
            ai_result = _generate_ai_impacts(data)
        except Exception:
            pass

        if ai_result:
            # Merge moods from rule-based (AI doesn't return moods, we need them for tile colors)
            rule_result = _rule_based_naira_impact(data)
            impacts = {**rule_result, **ai_result}
            impacts["source"] = ai_result.get("source", "ai")
        else:
            # Step 3b: Pure deterministic rules fallback
            impacts = _rule_based_naira_impact(data)

        # Cache in session state for the day
        st.session_state[_daily_key] = impacts

    return {
        "data":       data,
        "impacts":    impacts,
        "fetched_at": data.get("fetched_at", ""),
    }


def get_global_pulse_for_ai(pulse: dict | None = None) -> str:
    """
    Returns a compact global context string for injection into AI prompts.
    Silent — never shows anything to the user.
    Fetches pulse data if not already provided.
    """
    try:
        if pulse is None:
            pulse = get_global_pulse()
        data    = pulse.get("data", {})
        impacts = pulse.get("impacts", {})
        oil     = data.get("oil", {})
        dxy     = data.get("dxy", {})
        btc     = data.get("btc", {})
        fg      = data.get("fg", {})
        return (
            f"\nGLOBAL MARKET CONTEXT (today):\n"
            f"- Brent Crude Oil: ${oil.get('price', 0):.2f} ({oil.get('change_pct', 0):+.2f}%)\n"
            f"- US Dollar (DXY): {dxy.get('price', 0):.2f} ({dxy.get('change_pct', 0):+.2f}%)\n"
            f"- Bitcoin: ${btc.get('price', 0):,.0f} ({btc.get('change_pct', 0):+.2f}%)\n"
            f"- Global mood: {fg.get('label', 'Neutral')} ({fg.get('score', 50)}/100)\n"
            f"- Nigerian context: {impacts.get('summary', '')}\n"
        )
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# RENDERER — render_global_pulse_strip()
# ══════════════════════════════════════════════════════════════════════════════

def render_global_pulse_strip(tier: str, location: str = "home") -> None:
    """
    Renders the Global Pulse component inline.

    Args:
        tier:     User's current plan tier string
        location: "home" | "signals" — controls layout variant
                  "home"    → full four-tile grid + summary sentence
                  "signals" → compact single-line context bar

    Tier access:
        All tiers  → tiles with direction arrows + basic label
        Paid only  → Naira impact text + summary sentence
    """
    is_paid = tier in _PAID_TIERS

    # Silently fetch — never block render
    try:
        pulse   = get_global_pulse()
        data    = pulse["data"]
        impacts = pulse["impacts"]
    except Exception:
        return   # fail silently — never crash the page

    oil  = data.get("oil", {})
    dxy  = data.get("dxy", {})
    btc  = data.get("btc", {})
    fg   = data.get("fg", {})

    oil_chg  = oil.get("change_pct", 0)
    dxy_chg  = dxy.get("change_pct", 0)
    btc_chg  = btc.get("change_pct", 0)
    fg_score = fg.get("score", 50)
    fg_label = impacts.get("fg_label", fg.get("label", "Neutral"))

    def _arrow(v):
        return "▲" if v > 0 else "▼" if v < 0 else "–"

    def _chg_color(v):
        return "#22C55E" if v > 0 else "#EF4444" if v < 0 else "#6B7280"

    def _mood_color(mood):
        return {"positive": "#22C55E", "negative": "#EF4444", "neutral": "#6B7280"}.get(mood, "#6B7280")

    # ── SIGNALS PAGE: compact one-line bar ────────────────────────────────────
    if location == "signals":
        parts = []
        if oil.get("ok"):
            parts.append(
                f'<span style="color:{_chg_color(oil_chg)};">'
                f'🛢️ Oil {_arrow(oil_chg)}{abs(oil_chg):.1f}%</span>'
            )
        if dxy.get("ok"):
            parts.append(
                f'<span style="color:{_chg_color(dxy_chg)};">'
                f'💵 Dollar {_arrow(dxy_chg)}{abs(dxy_chg):.1f}%</span>'
            )
        if btc.get("ok"):
            parts.append(
                f'<span style="color:{_chg_color(btc_chg)};">'
                f'₿ BTC {_arrow(btc_chg)}{abs(btc_chg):.1f}%</span>'
            )
        if fg.get("ok"):
            fg_col = _chg_color(fg_score - 50)
            parts.append(
                f'<span style="color:{fg_col};">🌍 {fg_label}</span>'
            )

        pills = '&nbsp;&nbsp;·&nbsp;&nbsp;'.join(parts)

        if is_paid:
            summary_html = (
                f'<div style="font-size:11px;color:#C8C4BC;margin-top:5px;padding-top:5px;'
                f'border-top:1px solid #1E2229;">'
                f'<span style="color:#F0A500;font-weight:600;">NGX context:</span> '
                f'{impacts.get("summary", "")}'
                f'</div>'
            )
        else:
            summary_html = (
                '<div style="font-size:10px;color:#4B5563;margin-top:4px;">'
                '🔒 <a href="#" style="color:#F0A500;">Upgrade</a> to see what this means for your NGX portfolio'
                '</div>'
            )

        st.markdown(f"""
<div style="background:#080A0D;border:1px solid #1E2229;border-radius:8px;
            padding:9px 14px;margin-bottom:14px;font-family:'DM Mono',monospace;">
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
    <span style="font-size:9px;color:#4B5563;text-transform:uppercase;
                 letter-spacing:.09em;font-weight:600;flex-shrink:0;">🌍 Global Pulse</span>
    <span style="font-size:11px;">{pills}</span>
  </div>
  {summary_html}
</div>
""", unsafe_allow_html=True)
        return

    # ── HOMEPAGE: full four-tile grid + summary ───────────────────────────────

    # Build tile data
    tiles = []

    if oil.get("ok"):
        tiles.append({
            "icon":   "🛢️",
            "label":  "Crude Oil",
            "value":  f"${oil['price']:.2f}",
            "change": f"{_arrow(oil_chg)} {abs(oil_chg):.2f}%",
            "color":  _chg_color(oil_chg),
            "mood":   impacts.get("oil_mood", "neutral"),
            "impact": impacts.get("oil_impact", ""),
        })

    if dxy.get("ok"):
        tiles.append({
            "icon":   "💵",
            "label":  "US Dollar",
            "value":  f"{dxy['price']:.2f}",
            "change": f"{_arrow(dxy_chg)} {abs(dxy_chg):.2f}%",
            "color":  _chg_color(dxy_chg),
            "mood":   impacts.get("dxy_mood", "neutral"),
            "impact": impacts.get("dxy_impact", ""),
        })

    if btc.get("ok"):
        tiles.append({
            "icon":   "₿",
            "label":  "Bitcoin",
            "value":  f"${btc['price']:,.0f}",
            "change": f"{_arrow(btc_chg)} {abs(btc_chg):.2f}%",
            "color":  _chg_color(btc_chg),
            "mood":   impacts.get("btc_mood", "neutral"),
            "impact": impacts.get("btc_impact", ""),
        })

    if fg.get("ok"):
        fg_col = _mood_color(impacts.get("fg_mood", "neutral"))
        tiles.append({
            "icon":   "🌍",
            "label":  "Global Mood",
            "value":  fg_label,
            "change": f"{fg_score}/100",
            "color":  fg_col,
            "mood":   impacts.get("fg_mood", "neutral"),
            "impact": impacts.get("fg_impact", ""),
        })

    if not tiles:
        return   # all APIs failed — render nothing rather than an empty card

    # ── Tile HTML builder ──────────────────────────────────────────────────────
    def _tile_html(t: dict) -> str:
        border_col = t["color"]
        if is_paid:
            impact_section = (
                f'<div style="font-size:10px;color:#9CA3AF;line-height:1.55;'
                f'margin-top:8px;padding-top:7px;border-top:1px solid #1A1D24;">'
                f'{t["impact"]}</div>'
            )
        else:
            impact_section = (
                '<div style="font-size:10px;color:#4B5563;margin-top:8px;'
                'padding-top:6px;border-top:1px solid #1A1D24;">'
                '🔒 Naira impact — paid plan</div>'
            )
        return f"""
<div style="background:#0A0C0F;border:1px solid #1E2229;
            border-top:2px solid {border_col};
            border-radius:10px;padding:12px 14px;flex:1;min-width:140px;">
  <div style="font-size:18px;margin-bottom:4px;">{t['icon']}</div>
  <div style="font-size:9px;color:#4B5563;text-transform:uppercase;
              letter-spacing:.08em;margin-bottom:4px;">{t['label']}</div>
  <div style="font-size:16px;font-weight:600;color:#FFFFFF;
              font-family:'DM Mono',monospace;">{t['value']}</div>
  <div style="font-size:12px;font-weight:600;color:{t['color']};
              margin-top:2px;">{t['change']}</div>
  {impact_section}
</div>"""

    tiles_html = "\n".join(_tile_html(t) for t in tiles)

    # ── Summary sentence (paid only) ──────────────────────────────────────────
    if is_paid:
        summary = impacts.get("summary", "")
        source  = impacts.get("source", "rules")
        src_badge = (
            '<span style="font-size:9px;color:#22C55E;margin-left:6px;">✦ AI</span>'
            if source in ("gemini", "groq") else ""
        )
        summary_section = f"""
<div style="background:#080A0D;border:1px solid #1E2229;
            border-left:3px solid #F0A500;border-radius:8px;
            padding:11px 14px;margin-top:10px;
            font-family:'DM Mono',monospace;font-size:12px;
            color:#C8C4BC;line-height:1.7;">
  <span style="font-size:9px;color:#F0A500;text-transform:uppercase;
               letter-spacing:.09em;font-weight:600;">
    Today's NGX Context{src_badge}
  </span><br>
  {summary}
</div>"""
    else:
        summary_section = f"""
<div style="background:#0A0800;border:1px solid rgba(240,165,0,.15);
            border-radius:8px;padding:10px 14px;margin-top:10px;
            font-family:'DM Mono',monospace;font-size:11px;
            color:#6B7280;text-align:center;">
  🔒 <strong style="color:#F0A500;">Upgrade to Starter</strong> —
  unlock what these global signals mean for your Naira and NGX portfolio
</div>"""

    ai_note = (
        f'<span style="font-size:9px;color:#374151;">Updated {pulse.get("fetched_at","")}</span>'
    )

    st.markdown(f"""
<style>
  .gp-section-title {{
    font-family:'DM Mono',monospace;
    font-size:11px;color:#6B7280;
    text-transform:uppercase;letter-spacing:.1em;
    margin:16px 0 10px 0;
    display:flex;align-items:center;gap:8px;
  }}
</style>
<div class="gp-section-title">
  🌍 Global Pulse — World Markets Today
  {ai_note}
</div>
<div style="display:flex;flex-wrap:wrap;gap:8px;">
  {tiles_html}
</div>
{summary_section}
<div style="height:6px;"></div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIGNALS PAGE: per-card sector context
# ══════════════════════════════════════════════════════════════════════════════

# Pre-computed sector → global signal sensitivity map
# Used for per-card context injection on signals page (paid only)
_SECTOR_SENSITIVITY = {
    "Banking":       {"oil": 0.3, "dxy": 0.7, "btc": 0.2},
    "Finance":       {"oil": 0.3, "dxy": 0.7, "btc": 0.2},
    "Oil & Gas":     {"oil": 1.0, "dxy": 0.4, "btc": 0.1},
    "Energy":        {"oil": 0.8, "dxy": 0.3, "btc": 0.1},
    "Consumer Goods":{"oil": 0.4, "dxy": 0.8, "btc": 0.1},
    "Telecoms":      {"oil": 0.2, "dxy": 0.5, "btc": 0.2},
    "ICT":           {"oil": 0.2, "dxy": 0.4, "btc": 0.5},
    "Cement":        {"oil": 0.5, "dxy": 0.6, "btc": 0.1},
    "Construction":  {"oil": 0.5, "dxy": 0.5, "btc": 0.1},
    "Agriculture":   {"oil": 0.3, "dxy": 0.6, "btc": 0.1},
    "Healthcare":    {"oil": 0.2, "dxy": 0.7, "btc": 0.1},
    "Insurance":     {"oil": 0.2, "dxy": 0.5, "btc": 0.2},
    "Real Estate":   {"oil": 0.3, "dxy": 0.6, "btc": 0.2},
    "Transportation":{"oil": 0.7, "dxy": 0.4, "btc": 0.1},
}

@st.cache_data(ttl=1800)
def get_sector_global_context(sector: str, oil_chg: float,
                               dxy_chg: float, btc_chg: float,
                               fg_score: float) -> str:
    """
    Returns a single-sentence global context for a given NGX sector.
    Used inside signal cards for paid users.
    Cached 30 min — sector map never changes within a session.
    """
    s = _SECTOR_SENSITIVITY.get(sector, {"oil": 0.3, "dxy": 0.5, "btc": 0.2})

    # Weighted score: positive = global tailwind, negative = headwind
    score = (
        s["oil"] * oil_chg / 3.0 +
        s["dxy"] * (-dxy_chg) / 3.0 +   # stronger dollar = headwind
        s["btc"] * btc_chg / 5.0 +
        (fg_score - 50) / 100.0
    )

    if sector in ("Oil & Gas", "Energy"):
        if oil_chg >= 1.0:
            return f"🌍 Oil up {oil_chg:+.1f}% today — global tailwind for {sector} stocks."
        elif oil_chg <= -1.0:
            return f"🌍 Oil down {oil_chg:+.1f}% — global headwind for {sector} stocks today."
        else:
            return f"🌍 Oil stable today — no major global pressure on {sector} stocks."

    if sector in ("Consumer Goods", "Healthcare", "Cement"):
        if dxy_chg >= 0.5:
            return f"🌍 Dollar strengthening — import costs may rise, watch {sector} margins."
        elif dxy_chg <= -0.5:
            return f"🌍 Dollar weakening — import cost relief for {sector} sector today."
        else:
            return f"🌍 Currency stable — no significant global pressure on {sector} today."

    # Generic for other sectors
    if score >= 0.4:
        return f"🌍 Global conditions are favourable for {sector} stocks today."
    elif score <= -0.4:
        return f"🌍 Global headwinds present — be selective with {sector} positions."
    else:
        return f"🌍 Mixed global signals — focus on individual stock strength in {sector}."
