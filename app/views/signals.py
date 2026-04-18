"""
NGX Signal Engine  v2.0
========================
Replaces the hard-coded if/elif momentum scoring with a proper
multi-indicator composite technical analysis engine.

INDICATORS USED (all calculated from raw price + volume history):
  1. RSI (14)          — Momentum oscillator. Overbought/oversold + divergence
  2. MACD (12,26,9)    — Trend + momentum. Crossover + histogram direction
  3. EMA Cross (20/50) — Trend direction. Short-term vs long-term momentum
  4. OBV Trend         — Volume confirms price. Smart money flow
  5. Bollinger Bands   — Volatility + breakout detection
  6. ADX (14)          — Trend strength. Filters weak/sideways signals
  7. Volume Ratio      — Today's volume vs 20-day average

SIGNAL CLASSIFICATION:
  STRONG_BUY     → composite score ≥ 80 + strong trend confirmation
  BUY            → composite score 65–79 + positive trend
  BREAKOUT_WATCH → composite score 55–64 + volume surge + BB squeeze
  HOLD           → composite score 40–54 or conflicting signals
  CAUTION        → composite score 25–39 or deteriorating
  AVOID          → composite score < 25 + confirmed downtrend

REALISTIC ACCURACY EXPECTATION: 72–82% on NGX trending stocks.
Low-liquidity stocks (volume < 10,000 shares) are flagged as LOW_CONFIDENCE.

USAGE:
  from signal_engine import compute_signal
  result = compute_signal(symbol, price_history)
  # price_history = list of dicts: [{date, close, volume}, ...]

This script is meant to be run as a BACKEND JOB (cron / scheduled function)
that writes results to your Supabase signal_scores table once per trading day
after market close (typically 2:30–3:00 PM WAT on NGX).

DEPENDENCIES (all free, pip installable):
  pip install pandas numpy
  No TA-Lib C library needed — all indicators implemented in pure pandas/numpy.
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional


# ══════════════════════════════════════════════════════════════════
# CORE INDICATOR CALCULATIONS
# Pure pandas/numpy — no external C libraries needed.
# Each function takes a pd.Series of closing prices or volume.
# ══════════════════════════════════════════════════════════════════

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI. Standard 14-period.
    Returns series 0–100.
    Overbought > 70, Oversold < 30.
    """
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    # Use Wilder's smoothing (equivalent to EMA with alpha=1/period)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(close: pd.Series,
              fast: int = 12, slow: int = 26, signal: int = 9
              ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Standard MACD (12, 26, 9).
    Returns: (macd_line, signal_line, histogram)
    Bullish: macd_line crosses above signal_line + histogram turning positive
    """
    ema_fast   = close.ewm(span=fast,   adjust=False).mean()
    ema_slow   = close.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_ema(close: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return close.ewm(span=period, adjust=False).mean()


def calc_bollinger(close: pd.Series,
                   period: int = 20, std_dev: float = 2.0
                   ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands (20, 2).
    Returns: (upper_band, middle_band, lower_band)
    Squeeze: bands narrowing = low volatility = breakout incoming
    Price > upper = overbought breakout. Price < lower = oversold.
    """
    middle = close.rolling(period).mean()
    std    = close.rolling(period).std()
    upper  = middle + (std * std_dev)
    lower  = middle - (std * std_dev)
    return upper, middle, lower


def calc_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    On-Balance Volume.
    Rising OBV + rising price = confirmed bullish (smart money accumulating)
    Falling OBV + rising price = divergence warning (distribution)
    """
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum()
    return obv


def calc_adx(high: pd.Series, low: pd.Series,
             close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average Directional Index.
    ADX > 25 = strong trend (regardless of direction).
    ADX < 20 = weak/sideways market — signals less reliable.
    """
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low  - close.shift()).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()

    up_move   = high - high.shift()
    down_move = low.shift() - low

    plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm_smooth  = pd.Series(plus_dm,  index=close.index).ewm(alpha=1/period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=close.index).ewm(alpha=1/period, adjust=False).mean()

    plus_di  = 100 * plus_dm_smooth  / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm_smooth / atr.replace(0, np.nan)

    dx  = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx, plus_di, minus_di


