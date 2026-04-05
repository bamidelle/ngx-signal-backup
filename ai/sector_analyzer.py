import os
import sys
from datetime import date

import google.generativeai as genai
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_db():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


def get_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def analyze_sectors(sb, model):
    today = str(date.today())
    print("🚦 AI analyzing sectors...")

    sectors_res = sb.table("sector_performance")\
        .select("*")\
        .order("performance_date", desc=True)\
        .limit(9)\
        .execute()

    if not sectors_res.data:
        print("⚠️  No sector data")
        return

    for sector in sectors_res.data:
        try:
            prompt = f"""
You are a Nigerian stock market analyst. 
Analyze this sector and write a 1-sentence verdict in plain English 
and a 1-sentence verdict in Nigerian Pidgin English.

Sector: {sector['sector_name']}
Performance today: {sector['change_percent']:+.2f}%
Traffic light: {sector['traffic_light']}

Respond in JSON only:
{{
  "verdict": "<1 sentence plain English verdict>",
  "verdict_pg": "<1 sentence Nigerian Pidgin verdict>"
}}
"""
            response = model.generate_content(prompt)
            raw = response.text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            import json
            result = json.loads(raw.strip())

            sb.table("sector_performance").update({
                "verdict": result.get("verdict", sector["verdict"]),
                "verdict_pg": result.get(
                    "verdict_pg", sector["verdict_pg"]
                ),
            }).eq("sector_name", sector["sector_name"])\
              .eq("performance_date", sector["performance_date"])\
              .execute()

            print(f"  ✅ {sector['sector_name']}: updated")

        except Exception as e:
            print(f"  ⚠️  {sector['sector_name']} failed: {e}")
            continue

    print("✅ Sector analysis complete!")


if __name__ == "__main__":
    sb = get_db()
    model = get_gemini()
    analyze_sectors(sb, model)
