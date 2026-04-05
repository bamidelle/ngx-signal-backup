import os
import sys
import json
from datetime import date

import google.generativeai as genai
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.prompts import SIGNAL_SCORE_PROMPT


def get_db():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


def get_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def score_stocks(sb, model):
    today = str(date.today())
    print(f"⭐ AI scoring stocks for {today}...")

    # Get today's prices
    prices_res = sb.table("stock_prices")\
        .select("*")\
        .order("trading_date", desc=True)\
        .limit(30)\
        .execute()

    if not prices_res.data:
        print("⚠️  No price data found")
        return

    # Get stocks info
    stocks_res = sb.table("stocks")\
        .select("symbol, company_name, sector")\
        .execute()
    stock_map = {
        s["symbol"]: s for s in (stocks_res.data or [])
    }

    # Get recent news per stock
    news_res = sb.table("news")\
        .select("headline, symbols_mentioned, sentiment")\
        .order("scraped_at", desc=True)\
        .limit(50)\
        .execute()

    # Get sector performance
    sector_res = sb.table("sector_performance")\
        .select("sector_name, change_percent")\
        .order("performance_date", desc=True)\
        .limit(9)\
        .execute()
    sector_map = {
        s["sector_name"]: s["change_percent"]
        for s in (sector_res.data or [])
    }

    scored = 0
    for p in prices_res.data:
        symbol = p["symbol"]
        stock_info = stock_map.get(symbol, {})
        company = stock_info.get("company_name", symbol)
        sector = stock_info.get("sector", "Unknown")
        sector_change = sector_map.get(sector, 0.0)

        # Get news mentioning this stock
        stock_news = [
            n["headline"] for n in (news_res.data or [])
            if symbol in (n.get("symbols_mentioned") or [])
        ]
        news_str = " | ".join(stock_news[:3]) or "No recent news"

        try:
            prompt = SIGNAL_SCORE_PROMPT.format(
                symbol=symbol,
                company_name=company,
                sector=sector,
                price=p.get("price", 0),
                change_percent=p.get("change_percent", 0),
                price_history=f"Today: {p.get('price',0)}",
                news=news_str,
                sector_change=sector_change,
            )

            response = model.generate_content(prompt)
            raw = response.text.strip()

            # Clean JSON response
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            result = json.loads(raw)

            sb.table("signal_scores").upsert({
                "symbol": symbol,
                "score_date": today,
                "stars": int(result.get("stars", 3)),
                "signal": result.get("signal", "HOLD"),
                "reasoning": result.get("reasoning", ""),
                "momentum_score": float(
                    result.get("momentum_score", 0.5)
                ),
                "volume_score": float(
                    result.get("volume_score", 0.5)
                ),
                "news_score": float(
                    result.get("news_score", 0.5)
                ),
            }, on_conflict="symbol,score_date").execute()

            scored += 1
            print(f"  ✅ {symbol}: {result.get('stars')}⭐ {result.get('signal')}")

        except Exception as e:
            print(f"  ⚠️  {symbol} scoring failed: {e}")
            continue

    print(f"\n✅ AI scored {scored} stocks")


if __name__ == "__main__":
    print("🤖 NGX AI Signal Scorer starting...")
    sb = get_db()
    model = get_gemini()
    score_stocks(sb, model)
    print("✅ Signal scoring complete!")
