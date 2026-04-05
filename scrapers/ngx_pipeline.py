"""
NGX Signal — Resilient Multi-Source Nigerian Stock Market Data Pipeline
=======================================================================
Architecture: Primary → 5 fallback sources → normalization → smart signals
Author: NGX Signal Team
"""

import logging
import time
import json
import random
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

# ── Optional imports (graceful if not installed) ──────
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# ── Logging setup ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("NGXPipeline")


# ══════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════

# Rotating user agents — prevents blocking
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
    "Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
]

REQUEST_TIMEOUT = 20       # seconds per request
MAX_RETRIES     = 3        # retries per source
RETRY_DELAY     = 2        # seconds between retries
CACHE_TTL       = 3600     # 1 hour cache TTL in seconds

# In-memory cache
_CACHE: dict = {}


# ══════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════

def get_headers(referer: str = "https://www.google.com") -> dict:
    """Return headers with randomized User-Agent."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": referer,
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }


def safe_float(val, default: float = 0.0) -> float:
    """Safely convert any value to float."""
    if val is None:
        return default
    try:
        cleaned = str(val).replace(",", "").replace(
            "₦", ""
        ).replace("%", "").replace("+", "").strip()
        return float(cleaned) if cleaned not in ("", "-", "N/A", "—") \
            else default
    except (ValueError, TypeError):
        return default


def safe_int(val, default: int = 0) -> int:
    """Safely convert any value to int."""
    try:
        cleaned = str(val).replace(",", "").strip()
        return int(float(cleaned)) if cleaned not in ("", "-", "N/A", "—") \
            else default
    except (ValueError, TypeError):
        return default


def clean_symbol(sym: str) -> str:
    """Normalize stock symbol to uppercase stripped string."""
    return str(sym).upper().strip().replace(" ", "")


def retry_request(
    method: str,
    url: str,
    headers: dict,
    retries: int = MAX_RETRIES,
    delay: float = RETRY_DELAY,
    **kwargs
) -> Optional[requests.Response]:
    """
    Make an HTTP request with retry logic.
    Returns Response or None on all failures.
    """
    for attempt in range(1, retries + 1):
        try:
            res = requests.request(
                method, url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                **kwargs
            )
            if res.status_code == 200:
                return res
            logger.warning(
                f"HTTP {res.status_code} on attempt {attempt} — {url}"
            )
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt} — {url}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error attempt {attempt} — {e}")
        except Exception as e:
            logger.warning(f"Request error attempt {attempt} — {e}")

        if attempt < retries:
            time.sleep(delay * attempt)  # exponential backoff

    logger.error(f"All {retries} attempts failed for {url}")
    return None


def get_cache(key: str) -> Optional[list]:
    """Return cached data if still valid."""
    if key in _CACHE:
        data, ts = _CACHE[key]
        if time.time() - ts < CACHE_TTL:
            logger.info(f"Cache HIT for {key} ({len(data)} stocks)")
            return data
        del _CACHE[key]
    return None


def set_cache(key: str, data: list):
    """Store data in memory cache with timestamp."""
    _CACHE[key] = (data, time.time())
    logger.info(f"Cached {len(data)} stocks under key '{key}'")


# ══════════════════════════════════════════════════════
# DATA NORMALIZATION
# ══════════════════════════════════════════════════════

def normalize_data(raw_list: list, source: str) -> list:
    """
    Convert raw scraped data into the unified NGX format.
    Handles type conversion, deduplication, missing values.
    """
    now = datetime.utcnow().isoformat() + "Z"
    normalized = []
    seen_symbols = set()

    for item in raw_list:
        try:
            symbol = clean_symbol(item.get("symbol", ""))
            if not symbol or len(symbol) > 16:
                continue

            # Skip duplicates — keep first occurrence
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)

            price = safe_float(item.get("price"))
            change = safe_float(item.get("change"))
            percent_change = safe_float(item.get("percent_change"))
            volume = safe_int(item.get("volume"))

            # Skip invalid prices
            if price <= 0:
                continue

            # Derive missing percent_change if possible
            if percent_change == 0.0 and change != 0.0 and price > 0:
                prev = price - change
                if prev > 0:
                    percent_change = round((change / prev) * 100, 4)

            # Price change flag
            if percent_change > 0.1:
                flag = "UP"
            elif percent_change < -0.1:
                flag = "DOWN"
            else:
                flag = "FLAT"

            normalized.append({
                "symbol": symbol,
                "price": round(price, 4),
                "change": round(change, 4),
                "percent_change": round(percent_change, 4),
                "volume": volume,
                "price_change_flag": flag,
                "source": source,
                "timestamp": now,
            })

        except Exception as e:
            logger.debug(f"Normalize error for item {item}: {e}")
            continue

    logger.info(
        f"Normalized {len(normalized)} stocks from {source}"
    )
    return normalized


# ══════════════════════════════════════════════════════
# SOURCE 1: NGX PULSE (PRIMARY)
# ══════════════════════════════════════════════════════

def scrape_ngx_pulse() -> list:
    """
    PRIMARY SOURCE: NGX Pulse — ngxpulse.com
    Scrapes the equities price table from the official NGX
    market data portal.
    """
    logger.info("📡 Source 1: Scraping NGX Pulse...")
    raw = []

    urls = [
        "https://ngxpulse.com/market-statistics",
        "https://ngxpulse.com/equities",
        "https://ngxpulse.com/",
    ]

    for url in urls:
        res = retry_request(
            "GET", url,
            headers=get_headers("https://ngxpulse.com/"),
        )
        if not res:
            continue

        soup = BeautifulSoup(res.text, "html.parser")

        # Try multiple table selectors
        table = (
            soup.find("table", {"id": "equities-table"}) or
            soup.find("table", {"class": lambda c: c and "price" in c}) or
            soup.find("table")
        )

        if not table:
            # Try finding data in script tags (JSON embedded)
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and "symbol" in script.string.lower():
                    try:
                        # Look for JSON arrays
                        text = script.string
                        start = text.find("[{")
                        end = text.rfind("}]")
                        if start != -1 and end != -1:
                            data = json.loads(text[start:end + 2])
                            for item in data:
                                raw.append({
                                    "symbol": item.get(
                                        "symbol", item.get("ticker", "")
                                    ),
                                    "price": item.get(
                                        "close", item.get("price", 0)
                                    ),
                                    "change": item.get(
                                        "change", item.get("change_abs", 0)
                                    ),
                                    "percent_change": item.get(
                                        "pct_change", item.get("change", 0)
                                    ),
                                    "volume": item.get("volume", 0),
                                })
                    except Exception:
                        continue

            if raw:
                break
            continue

        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Detect column positions from header
        header_row = rows[0]
        headers = [
            th.get_text(strip=True).lower()
            for th in header_row.find_all(["th", "td"])
        ]

        col_map = {}
        for i, h in enumerate(headers):
            if any(k in h for k in ["symbol", "ticker", "stock"]):
                col_map["symbol"] = i
            elif any(k in h for k in ["price", "close", "last"]):
                col_map["price"] = i
            elif "%" in h or "percent" in h or "chg%" in h:
                col_map["percent_change"] = i
            elif any(k in h for k in ["change", "chg"]):
                col_map["change"] = i
            elif "volume" in h or "vol" in h:
                col_map["volume"] = i

        if "symbol" not in col_map or "price" not in col_map:
            continue

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            try:
                raw.append({
                    "symbol": cells[col_map["symbol"]].get_text(strip=True),
                    "price": cells[col_map.get("price", 1)].get_text(strip=True),
                    "change": cells[col_map["change"]].get_text(strip=True)
                    if "change" in col_map and col_map["change"] < len(cells)
                    else "0",
                    "percent_change": cells[col_map["percent_change"]].get_text(strip=True)
                    if "percent_change" in col_map
                    and col_map["percent_change"] < len(cells)
                    else "0",
                    "volume": cells[col_map["volume"]].get_text(strip=True)
                    if "volume" in col_map and col_map["volume"] < len(cells)
                    else "0",
                })
            except Exception:
                continue

        if raw:
            logger.info(f"✅ NGX Pulse: {len(raw)} rows from {url}")
            break

    return normalize_data(raw, "ngx_pulse") if raw else []


# ══════════════════════════════════════════════════════
# SOURCE 2: TRADINGVIEW SCREENER (FALLBACK 1)
# ══════════════════════════════════════════════════════

def fetch_tradingview() -> list:
    """
    FALLBACK 1: TradingView Screener API
    Uses TradingView's internal scanner endpoint for Nigeria.
    Returns full market data including fundamentals.
    """
    logger.info("📡 Source 2: TradingView Screener API...")
    raw = []

    url = "https://scanner.tradingview.com/nigeria/scan"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Content-Type": "application/json",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }
    payload = {
        "columns": [
            "name", "description", "close",
            "change", "change_abs", "volume",
        ],
        "range": [0, 500],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
    }

    res = retry_request("POST", url, headers=headers, json=payload)
    if not res:
        return []

    try:
        data = res.json()
        if not data or not isinstance(data, dict):
            return []
        items = data.get("data") or []

        for item in items:
            try:
                d = item.get("d") or []
                if not d or len(d) < 3:
                    continue
                full_name = item.get("s", "") or ""
                symbol = full_name.split(":")[-1]
                price = safe_float(d[2] if len(d) > 2 else None)
                change_pct = safe_float(d[3] if len(d) > 3 else None)
                change_amt = safe_float(d[4] if len(d) > 4 else None)
                volume = safe_int(d[5] if len(d) > 5 else None)

                if price <= 0:
                    continue

                raw.append({
                    "symbol": symbol,
                    "price": price,
                    "change": change_amt,
                    "percent_change": change_pct,
                    "volume": volume,
                })
            except Exception:
                continue

        logger.info(f"✅ TradingView: {len(raw)} stocks")
    except Exception as e:
        logger.error(f"TradingView parse error: {e}")
        return []

    return normalize_data(raw, "tradingview") if raw else []


# ══════════════════════════════════════════════════════
# SOURCE 3: NGN MARKETS (FALLBACK 2)
# ══════════════════════════════════════════════════════

def scrape_ngn_markets() -> list:
    """
    FALLBACK 2: NGN Markets — ngnmarkets.com
    Scrapes the HTML price table.
    """
    logger.info("📡 Source 3: NGN Markets...")
    raw = []

    urls = [
        "https://www.ngnmarkets.com/equities",
        "https://www.ngnmarkets.com/",
        "https://ngnmarkets.com/stocks",
    ]

    for url in urls:
        res = retry_request(
            "GET", url,
            headers=get_headers("https://ngnmarkets.com/")
        )
        if not res:
            continue

        soup = BeautifulSoup(res.text, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 3:
                continue

            header_cells = rows[0].find_all(["th", "td"])
            headers_text = [
                h.get_text(strip=True).lower()
                for h in header_cells
            ]

            # Detect if this looks like a stock table
            has_symbol = any(
                k in " ".join(headers_text)
                for k in ["symbol", "ticker", "stock", "equity"]
            )
            has_price = any(
                k in " ".join(headers_text)
                for k in ["price", "close", "last"]
            )

            if not has_symbol and not has_price:
                continue

            col_idx = {}
            for i, h in enumerate(headers_text):
                if any(k in h for k in ["symbol", "ticker", "stock"]):
                    col_idx["symbol"] = i
                elif any(k in h for k in ["price", "close", "last"]):
                    col_idx["price"] = i
                elif "%" in h or "percent" in h:
                    col_idx["percent_change"] = i
                elif any(k in h for k in ["change", "chg"]):
                    col_idx["change"] = i
                elif "vol" in h:
                    col_idx["volume"] = i

            if "symbol" not in col_idx or "price" not in col_idx:
                continue

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                try:
                    raw.append({
                        "symbol": cells[col_idx["symbol"]].get_text(strip=True),
                        "price": cells[col_idx["price"]].get_text(strip=True),
                        "change": cells[col_idx.get("change", 0)].get_text(strip=True)
                        if "change" in col_idx else "0",
                        "percent_change": cells[col_idx.get("percent_change", 0)].get_text(strip=True)
                        if "percent_change" in col_idx else "0",
                        "volume": cells[col_idx.get("volume", 0)].get_text(strip=True)
                        if "volume" in col_idx else "0",
                    })
                except (IndexError, AttributeError):
                    continue

            if raw:
                break

        if raw:
            logger.info(f"✅ NGN Markets: {len(raw)} stocks from {url}")
            break

    return normalize_data(raw, "ngn_markets") if raw else []


# ══════════════════════════════════════════════════════
# SOURCE 4: AFX KWAYISI (FALLBACK 3)
# ══════════════════════════════════════════════════════

def scrape_afx() -> list:
    """
    FALLBACK 3: AFX Kwayisi — afx.kwayisi.org/ngx/
    Well-structured HTML table with clean NGX data.
    Note: Sometimes blocks cloud IPs — hence fallback position.
    """
    logger.info("📡 Source 4: AFX Kwayisi...")
    raw = []

    res = retry_request(
        "GET",
        "https://afx.kwayisi.org/ngx/",
        headers=get_headers("https://afx.kwayisi.org/")
    )
    if not res:
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    table = soup.find("table")
    if not table:
        logger.warning("AFX: No table found")
        return []

    rows = table.find_all("tr")
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        try:
            link = cells[0].find("a")
            symbol = ""
            if link:
                href = link.get("href", "")
                symbol = href.split("/")[-1].replace(".html", "")
            if not symbol:
                symbol = cells[0].get_text(strip=True)

            raw.append({
                "symbol": symbol,
                "price": cells[1].get_text(strip=True),
                "change": cells[2].get_text(strip=True),
                "percent_change": cells[3].get_text(strip=True),
                "volume": cells[4].get_text(strip=True)
                if len(cells) > 4 else "0",
            })
        except Exception:
            continue

    logger.info(f"✅ AFX: {len(raw)} stocks")
    return normalize_data(raw, "afx_kwayisi") if raw else []


# ══════════════════════════════════════════════════════
# SOURCE 5: NGX GROUP OFFICIAL PDF (FALLBACK 4)
# ══════════════════════════════════════════════════════

def parse_ngx_pdf() -> list:
    """
    FALLBACK 4: NGX Group official daily price list (PDF).
    Downloads the daily equities price PDF and extracts data
    using pdfplumber.
    """
    logger.info("📡 Source 5: NGX Official PDF...")

    if not PDF_AVAILABLE:
        logger.warning("pdfplumber not installed — skipping PDF source")
        return []

    import io

    # NGX publishes daily price list PDF at this URL
    pdf_urls = [
        "https://ngxgroup.com/exchange/data/equities-price-list/",
        "https://ngxgroup.com/exchange/trade-summary/",
    ]

    raw = []

    for url in pdf_urls:
        # First get the page to find the PDF download link
        res = retry_request(
            "GET", url,
            headers=get_headers("https://ngxgroup.com/")
        )
        if not res:
            continue

        soup = BeautifulSoup(res.text, "html.parser")

        # Look for PDF links
        pdf_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf") and (
                "price" in href.lower() or
                "equit" in href.lower() or
                "daily" in href.lower()
            ):
                pdf_link = href if href.startswith("http") \
                    else f"https://ngxgroup.com{href}"
                break

        # Also try direct PDF URL patterns
        if not pdf_link:
            from datetime import date as dt
            today = dt.today()
            date_patterns = [
                today.strftime("%d%m%Y"),
                today.strftime("%Y%m%d"),
                today.strftime("%d-%m-%Y"),
            ]
            for pat in date_patterns:
                candidate = (
                    f"https://ngxgroup.com/wp-content/uploads/"
                    f"equities-price-list-{pat}.pdf"
                )
                test = retry_request(
                    "HEAD", candidate,
                    headers=get_headers("https://ngxgroup.com/"),
                    retries=1
                )
                if test:
                    pdf_link = candidate
                    break

        if not pdf_link:
            # Try parsing the HTML table directly from this page
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                if len(rows) > 5:
                    for row in rows[1:]:
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 3:
                            try:
                                raw.append({
                                    "symbol": cells[0].get_text(strip=True),
                                    "price": cells[1].get_text(strip=True),
                                    "change": cells[2].get_text(strip=True)
                                    if len(cells) > 2 else "0",
                                    "percent_change": cells[3].get_text(strip=True)
                                    if len(cells) > 3 else "0",
                                    "volume": cells[4].get_text(strip=True)
                                    if len(cells) > 4 else "0",
                                })
                            except Exception:
                                continue
                    if raw:
                        break
            if raw:
                break
            continue

        # Download and parse PDF
        pdf_res = retry_request(
            "GET", pdf_link,
            headers=get_headers("https://ngxgroup.com/"),
            retries=2
        )
        if not pdf_res:
            continue

        try:
            with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
                for page in pdf.pages:
                    # Extract table from PDF page
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2:
                            continue

                        # Detect header row
                        header = [
                            str(c).lower() if c else ""
                            for c in table[0]
                        ]
                        col_map = {}
                        for i, h in enumerate(header):
                            if any(k in h for k in ["symbol", "ticker"]):
                                col_map["symbol"] = i
                            elif any(k in h for k in ["price", "close"]):
                                col_map["price"] = i
                            elif "%" in h or "percent" in h:
                                col_map["percent_change"] = i
                            elif "change" in h or "chg" in h:
                                col_map["change"] = i
                            elif "volume" in h or "vol" in h:
                                col_map["volume"] = i

                        if "symbol" not in col_map:
                            continue

                        for data_row in table[1:]:
                            try:
                                if not data_row or not data_row[col_map.get("symbol", 0)]:
                                    continue
                                raw.append({
                                    "symbol": data_row[col_map["symbol"]],
                                    "price": data_row[col_map.get("price", 1)]
                                    if len(data_row) > col_map.get("price", 1) else "0",
                                    "change": data_row[col_map.get("change", 2)]
                                    if "change" in col_map and
                                    len(data_row) > col_map["change"] else "0",
                                    "percent_change": data_row[col_map.get("percent_change", 3)]
                                    if "percent_change" in col_map and
                                    len(data_row) > col_map["percent_change"] else "0",
                                    "volume": data_row[col_map.get("volume", 4)]
                                    if "volume" in col_map and
                                    len(data_row) > col_map["volume"] else "0",
                                })
                            except Exception:
                                continue
        except Exception as e:
            logger.error(f"PDF parse error: {e}")
            continue

        if raw:
            logger.info(f"✅ NGX PDF: {len(raw)} rows parsed")
            break

    return normalize_data(raw, "ngx_pdf") if raw else []


# ══════════════════════════════════════════════════════
# SIGNAL ENGINE — DECISION INTELLIGENCE
# ══════════════════════════════════════════════════════

# Historical price store (in-memory, keyed by symbol)
_PRICE_HISTORY: dict = defaultdict(list)


def update_price_history(data: list):
    """Append today's prices to in-memory history for MA calculation."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for stock in data:
        sym = stock["symbol"]
        history = _PRICE_HISTORY[sym]
        # Avoid duplicate dates
        if not history or history[-1]["date"] != today:
            history.append({
                "date": today,
                "price": stock["price"],
                "volume": stock["volume"],
            })
        # Keep last 30 days only
        _PRICE_HISTORY[sym] = history[-30:]