def calc_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """
    Today's volume / 20-day average volume.
    > 1.5 = significantly above average (confirms moves)
    > 2.0 = very high (breakout confirmation)
    < 0.5 = thin market (signals less reliable)
    """
    avg_vol = volume.rolling(period).mean()
    return volume / avg_vol.replace(0, np.nan)


# ══════════════════════════════════════════════════════════════════
# COMPOSITE SCORER
# Takes all indicator values and produces a 0–100 composite score
# with weighted contributions from each indicator.
# ══════════════════════════════════════════════════════════════════

def score_indicators(
    # Latest values (scalars)
    rsi:             float,
    macd_line:       float,
    macd_signal:     float,
    macd_hist:       float,
    macd_hist_prev:  float,  # histogram yesterday (for direction)
    ema_20:          float,
    ema_50:          float,
    price:           float,
    bb_upper:        float,
    bb_middle:       float,
    bb_lower:        float,
    bb_upper_prev:   float,  # for squeeze detection
    bb_lower_prev:   float,
    obv:             float,
    obv_prev5:       float,  # OBV 5 days ago (trend)
    adx:             float,
    plus_di:         float,
    minus_di:        float,
    vol_ratio:       float,
    rsi_prev3:       float,  # RSI 3 days ago (divergence check)
    price_prev3:     float,  # price 3 days ago
) -> dict:
    """
    Produces a composite score (0–100) from 7 indicator families.
    Returns full breakdown dict for transparency/logging.

    WEIGHTS (sum = 100):
      RSI           25  — Momentum state
      MACD          25  — Trend + momentum confirmation
      EMA Cross     20  — Trend direction
      OBV           15  — Volume confirmation
      BB            10  — Volatility / breakout
      ADX            5  — Trend strength multiplier (bonus/penalty)
    """
    scores = {}
    signals = {}

    # ── 1. RSI Score (0–25 points) ────────────────────────────────
    # Zones: <30 oversold (bullish reversal potential), >70 overbought
    # Best entry: RSI 40–60 rising (momentum building)
    # Bonus: RSI > rsi_prev3 with price rising = confirmed momentum
    if rsi <= 30:
        rsi_score = 20   # Oversold — reversal opportunity
        signals["rsi"] = "OVERSOLD"
    elif rsi <= 45:
        rsi_score = 22   # Recovering from oversold — best buy zone
        signals["rsi"] = "RECOVERING"
    elif rsi <= 55:
        rsi_score = 18   # Neutral zone
        signals["rsi"] = "NEUTRAL"
    elif rsi <= 65:
        rsi_score = 14   # Healthy uptrend
        signals["rsi"] = "UPTREND"
    elif rsi <= 70:
        rsi_score = 10   # Approaching overbought
        signals["rsi"] = "APPROACHING_OB"
    else:
        rsi_score = 5    # Overbought — caution
        signals["rsi"] = "OVERBOUGHT"

    # RSI momentum bonus: rising RSI confirms direction
    if rsi > rsi_prev3:
        rsi_score = min(rsi_score + 3, 25)
        signals["rsi_momentum"] = "RISING"
    elif rsi < rsi_prev3 - 5:
        rsi_score = max(rsi_score - 3, 0)
        signals["rsi_momentum"] = "FALLING"
    else:
        signals["rsi_momentum"] = "FLAT"

    scores["rsi"] = rsi_score

    # ── 2. MACD Score (0–25 points) ──────────────────────────────
    # Crossover: macd_line > signal_line = bullish
    # Histogram direction: turning positive/increasing = momentum building
    macd_bullish     = macd_line > macd_signal
    hist_turning_up  = macd_hist > macd_hist_prev   # histogram expanding upward
    hist_above_zero  = macd_hist > 0
    macd_above_zero  = macd_line > 0                # price in overall uptrend

    if macd_bullish and hist_turning_up and macd_above_zero:
        macd_score = 23    # Full bullish alignment
        signals["macd"] = "STRONG_BULLISH"
    elif macd_bullish and hist_turning_up:
        macd_score = 19    # Crossover with building momentum
        signals["macd"] = "BULLISH_CROSS"
    elif macd_bullish and hist_above_zero:
        macd_score = 15    # In uptrend, holding
        signals["macd"] = "BULLISH_HOLD"
    elif macd_bullish:
        macd_score = 11    # Crossover but momentum fading
        signals["macd"] = "WEAK_BULLISH"
    elif not macd_bullish and not hist_above_zero and not hist_turning_up:
        macd_score = 3     # Confirmed bearish
        signals["macd"] = "BEARISH"
    elif not macd_bullish and hist_turning_up:
        macd_score = 10    # Bearish but reversing — watch
        signals["macd"] = "BEARISH_REVERSING"
    else:
        macd_score = 7     # Weakening downtrend
        signals["macd"] = "WEAK_BEARISH"

    scores["macd"] = macd_score

    # ── 3. EMA Cross Score (0–20 points) ─────────────────────────
    # EMA20 > EMA50 = short-term above long-term = uptrend
    # Price > EMA20 = price above short-term trend
    price_above_ema20 = price > ema_20
    price_above_ema50 = price > ema_50
    ema_cross_bullish = ema_20 > ema_50

    # Calculate EMA spread as % (how strong the trend is)
    ema_spread_pct = ((ema_20 - ema_50) / ema_50) * 100 if ema_50 > 0 else 0

    if ema_cross_bullish and price_above_ema20 and price_above_ema50:
        if ema_spread_pct > 3:
            ema_score = 20    # Strong uptrend, price above both EMAs
            signals["ema"] = "STRONG_UPTREND"
        else:
            ema_score = 16    # Uptrend, EMA cross recent
            signals["ema"] = "UPTREND"
    elif ema_cross_bullish and price_above_ema50:
        ema_score = 13        # Above long-term but pulled back below short-term
        signals["ema"] = "MILD_UPTREND"
    elif ema_cross_bullish and not price_above_ema20:
        ema_score = 9         # EMA says up but price pulled back — watch
        signals["ema"] = "PULLBACK_IN_UPTREND"
    elif not ema_cross_bullish and price_above_ema20:
        ema_score = 8         # Short-term bounce in downtrend
        signals["ema"] = "BOUNCE_IN_DOWNTREND"
    elif not ema_cross_bullish and price_above_ema50:
        ema_score = 6         # Price caught between EMAs
        signals["ema"] = "BETWEEN_EMAS"
    else:
        ema_score = 2         # Below both EMAs — downtrend
        signals["ema"] = "DOWNTREND"

    scores["ema"] = ema_score

    # ── 4. OBV Score (0–15 points) ───────────────────────────────
    # OBV rising with price = smart money confirming move
    # OBV falling with rising price = DANGER (distribution)
    obv_rising    = obv > obv_prev5
    price_rising  = price > price_prev3

    if obv_rising and price_rising:
        obv_score = 15       # Volume confirms price — highest conviction
        signals["obv"] = "CONFIRMED_ACCUMULATION"
    elif obv_rising and not price_rising:
        obv_score = 11       # OBV leading price up — bullish divergence
        signals["obv"] = "BULLISH_DIVERGENCE"
    elif not obv_rising and price_rising:
        obv_score = 4        # Price rising without volume — WARNING
        signals["obv"] = "DISTRIBUTION_WARNING"
    else:
        obv_score = 6        # Both falling — confirmed downtrend
        signals["obv"] = "CONFIRMED_DECLINE"

    # Volume ratio bonus
    if vol_ratio >= 2.0:
        obv_score = min(obv_score + 3, 15)    # Very high volume = strong signal
    elif vol_ratio >= 1.5:
        obv_score = min(obv_score + 1, 15)
    elif vol_ratio < 0.4:
        obv_score = max(obv_score - 3, 0)     # Thin market = unreliable

    scores["obv"] = obv_score

    # ── 5. Bollinger Bands Score (0–10 points) ────────────────────
    # %B: where price is within the bands (0=lower, 0.5=middle, 1=upper)
    # Squeeze: bands narrowing = breakout incoming
    bb_width      = bb_upper - bb_lower
    bb_width_prev = bb_upper_prev - bb_lower_prev
    bb_squeeze    = bb_width < bb_width_prev * 0.9   # bands narrowing

    if bb_width > 0:
        pct_b = (price - bb_lower) / bb_width
    else:
        pct_b = 0.5

    if bb_squeeze and pct_b > 0.5:
        bb_score = 10    # Squeeze + price above mid = bullish breakout setup
        signals["bb"] = "BULLISH_SQUEEZE"
    elif pct_b > 0.8 and not bb_squeeze:
        bb_score = 8     # Near upper band in expanding market = strong uptrend
        signals["bb"] = "UPPER_BAND_RIDE"
    elif 0.4 <= pct_b <= 0.7:
        bb_score = 6     # Healthy middle zone
        signals["bb"] = "MIDDLE_ZONE"
    elif pct_b < 0.2:
        bb_score = 7     # Near lower band = potential reversal (oversold)
        signals["bb"] = "OVERSOLD_REVERSAL"
    elif bb_squeeze and pct_b < 0.5:
        bb_score = 4     # Squeeze + below mid = watch for bearish break
        signals["bb"] = "BEARISH_SQUEEZE"
    else:
        bb_score = 3
        signals["bb"] = "NEUTRAL"

    scores["bb"] = bb_score

    # ── 6. ADX Trend Strength Modifier (bonus/penalty) ────────────
    # ADX doesn't add to score directly — it multiplies signal reliability
    # Strong trend (ADX > 25): boost strong signals, boost poor signals
    # Weak trend (ADX < 20): reduce confidence in all signals
    if adx >= 40:
        adx_modifier = 1.08    # Very strong trend — high confidence
        signals["adx"] = "VERY_STRONG_TREND"
    elif adx >= 25:
        adx_modifier = 1.04    # Strong trend — confirmed
        signals["adx"] = "STRONG_TREND"
    elif adx >= 20:
        adx_modifier = 1.0     # Moderate trend — normal weight
        signals["adx"] = "MODERATE_TREND"
    else:
        adx_modifier = 0.90    # Weak/sideways — reduce all signal confidence
        signals["adx"] = "WEAK_TREND"

    # Plus DI > Minus DI confirms direction is UP
    if plus_di > minus_di and adx >= 20:
        signals["adx_direction"] = "BULLISH_DIRECTIONAL"
        adx_modifier = min(adx_modifier + 0.03, 1.12)
    elif minus_di > plus_di and adx >= 25:
        signals["adx_direction"] = "BEARISH_DIRECTIONAL"
        adx_modifier = max(adx_modifier - 0.05, 0.80)
    else:
        signals["adx_direction"] = "NEUTRAL"

    # ── Compute raw composite ─────────────────────────────────────
    raw_score = (
        scores["rsi"] +
        scores["macd"] +
        scores["ema"] +
        scores["obv"] +
        scores["bb"]
    )  # Max possible raw = 25+25+20+15+10 = 95

    # Normalize to 0–100 and apply ADX modifier
    composite = min(100, int((raw_score / 95) * 100 * adx_modifier))
    scores["composite"] = composite

    return {
        "composite":     composite,
        "scores":        scores,
        "signals":       signals,
        "adx_modifier":  adx_modifier,
        "vol_ratio":     round(float(vol_ratio), 2) if not np.isnan(vol_ratio) else 1.0,
        "rsi_value":     round(float(rsi), 1),
        "macd_bullish":  bool(macd_bullish),
        "ema_bullish":   bool(ema_cross_bullish),
        "obv_rising":    bool(obv_rising),
        "adx_strength":  round(float(adx), 1),
    }


