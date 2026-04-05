import os
import sys
from datetime import date
import requests as http_requests

from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.prompts import DAILY_BRIEF_PROMPT, PIDGIN_BRIEF_PROMPT


# ── CONNECTIONS ──────────────────────────────────────
def get_db():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


# ── AI PROVIDERS ─────────────────────────────────────
def call_gemini(prompt: str):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("   ⚠️  No GEMINI_API_KEY set")
        return None
    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash-latest:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 1024,
                "temperature": 0.7
            },
        }
        res = http_requests.post(url, json=payload, timeout=30)
        data = res.json()

        if "error" in data:
            msg = data["error"].get("message", "unknown")[:100]
            print(f"   ⚠️  Gemini error: {msg}")
            return None

        candidates = data.get("candidates", [])
        if not candidates:
            print("   ⚠️  Gemini returned no candidates")
            return None

        return candidates[0]["content"]["parts"][0]["text"].strip()

    except Exception as e:
        print(f"   ⚠️  Gemini exception: {e}")
        return None


def call_groq(prompt: str):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("   ⚠️  No GROQ_API_KEY set — skipping Groq")
        return None
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.7,
        }
        res = http_requests.post(
            url, json=payload, headers=headers, timeout=30
        )
        data = res.json()

        if "error" in data:
            msg = data["error"].get("message", "unknown")[:100]
            print(f"   ⚠️  Groq error: {msg}")
            return None

        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"   ⚠️  Groq exception: {e}")
        return None


def generate_with_fallback(prompt: str):
    """Try Gemini first, fall back to Groq automatically"""
    print("   → Trying Gemini...")
    result = call_gemini(prompt)
    if result:
        print("   ✅ Gemini succeeded")
        return result

    print("   → Gemini unavailable, trying Groq...")
    result = call_groq(prompt)
    if result:
        print("   ✅ Groq succeeded")
        return result

    print("   ❌ All AI providers failed")
    return None


# ── FETCH TODAY'S DATA ───────────────────────────────
def fetch_market_data(sb):
    today = str(date.today())

    summary_res = sb.table("market_summary")\
        .select("*")\
        .eq("trading_date", today)\
        .limit(1)\
        .execute()
    summary = summary_res.data[0] if summary_res.data else {}

    if not summary:
        summary_res = sb.table("market_summary")\
            .select("*")\
            .order("trading_date", desc=True)\
            .limit(1)\
            .execute()
        summary = summary_res.data[0] if summary_res.data else {}

    gainers_res = sb.table("stock_prices")\
        .select("symbol, price, change_percent")\
        .gte("change_percent", 0)\
        .order("change_percent", desc=True)\
        .limit(5)\
        .execute()

    losers_res = sb.table("stock_prices")\
        .select("symbol, price, change_percent")\
        .lt("change_percent", 0)\
        .order("change_percent")\
        .limit(5)\
        .execute()

    active_res = sb.table("stock_prices")\
        .select("symbol, price, volume")\
        .order("volume", desc=True)\
        .limit(3)\
        .execute()

    sectors_res = sb.table("sector_performance")\
        .select("sector_name, change_percent, traffic_light")\
        .order("change_percent", desc=True)\
        .execute()

    news_res = sb.table("news")\
        .select("headline, sentiment")\
        .order("scraped_at", desc=True)\
        .limit(5)\
        .execute()

    return {
        "summary": summary,
        "gainers": gainers_res.data or [],
        "losers": losers_res.data or [],
        "most_active": active_res.data or [],
        "sectors": sectors_res.data or [],
        "news": news_res.data or [],
    }


# ── FORMAT DATA FOR PROMPT ───────────────────────────
def format_for_prompt(data):
    gainers_str = ", ".join(
        f"{g['symbol']} (+{g['change_percent']:.1f}%)"
        for g in data["gainers"]
    )
    losers_str = ", ".join(
        f"{l['symbol']} ({l['change_percent']:.1f}%)"
        for l in data["losers"]
    )
    active_str = ", ".join(
        f"{a['symbol']}" for a in data["most_active"]
    )
    sectors_str = ", ".join(
        f"{s['sector_name']} ({s['traffic_light'].upper()})"
        for s in data["sectors"]
    )
    news_str = " | ".join(
        n["headline"] for n in data["news"]
    )

    summary = data["summary"]
    asi = summary.get("asi_index", 104823)
    asi_change = summary.get("asi_change_percent", 0.0)

    return {
        "asi": f"{asi:,.2f}",
        "asi_change": asi_change,
        "gainers": gainers_str or "No data",
        "losers": losers_str or "No data",
        "most_active": active_str or "No data",
        "sectors": sectors_str or "No data",
        "news": news_str or "No major news today",
    }


# ── SAVE BRIEF TO SUPABASE ───────────────────────────
def save_brief(sb, brief_en, brief_pg):
    today = str(date.today())
    try:
        sb.table("ai_briefs")\
            .delete()\
            .eq("brief_date", today)\
            .eq("brief_type", "morning")\
            .execute()
        print(f"🗑️  Cleared old briefs for {today}")

        if brief_en:
            sb.table("ai_briefs").insert({
                "brief_date": today,
                "brief_type": "morning",
                "language": "en",
                "title": f"NGX Morning Brief — {today}",
                "body": brief_en,
            }).execute()
            print(f"✅ English brief saved for {today}")

        if brief_pg:
            sb.table("ai_briefs").insert({
                "brief_date": today,
                "brief_type": "morning",
                "language": "pg",
                "title": f"NGX Morning Brief (Pidgin) — {today}",
                "body": brief_pg,
            }).execute()
            print(f"✅ Pidgin brief saved for {today}")

        return True

    except Exception as e:
        print(f"❌ Brief save error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── MAIN ─────────────────────────────────────────────
if __name__ == "__main__":
    print("🤖 NGX AI Brief Generator starting...")

    sb = get_db()

    print("📊 Fetching market data...")
    data = fetch_market_data(sb)
    fmt_data = format_for_prompt(data)

    print(f"   ASI: {fmt_data['asi']} ({fmt_data['asi_change']:+.2f}%)")
    print(f"   Gainers: {fmt_data['gainers']}")
    print(f"   Losers: {fmt_data['losers']}")

    print("✍️  Generating English brief...")
    brief_en = generate_with_fallback(
        DAILY_BRIEF_PROMPT.format(**fmt_data)
    )

    print("✍️  Generating Pidgin brief...")
    brief_pg = generate_with_fallback(
        PIDGIN_BRIEF_PROMPT.format(**fmt_data)
    )

    if brief_en:
        print("\n── ENGLISH BRIEF PREVIEW ──")
        print(brief_en[:300] + "...")

    if brief_pg:
        print("\n── PIDGIN BRIEF PREVIEW ──")
        print(brief_pg[:300] + "...")

    save_brief(sb, brief_en, brief_pg)
    print("✅ Brief generation complete!")