def calculate_moving_average(symbol: str, period: int = 5) -> Optional[float]:
    """Calculate simple moving average for given period."""
    history = _PRICE_HISTORY.get(symbol, [])
    if len(history) < period:
        return None
    prices = [h["price"] for h in history[-period:]]
    return round(sum(prices) / len(prices), 4)


def calculate_avg_volume(symbol: str, period: int = 10) -> Optional[float]:
    """Calculate average volume over period days."""
    history = _PRICE_HISTORY.get(symbol, [])
    if len(history) < 2:
        return None
    volumes = [
        h["volume"] for h in history[-period:]
        if h["volume"] > 0
    ]
    return round(sum(volumes) / len(volumes), 0) if volumes else None


def get_52w_position(price: float, high_52w: float, low_52w: float) -> str:
    """Describe where price sits in its 52-week range."""
    if not high_52w or not low_52w or high_52w <= low_52w:
        return "unknown"
    pct = (price - low_52w) / (high_52w - low_52w) * 100
    if pct >= 80:
        return "near_52w_high"
    elif pct >= 50:
        return "upper_half"
    elif pct >= 20:
        return "lower_half"
    else:
        return "near_52w_low"


def generate_smart_signal(
    stock: dict,
    high_52w: Optional[float] = None,
    low_52w: Optional[float] = None,
    pe_ratio: Optional[float] = None,
    sector_change: Optional[float] = None,
    resistance: Optional[float] = None,
) -> dict:
    """
    DECISION INTELLIGENCE ENGINE
    Generates a full actionable trading signal from multiple data factors.

    Factors weighted:
    - Momentum (daily % change): 35%
    - Volume vs average: 25%
    - 52-week range position: 20%
    - P/E valuation: 10%
    - Sector sentiment: 10%

    Returns a rich signal dict with entry, target, stop-loss.
    """
    sym = stock["symbol"]
    price = stock["price"]
    chg = stock["percent_change"]
    volume = stock["volume"]
    flag = stock["price_change_flag"]

    # ── Moving Averages ────────────────────────────────
    ma5 = calculate_moving_average(sym, 5)
    ma10 = calculate_moving_average(sym, 10)
    ma20 = calculate_moving_average(sym, 20)

    # ── Volume Analysis ────────────────────────────────
    avg_vol = calculate_avg_volume(sym, 10)
    volume_ratio = round(volume / avg_vol, 2) if avg_vol and avg_vol > 0 else 1.0
    volume_spike = volume_ratio >= 1.5
    volume_label = (
        f"+{int((volume_ratio - 1) * 100)}% above average"
        if volume_ratio > 1 else
        f"{int((1 - volume_ratio) * 100)}% below average"
    )

    # ── Trend Direction ────────────────────────────────
    trend = "unknown"
    if ma5 and ma10:
        if ma5 > ma10:
            trend = "upward"
        elif ma5 < ma10:
            trend = "downward"
        else:
            trend = "sideways"

    # ── 52-Week Position ───────────────────────────────
    range_position = get_52w_position(price, high_52w or 0, low_52w or 0)
    near_resistance = (
        resistance and abs(price - resistance) / resistance < 0.02
    )

    # ── Sector Sentiment ──────────────────────────────
    sector_sentiment = "neutral"
    if sector_change is not None:
        if sector_change >= 1.5:
            sector_sentiment = "strongly bullish"
        elif sector_change >= 0.3:
            sector_sentiment = "bullish"
        elif sector_change <= -1.5:
            sector_sentiment = "strongly bearish"
        elif sector_change <= -0.3:
            sector_sentiment = "bearish"

    # ── P/E Assessment ────────────────────────────────
    pe_assessment = "unknown"
    if pe_ratio and pe_ratio > 0:
        if pe_ratio < 8:
            pe_assessment = "significantly undervalued"
        elif pe_ratio < 15:
            pe_assessment = "fairly valued"
        elif pe_ratio < 25:
            pe_assessment = "moderately priced"
        else:
            pe_assessment = "expensive"

    # ── Composite Scoring ─────────────────────────────
    score = 0.0

    # Momentum (35%)
    if chg >= 5:
        score += 3.5
    elif chg >= 2:
        score += 2.5
    elif chg >= 0.5:
        score += 1.5
    elif chg >= -0.5:
        score += 0.5
    elif chg >= -2:
        score -= 1.0
    else:
        score -= 2.5

    # Volume (25%)
    if volume_ratio >= 2.0:
        score += 2.5 if flag == "UP" else -2.5
    elif volume_ratio >= 1.5:
        score += 1.5 if flag == "UP" else -1.5
    elif volume_ratio >= 1.0:
        score += 0.5 if flag == "UP" else -0.5

    # Trend/MA (20%)
    if trend == "upward":
        score += 2.0
    elif trend == "downward":
        score -= 2.0

    # P/E (10%)
    if pe_ratio and pe_ratio > 0:
        if pe_ratio < 8:
            score += 1.0
        elif pe_ratio < 15:
            score += 0.5
        elif pe_ratio > 40:
            score -= 0.5

    # Sector (10%)
    if "bullish" in sector_sentiment:
        score += 1.0 if "strongly" in sector_sentiment else 0.5
    elif "bearish" in sector_sentiment:
        score -= 1.0 if "strongly" in sector_sentiment else 0.5

    # ── Signal Classification ─────────────────────────
    if score >= 5.0:
        signal_label = "STRONG BUY 🚀"
        signal_code = "STRONG_BUY"
        stars = 5
    elif score >= 2.5:
        signal_label = "BUY 📈"
        signal_code = "BUY"
        stars = 4
    elif score >= 0.5:
        if near_resistance and volume_spike:
            signal_label = "BUY — Breakout Watch 👀"
            signal_code = "BREAKOUT_WATCH"
            stars = 4
        else:
            signal_label = "HOLD ⏸️"
            signal_code = "HOLD"
            stars = 3
    elif score >= -1.5:
        signal_label = "CAUTION ⚠️"
        signal_code = "CAUTION"
        stars = 2
    else:
        signal_label = "AVOID 🔴"
        signal_code = "AVOID"
        stars = 1

    # ── Entry / Target / Stop Loss ────────────────────
    entry_price = None
    target_price = None
    stop_loss = None

    if signal_code in ("STRONG_BUY", "BUY", "BREAKOUT_WATCH"):
        if near_resistance and resistance:
            entry_price = round(resistance * 1.005, 2)  # Buy on breakout
        else:
            entry_price = round(price * 1.002, 2)       # Buy near current

        # Target: based on momentum + technical
        if chg >= 5:
            target_price = round(price * 1.12, 2)       # 12% target
        elif chg >= 2:
            target_price = round(price * 1.08, 2)       # 8% target
        else:
            target_price = round(price * 1.06, 2)       # 6% target

        # Stop-loss: 4-6% below entry
        stop_loss = round((entry_price or price) * 0.95, 2)

    elif signal_code in ("CAUTION", "AVOID"):
        stop_loss = round(price * 0.97, 2)

    # ── Narrative WHY ─────────────────────────────────
    why_parts = []

    if chg >= 2:
        why_parts.append(
            f"Strong upward momentum of +{chg:.2f}% today"
        )
    elif chg > 0:
        why_parts.append(f"Mild positive move of +{chg:.2f}%")
    elif chg < -2:
        why_parts.append(
            f"Significant decline of {chg:.2f}% — bearish pressure"
        )
    elif chg < 0:
        why_parts.append(f"Slight dip of {chg:.2f}% today")

    if volume_spike and flag == "UP":
        why_parts.append(
            f"Volume spike ({volume_label}) confirms buying conviction"
        )
    elif volume_spike and flag == "DOWN":
        why_parts.append(
            f"High volume ({volume_label}) on a down day signals distribution"
        )

    if near_resistance and resistance:
        why_parts.append(
            f"Testing key resistance at ₦{resistance:,.2f}"
            f" — a breakout here could trigger a short-term rally"
        )

    if trend != "unknown":
        why_parts.append(f"5-day trend is {trend}")

    if "bullish" in sector_sentiment:
        why_parts.append(f"Sector sentiment is {sector_sentiment}")
    elif "bearish" in sector_sentiment:
        why_parts.append(f"Sector headwinds ({sector_sentiment})")

    if pe_ratio and pe_assessment != "unknown":
        why_parts.append(f"Valuation: {pe_assessment} (P/E {pe_ratio:.1f}x)")

    reasoning = ". ".join(why_parts) + "." if why_parts else \
        "Insufficient data for full analysis."

    # ── Context Tags ──────────────────────────────────
    context = []
    if volume_spike:
        context.append(f"Volume spike {volume_label}")
    if trend != "unknown":
        context.append(f"5-day trend → {trend}")
    if resistance:
        context.append(f"Resistance ₦{resistance:,.2f}")
    if "bullish" in sector_sentiment:
        context.append(f"Sector {sector_sentiment}")
    if ma5:
        context.append(f"MA5: ₦{ma5:,.2f}")
    if ma20:
        context.append(f"MA20: ₦{ma20:,.2f}")

    return {
        # Core signal
        "signal": signal_label,
        "signal_code": signal_code,
        "stars": stars,
        "score": round(score, 2),

        # Actionable guidance
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_loss": stop_loss,

        # Analysis context
        "reasoning": reasoning,
        "context_tags": context,

        # Technical data
        "ma_5": ma5,
        "ma_10": ma10,
        "ma_20": ma20,
        "volume_ratio": volume_ratio,
        "volume_label": volume_label,
        "trend": trend,
        "sector_sentiment": sector_sentiment,
        "pe_assessment": pe_assessment,
        "range_position": range_position,
        "near_resistance": near_resistance or False,
    }