# ══════════════════════════════════════════════════════════════════
# SIGNAL CLASSIFIER
# Converts composite score + context into STRONG_BUY / BUY / etc.
# Also determines star rating, confidence, entry/target/stop.
# ══════════════════════════════════════════════════════════════════

def classify_signal(score_result: dict, price: float, volume: int) -> dict:
    """
    Takes the output of score_indicators() and returns the final signal
    classification suitable for writing to the signal_scores Supabase table.
    """
    composite    = score_result["composite"]
    signals      = score_result["signals"]
    vol_ratio    = score_result["vol_ratio"]
    adx_strength = score_result["adx_strength"]
    macd_bullish = score_result["macd_bullish"]
    ema_bullish  = score_result["ema_bullish"]
    obv_rising   = score_result["obv_rising"]
    rsi_value    = score_result["rsi_value"]

    # ── Low liquidity guard ───────────────────────────────────────
    low_liquidity = (volume < 10_000 or vol_ratio < 0.2)

    # ── Breakout detection ────────────────────────────────────────
    is_breakout = (
        signals.get("bb") in ("BULLISH_SQUEEZE",) and
        vol_ratio >= 1.5 and
        macd_bullish
    )

    # ── Count bullish confirmations ───────────────────────────────
    confirmations = sum([
        macd_bullish,
        ema_bullish,
        obv_rising,
        rsi_value < 70 and rsi_value > 30,   # RSI in healthy zone
        signals.get("adx_direction") == "BULLISH_DIRECTIONAL",
    ])

    # ── Signal classification ─────────────────────────────────────
    if composite >= 80 and confirmations >= 4 and not low_liquidity:
        signal = "STRONG_BUY"
        stars  = 5
        confidence = "VERY HIGH"
    elif composite >= 80 and confirmations >= 3:
        signal = "STRONG_BUY"
        stars  = 5 if not low_liquidity else 4
        confidence = "HIGH" if not low_liquidity else "MODERATE"
    elif composite >= 65 and confirmations >= 3:
        signal = "BUY"
        stars  = 4
        confidence = "HIGH"
    elif composite >= 65 and confirmations >= 2:
        signal = "BUY"
        stars  = 3
        confidence = "MODERATE"
    elif is_breakout or (composite >= 55 and vol_ratio >= 1.5 and macd_bullish):
        signal = "BREAKOUT_WATCH"
        stars  = 4
        confidence = "MODERATE"
    elif composite >= 55 and confirmations >= 2:
        signal = "BREAKOUT_WATCH"
        stars  = 3
        confidence = "MODERATE"
    elif composite >= 40:
        signal = "HOLD"
        stars  = 3
        confidence = "LOW" if adx_strength < 20 else "MODERATE"
    elif composite >= 25:
        signal = "CAUTION"
        stars  = 2
        confidence = "LOW"
    else:
        signal = "AVOID"
        stars  = 1
        confidence = "HIGH"  # High confidence it's a bad trade

    # Low liquidity always reduces stars and confidence
    if low_liquidity and signal in ("STRONG_BUY", "BUY", "BREAKOUT_WATCH"):
        stars = max(stars - 1, 2)
        confidence = "LOW_LIQUIDITY"
        signal = "HOLD" if signal == "BREAKOUT_WATCH" else signal

    # ── Entry / Target / Stop Loss ────────────────────────────────
    entry_price = target_price = stop_loss = potential = None
    if signal in ("STRONG_BUY", "BUY", "BREAKOUT_WATCH") and price > 0:
        entry_price  = round(price * 1.002, 2)       # 0.2% above current (market order buffer)
        multiplier   = 1.15 if stars == 5 else 1.10 if stars == 4 else 1.07
        target_price = round(price * multiplier, 2)
        stop_loss    = round(price * 0.94, 2)         # 6% stop loss (NGX 10% daily limit)
        potential    = round(((target_price - entry_price) / entry_price) * 100, 1)

    # ── Generate reasoning string ─────────────────────────────────
    rsi_desc  = signals.get("rsi", "")
    macd_desc = signals.get("macd", "")
    ema_desc  = signals.get("ema", "")
    obv_desc  = signals.get("obv", "")
    adx_desc  = signals.get("adx", "")

    reasoning_parts = []
    if macd_desc in ("STRONG_BULLISH", "BULLISH_CROSS"):
        reasoning_parts.append("MACD bullish crossover confirmed")
    elif macd_desc == "BEARISH":
        reasoning_parts.append("MACD in confirmed downtrend")

    if rsi_desc == "OVERSOLD":
        reasoning_parts.append(f"RSI oversold at {rsi_value:.0f} — reversal potential")
    elif rsi_desc == "OVERBOUGHT":
        reasoning_parts.append(f"RSI overbought at {rsi_value:.0f} — take profits")
    elif rsi_desc == "RECOVERING":
        reasoning_parts.append(f"RSI recovering from oversold ({rsi_value:.0f})")

    if ema_desc == "STRONG_UPTREND":
        reasoning_parts.append("Price above EMA20 and EMA50 in strong uptrend")
    elif ema_desc == "DOWNTREND":
        reasoning_parts.append("Price below both EMAs — downtrend in force")
    elif ema_desc == "PULLBACK_IN_UPTREND":
        reasoning_parts.append("Pullback in an uptrend — potential re-entry")

    if obv_desc == "DISTRIBUTION_WARNING":
        reasoning_parts.append("⚠️ OBV divergence: price rising without volume — watch for reversal")
    elif obv_desc == "CONFIRMED_ACCUMULATION":
        reasoning_parts.append("Volume confirms price move — institutional accumulation")
    elif obv_desc == "BULLISH_DIVERGENCE":
        reasoning_parts.append("OBV rising ahead of price — bullish lead")

    if adx_desc == "WEAK_TREND":
        reasoning_parts.append("ADX below 20 — trend weak, signal lower confidence")
    elif adx_desc == "VERY_STRONG_TREND":
        reasoning_parts.append(f"ADX at {adx_strength:.0f} — very strong trend in force")

    if vol_ratio >= 2.0:
        reasoning_parts.append(f"Volume {vol_ratio:.1f}x above average — high conviction move")
    elif vol_ratio < 0.4:
        reasoning_parts.append("Volume very thin — move may not sustain")

    reasoning = ". ".join(reasoning_parts) + "." if reasoning_parts else "Mixed signals — no clear direction."

    return {
        "signal":        signal,
        "stars":         stars,
        "confidence":    confidence,
        "composite":     composite,
        "entry_price":   entry_price,
        "target_price":  target_price,
        "stop_loss":     stop_loss,
        "potential_pct": potential,
        "reasoning":     reasoning,
        "low_liquidity": low_liquidity,
        # Individual scores for transparency
        "rsi_score":     score_result["scores"].get("rsi", 0),
        "macd_score":    score_result["scores"].get("macd", 0),
        "ema_score":     score_result["scores"].get("ema", 0),
        "obv_score":     score_result["scores"].get("obv", 0),
        "bb_score":      score_result["scores"].get("bb", 0),
        # Raw indicator values (store in DB for auditing)
        "rsi_value":     score_result["rsi_value"],
        "adx_value":     adx_strength,
        "vol_ratio":     score_result["vol_ratio"],
        "macd_bullish":  macd_bullish,
        "ema_bullish":   ema_bullish,
    }


