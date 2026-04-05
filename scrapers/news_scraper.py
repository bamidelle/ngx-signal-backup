"""
NGX Signal — Multi-Source News Scraper
Layer 1: NGX Pulse (ngxpulse.ng) — PRIMARY
Layers 2-6: BusinessDay, Nairametrics, TechCabal, Vanguard, Punch
"""
import os, random, requests
from bs4 import BeautifulSoup
from supabase import create_client

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
]

NEWS_SOURCES = [
    {"name":"NGX Pulse","urls":["https://ngxpulse.ng/news","https://ngxpulse.ng/market-news","https://ngxpulse.ng/"],"base":"https://ngxpulse.ng","selectors":["h2","h3","h1"],"priority":1},
    {"name":"BusinessDay","urls":["https://businessday.ng/markets/","https://businessday.ng/capital-market/"],"base":"https://businessday.ng","selectors":["h3","h2"],"priority":2},
    {"name":"Nairametrics","urls":["https://nairametrics.com/category/stock-market-2/"],"base":"https://nairametrics.com","selectors":["h2","h3"],"priority":3},
    {"name":"TechCabal","urls":["https://techcabal.com/category/finance/"],"base":"https://techcabal.com","selectors":["h2","h3"],"priority":4},
    {"name":"Vanguard","urls":["https://www.vanguardngr.com/category/business/stocks/"],"base":"https://www.vanguardngr.com","selectors":["h2","h3"],"priority":5},
    {"name":"The Punch","urls":["https://punchng.com/topic/stock-market/"],"base":"https://punchng.com","selectors":["h2","h3"],"priority":6},
]

POSITIVE = ["gain","rise","bull","growth","surge","profit","rally","increase","strong","boost","record","recovery","advance"]
NEGATIVE = ["fall","drop","loss","bear","decline","crash","down","weak","plunge","sell","slide","dip","deficit","downturn"]


def detect_sentiment(text):
    t = text.lower()
    p = sum(1 for w in POSITIVE if w in t)
    n = sum(1 for w in NEGATIVE if w in t)
    return "positive" if p>n else "negative" if n>p else "neutral"


def resolve_url(href, base):
    if not href: return ""
    if href.startswith("http"): return href
    if href.startswith("//"): return "https:"+href
    if href.startswith("/"): return base+href
    return base+"/"+href


def scrape_source(source):
    articles = []
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept":"text/html;q=0.9,*/*;q=0.8"}
    seen_h = set()
    for url in source["urls"]:
        try:
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code != 200: continue
            soup = BeautifulSoup(res.text, "html.parser")
            for tag_name in source["selectors"]:
                for tag in soup.find_all(tag_name, limit=20):
                    headline = tag.get_text(strip=True)
                    if not headline or len(headline)<20 or headline in seen_h: continue
                    seen_h.add(headline)
                    href = ""
                    if tag.name=="a": href=tag.get("href","")
                    else:
                        a = tag.find("a",href=True) or tag.find_parent("a",href=True)
                        if a: href=a.get("href","")
                    aurl = resolve_url(href, source["base"])
                    skip = ["category","tag","page","author","login","register","#","javascript","wp-content"]
                    if any(s in aurl.lower() for s in skip): continue
                    articles.append({"headline":headline[:500],"source":source["name"],"url":aurl or url,"sentiment":detect_sentiment(headline)})
            if articles: break
        except Exception as e:
            print(f"      {source['name']} error: {e}")
    return articles


def run_news_scraper(sb=None):
    if sb is None:
        sb_url = os.environ.get("SUPABASE_URL")
        sb_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not sb_url or not sb_key: print("Missing Supabase creds"); return 0
        sb = create_client(sb_url, sb_key)

    print("Scraping news (NGX Pulse as Layer 1)...")
    all_articles = []
    for source in sorted(NEWS_SOURCES, key=lambda x: x["priority"]):
        print(f"   Layer {source['priority']}: {source['name']}...")
        arts = scrape_source(source)
        print(f"      {len(arts)} articles")
        all_articles.extend(arts)

    seen_u=set(); seen_h=set(); unique=[]
    for a in all_articles:
        uk=(a.get("url") or "")[:120]; hk=(a.get("headline") or "")[:60].lower()
        if uk in seen_u or hk in seen_h or not uk or not hk: continue
        seen_u.add(uk); seen_h.add(hk); unique.append(a)

    print(f"   {len(unique)} unique articles")
    saved = 0
    for article in unique[:40]:
        try:
            sb.table("news").upsert({"headline":article["headline"],"source":article["source"],"url":article["url"],"sentiment":article["sentiment"]}, on_conflict="url").execute()
            saved+=1
        except Exception: continue

    print(f"Saved {saved} articles")
    return saved


if __name__ == "__main__":
    run_news_scraper()