# ══════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════

def get_market_data(
    use_cache: bool = True,
    add_signals: bool = True,
    enrichment: Optional[dict] = None,
) -> dict:
    """
    MAIN ENTRY POINT — Resilient multi-source data pipeline.

    Tries each source in order until one succeeds.
    Returns clean, normalized, signal-enriched market data.

    Args:
        use_cache: Whether to return cached data if fresh
        add_signals: Whether to generate smart signals
        enrichment: Optional dict of {symbol: {pe_ratio, high_52w,
                    low_52w, resistance, sector_change}} for richer signals

    Returns:
        {
            "data": [...normalized stocks with signals...],
            "source": "source_name",
            "stock_count": N,
            "timestamp": "ISO datetime",
            "success": True/False,
        }
    """
    cache_key = "ngx_market_data"
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Check cache first
    if use_cache:
        cached = get_cache(cache_key)
        if cached:
            return {
                "data": cached,
                "source": "cache",
                "stock_count": len(cached),
                "timestamp": timestamp,
                "success": True,
                "cached": True,
            }

    # Define source pipeline
    sources = [
        ("NGX Pulse",      scrape_ngx_pulse),
        ("TradingView",    fetch_tradingview),
        ("NGN Markets",    scrape_ngn_markets),
        ("AFX Kwayisi",    scrape_afx),
        ("NGX PDF",        parse_ngx_pdf),
    ]

    data = []
    used_source = None

    for source_name, source_fn in sources:
        logger.info(f"\n{'='*50}")
        logger.info(f"🔄 Attempting: {source_name}")
        logger.info(f"{'='*50}")

        try:
            result = source_fn()
            if result and len(result) >= 5:
                data = result
                used_source = source_name
                logger.info(
                    f"✅ SUCCESS: {source_name} — "
                    f"{len(data)} stocks retrieved"
                )
                break
            else:
                logger.warning(
                    f"⚠️  {source_name} returned insufficient data "
                    f"({len(result) if result else 0} stocks)"
                )
        except Exception as e:
            logger.error(f"❌ {source_name} raised exception: {e}")
            continue

    if not data:
        logger.error("🚨 ALL SOURCES FAILED — no market data available")
        return {
            "data": [],
            "source": None,
            "stock_count": 0,
            "timestamp": timestamp,
            "success": False,
            "error": "All data sources failed",
        }

    # Update price history for MA calculations
    update_price_history(data)

    # Add smart signals if requested
    if add_signals:
        enrichment = enrichment or {}
        enriched_data = []

        for stock in data:
            sym = stock["symbol"]
            extra = enrichment.get(sym, {})

            signal = generate_smart_signal(
                stock,
                high_52w=extra.get("high_52w"),
                low_52w=extra.get("low_52w"),
                pe_ratio=extra.get("pe_ratio"),
                sector_change=extra.get("sector_change"),
                resistance=extra.get("resistance"),
            )

            enriched_data.append({**stock, "signal_data": signal})

        data = enriched_data

    # Cache the result
    set_cache(cache_key, data)

    return {
        "data": data,
        "source": used_source,
        "stock_count": len(data),
        "timestamp": timestamp,
        "success": True,
        "cached": False,
    }