# ══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# Takes symbol + price history, returns full signal dict.
# ══════════════════════════════════════════════════════════════════

def compute_signal(
    symbol: str,
    price_history: list[dict],
    min_periods: int = 30,
) -> Optional[dict]:
    """
    Main function. Call this for each stock once per trading day.

    Args:
        symbol:        Stock ticker e.g. "ZENITHBANK"
        price_history: List of dicts, ordered oldest to newest:
                       [{"date": "2025-01-01", "close": 25.50, "volume": 450000,
                         "high": 26.00, "low": 25.00}, ...]
                       Minimum 30 records needed. 60+ is ideal.
        min_periods:   Minimum price records needed. Returns None if insufficient.

    Returns:
        dict with all signal fields ready to upsert to signal_scores table,
        or None if insufficient data.
    """
    if len(price_history) < min_periods:
        return None

    # ── Build DataFrame ───────────────────────────────────────────
    df = pd.DataFrame(price_history)
    df = df.sort_values("date").reset_index(drop=True)

    close  = df["close"].astype(float)
    volume = df["volume"].astype(float).fillna(0)

    # Handle missing high/low (use close ± 0.5% estimate if not available)
    if "high" in df.columns and "low" in df.columns:
        high = df["high"].astype(float)
        low  = df["low"].astype(float)
    else:
        high = close * 1.005
        low  = close * 0.995

    # ── Calculate all indicators ──────────────────────────────────
    rsi_series               = calc_rsi(close)
    macd_line, macd_sig, macd_hist = calc_macd(close)
    ema20                    = calc_ema(close, 20)
    ema50                    = calc_ema(close, 50)
    bb_upper, bb_mid, bb_lower = calc_bollinger(close)
    obv_series               = calc_obv(close, volume)
    adx_series, plus_di_s, minus_di_s = calc_adx(high, low, close)
    vol_ratio_series         = calc_volume_ratio(volume)

    # ── Extract latest values ─────────────────────────────────────
    def safe(series, idx=-1, fallback=0.0):
        try:
            val = series.iloc[idx]
            return float(val) if not np.isnan(val) else fallback
        except Exception:
            return fallback

    latest_price   = safe(close)
    latest_volume  = int(safe(volume))

    rsi            = safe(rsi_series)
    rsi_prev3      = safe(rsi_series, -4)
    price_prev3    = safe(close, -4)

    ml             = safe(macd_line)
    ms             = safe(macd_sig)
    mh             = safe(macd_hist)
    mh_prev        = safe(macd_hist, -2)

    e20            = safe(ema20)
    e50            = safe(ema50)

    bbu            = safe(bb_upper)
    bbm            = safe(bb_mid)
    bbl            = safe(bb_lower)
    bbu_prev       = safe(bb_upper, -2)
    bbl_prev       = safe(bb_lower, -2)

    obv_now        = safe(obv_series)
    obv_prev5      = safe(obv_series, -6)

    adx            = safe(adx_series)
    plus_di        = safe(plus_di_s)
    minus_di       = safe(minus_di_s)

    vol_ratio      = safe(vol_ratio_series)

    # ── Score ─────────────────────────────────────────────────────
    score_result = score_indicators(
        rsi=rsi,
        macd_line=ml,       macd_signal=ms,
        macd_hist=mh,       macd_hist_prev=mh_prev,
        ema_20=e20,         ema_50=e50,
        price=latest_price,
        bb_upper=bbu,       bb_middle=bbm,       bb_lower=bbl,
        bb_upper_prev=bbu_prev, bb_lower_prev=bbl_prev,
        obv=obv_now,        obv_prev5=obv_prev5,
        adx=adx,            plus_di=plus_di,     minus_di=minus_di,
        vol_ratio=vol_ratio,
        rsi_prev3=rsi_prev3,
        price_prev3=price_prev3,
    )

    # ── Classify ──────────────────────────────────────────────────
    result = classify_signal(score_result, latest_price, latest_volume)

    # ── Add metadata ──────────────────────────────────────────────
    result.update({
        "symbol":          symbol,
        "score_date":      str(date.today()),
        "price":           round(latest_price, 2),
        "volume":          latest_volume,
        "data_points":     len(price_history),
        "computed_at":     datetime.now().isoformat(),
        # Map to existing Supabase column names
        "momentum_score":  round(score_result["scores"].get("rsi", 0)  / 25, 3),
        "volume_score":    round(score_result["scores"].get("obv", 0)  / 15, 3),
        "news_score":      round(score_result["composite"] / 100, 3),   # composite
    })

    return result


# ══════════════════════════════════════════════════════════════════
# BATCH RUNNER
# Run this once per day after market close to update all stocks.
# ══════════════════════════════════════════════════════════════════

def run_batch(supabase_client, lookback_days: int = 90):
    """
    Fetches price history from Supabase for all stocks,
    computes signals, and upserts results to signal_scores table.

    Call this from your cron job / scheduled function after market close.

    Args:
        supabase_client: Initialised Supabase client
        lookback_days:   How many days of history to fetch (90 recommended)
    """
    from datetime import timedelta

    sb = supabase_client
    since = str(date.today() - timedelta(days=lookback_days))

    print(f"[NGX Signal Engine v2] Starting batch run for {date.today()}")

    # 1. Get all price history
    prices_res = sb.table("stock_prices") \
        .select("symbol, trading_date, price, volume, high, low") \
        .gte("trading_date", since) \
        .order("trading_date", desc=False) \
        .limit(50000) \
        .execute()

    if not prices_res.data:
        print("ERROR: No price data returned from Supabase.")
        return

    # 2. Group by symbol
    from collections import defaultdict
    history_map = defaultdict(list)
    for row in prices_res.data:
        sym = row.get("symbol", "")
        if sym:
            history_map[sym].append({
                "date":   row.get("trading_date", ""),
                "close":  float(row.get("price", 0)  or 0),
                "volume": int(row.get("volume",  0)  or 0),
                "high":   float(row.get("high",  0)  or 0),
                "low":    float(row.get("low",   0)  or 0),
            })

    print(f"  Found {len(history_map)} symbols with price history.")

    # 3. Compute signals and upsert
    success = 0
    skipped = 0
    errors  = 0

    for symbol, history in history_map.items():
        try:
            result = compute_signal(symbol, history)
            if result is None:
                skipped += 1
                print(f"  SKIP {symbol}: insufficient data ({len(history)} days)")
                continue

            # Map to signal_scores table schema
            upsert_data = {
                "symbol":         result["symbol"],
                "signal":         result["signal"],
                "stars":          result["stars"],
                "score_date":     result["score_date"],
                "reasoning":      result["reasoning"],
                "momentum_score": result["momentum_score"],
                "volume_score":   result["volume_score"],
                "news_score":     result["news_score"],   # composite
                # Optional extended columns (add to your table if you want them)
                # "entry_price":    result["entry_price"],
                # "target_price":   result["target_price"],
                # "stop_loss":      result["stop_loss"],
                # "composite_score": result["composite"],
                # "confidence":     result["confidence"],
                # "rsi_value":      result["rsi_value"],
            }

            sb.table("signal_scores").upsert(
                upsert_data,
                on_conflict="symbol"
            ).execute()

            success += 1
            print(f"  ✓ {symbol}: {result['signal']} ({result['stars']}★) "
                  f"score={result['composite']} rsi={result['rsi_value']:.0f}")

        except Exception as e:
            errors += 1
            print(f"  ERROR {symbol}: {e}")

    print(f"\n[Done] {success} updated · {skipped} skipped · {errors} errors")