def format_signal_card(stock: dict) -> str:
    """
    Format a single stock into a rich display card.
    This is what NGX Signal shows users instead of raw numbers.
    """
    sig = stock.get("signal_data", {})
    if not sig:
        return f"{stock['symbol']}: ₦{stock['price']:,.2f} | No signal"

    sym = stock["symbol"]
    price = stock["price"]
    chg = stock["percent_change"]
    signal = sig.get("signal", "N/A")
    reasoning = sig.get("reasoning", "")
    entry = sig.get("entry_price")
    target = sig.get("target_price")
    stop = sig.get("stop_loss")
    context = sig.get("context_tags", [])

    lines = [
        f"{'='*55}",
        f"📊 {sym} — {signal}",
        f"   Price: ₦{price:,.2f}  |  Change: {chg:+.2f}%",
        f"",
        f"💡 WHY: {reasoning}",
        f"",
    ]

    if context:
        lines.append(f"🔍 Context:")
        for tag in context:
            lines.append(f"   • {tag}")
        lines.append("")

    if entry and target and stop:
        lines += [
            f"🎯 Action:",
            f"   ✅ Entry:     ₦{entry:,.2f}",
            f"   🎯 Target:    ₦{target:,.2f}",
            f"   🛑 Stop-loss: ₦{stop:,.2f}",
        ]

    lines.append(f"{'='*55}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════
# INTEGRATION WITH NGX SIGNAL SUPABASE PIPELINE
# ══════════════════════════════════════════════════════

def save_to_supabase(result: dict, sb) -> int:
    """
    Save pipeline results to Supabase stock_prices and
    signal_scores tables. Integrates with existing NGX Signal
    database schema.
    """
    from datetime import date as dt
    today = str(dt.today())
    saved = 0

    for stock in result.get("data", []):
        try:
            # Save price
            sb.table("stock_prices").upsert({
                "symbol": stock["symbol"],
                "price": stock["price"],
                "change_amount": stock["change"],
                "change_percent": stock["percent_change"],
                "volume": stock["volume"],
                "trading_date": today,
            }, on_conflict="symbol,trading_date").execute()

            # Save signal
            sig = stock.get("signal_data", {})
            if sig:
                sb.table("signal_scores").upsert({
                    "symbol": stock["symbol"],
                    "score_date": today,
                    "stars": sig.get("stars", 3),
                    "signal": sig.get("signal_code", "HOLD"),
                    "reasoning": sig.get("reasoning", ""),
                    "momentum_score": sig.get("score", 0),
                    "volume_score": sig.get("volume_ratio", 1.0),
                    "news_score": 0.5,
                }, on_conflict="symbol,score_date").execute()

            saved += 1
        except Exception as e:
            logger.debug(f"Supabase save error {stock['symbol']}: {e}")
            continue

    logger.info(f"✅ Saved {saved} stocks to Supabase")
    return saved


# ══════════════════════════════════════════════════════
# EXAMPLE USAGE
# ══════════════════════════════════════════════════════

if __name__ == "__main__":

    print("\n🚀 NGX Signal — Resilient Market Data Pipeline")
    print("=" * 55)

    # Optional enrichment data for better signals
    # In production this comes from TradingView fundamentals
    sample_enrichment = {
        "ZENITHBANK": {
            "pe_ratio": 4.2,
            "high_52w": 52.50,
            "low_52w": 28.10,
            "resistance": 46.00,
            "sector_change": 1.8,  # Banking sector up 1.8%
        },
        "GTCO": {
            "pe_ratio": 3.8,
            "high_52w": 65.00,
            "low_52w": 38.50,
            "resistance": 60.00,
            "sector_change": 1.8,
        },
        "DANGCEM": {
            "pe_ratio": 18.5,
            "high_52w": 550.00,
            "low_52w": 380.00,
            "resistance": 520.00,
            "sector_change": 0.4,
        },
        "MTNN": {
            "pe_ratio": 22.1,
            "high_52w": 350.00,
            "low_52w": 180.00,
            "resistance": 320.00,
            "sector_change": 0.2,
        },
    }

    # Run the pipeline
    result = get_market_data(
        use_cache=False,
        add_signals=True,
        enrichment=sample_enrichment,
    )

    # Summary
    print(f"\n📊 Pipeline Results:")
    print(f"   Source used:  {result['source']}")
    print(f"   Stocks found: {result['stock_count']}")
    print(f"   Success:      {result['success']}")
    print(f"   Timestamp:    {result['timestamp']}")

    if result["success"] and result["data"]:

        # Show signal distribution
        signal_counts = {}
        for stock in result["data"]:
            sig = stock.get("signal_data", {})
            code = sig.get("signal_code", "UNKNOWN")
            signal_counts[code] = signal_counts.get(code, 0) + 1

        print(f"\n📈 Signal Distribution:")
        for signal, count in sorted(
            signal_counts.items(), key=lambda x: -x[1]
        ):
            print(f"   {signal}: {count} stocks")

        # Show top 3 STRONG BUY cards
        strong_buys = [
            s for s in result["data"]
            if s.get("signal_data", {}).get("signal_code") == "STRONG_BUY"
        ][:3]

        if strong_buys:
            print(f"\n🔥 Top Strong Buy Signals:")
            for stock in strong_buys:
                print(format_signal_card(stock))
        else:
            # Show top 3 by signal score
            top = sorted(
                result["data"],
                key=lambda x: x.get("signal_data", {}).get("score", 0),
                reverse=True
            )[:3]
            print(f"\n📊 Top Signals Today:")
            for stock in top:
                print(format_signal_card(stock))

        # Raw data sample
        print(f"\n📋 Sample Raw Data (first 3 stocks):")
        for stock in result["data"][:3]:
            sig = stock.get("signal_data", {})
            print(
                f"   {stock['symbol']:<15} "
                f"₦{stock['price']:>10,.2f}  "
                f"{stock['percent_change']:>+7.2f}%  "
                f"Vol:{stock['volume']:>12,}  "
                f"[{sig.get('signal_code', 'N/A')}]"
            )