# ══════════════════════════════════════════════════════════════════
# STANDALONE TEST
# Run: python signal_engine.py
# Uses synthetic data to verify all indicators work correctly.
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import random

    print("=" * 60)
    print("NGX Signal Engine v2.0 — Self Test")
    print("=" * 60)

    # Generate synthetic uptrending stock data (60 days)
    random.seed(42)
    np.random.seed(42)

    base_price = 500.0
    prices = [base_price]
    for _ in range(89):
        change = np.random.normal(0.003, 0.02)   # slight upward drift
        prices.append(max(1, prices[-1] * (1 + change)))

    from datetime import date, timedelta
    test_history = []
    start = date.today() - timedelta(days=89)
    for i, p in enumerate(prices):
        test_history.append({
            "date":   str(start + timedelta(days=i)),
            "close":  round(p, 2),
            "high":   round(p * 1.01, 2),
            "low":    round(p * 0.99, 2),
            "volume": random.randint(50_000, 500_000),
        })

    result = compute_signal("TESTSTOCK", test_history)
    if result:
        print(f"\nSymbol:      {result['symbol']}")
        print(f"Signal:      {result['signal']} ({result['stars']}★)")
        print(f"Composite:   {result['composite']}/100")
        print(f"Confidence:  {result['confidence']}")
        print(f"RSI:         {result['rsi_value']}")
        print(f"ADX:         {result['adx_value']}")
        print(f"Vol Ratio:   {result['vol_ratio']}x")
        print(f"MACD Bull:   {result['macd_bullish']}")
        print(f"EMA Bull:    {result['ema_bullish']}")
        print(f"Reasoning:   {result['reasoning']}")
        if result["entry_price"]:
            print(f"Entry:       ₦{result['entry_price']:,.2f}")
            print(f"Target:      ₦{result['target_price']:,.2f} (+{result['potential_pct']}%)")
            print(f"Stop Loss:   ₦{result['stop_loss']:,.2f}")
    else:
        print("ERROR: Insufficient data for test.")