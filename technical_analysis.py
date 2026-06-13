"""
Technical analysis module using Birdeye OHLCV candle data.

Provides RSI, Fibonacci retracement, VWAP, volume profile,
support/resistance detection, and momentum shift analysis
for Solana memecoin evaluation.
"""

import time
import requests
from dataclasses import dataclass, field

from config import (
    BIRDEYE_API_KEY, BIRDEYE_API,
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    OHLCV_1M_CANDLES, OHLCV_5M_CANDLES,
    FIB_LEVELS, FIB_PROXIMITY_PCT,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Data class
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TAResult:
    available: bool = False
    # Fibonacci
    swing_high: float = 0.0
    swing_low: float = 0.0
    ath: float = 0.0
    retracement_from_ath_pct: float = 0.0
    fib_levels: dict = field(default_factory=dict)
    nearest_fib: float = 0.0
    nearest_fib_level: float = 0.0
    fib_proximity_pct: float = 100.0
    # RSI
    rsi_1m: float = 50.0
    rsi_5m: float = 50.0
    rsi_signal: str = "NEUTRAL"
    # VWAP
    vwap: float = 0.0
    price_vs_vwap_pct: float = 0.0
    vwap_reclaim: bool = False
    # Volume
    volume_trend: str = "UNKNOWN"
    volume_recovery_ratio: float = 1.0
    # Support/Resistance
    support_levels: list = field(default_factory=list)
    resistance_levels: list = field(default_factory=list)
    # Momentum
    momentum_shift: float = 0.0
    momentum_signal: str = "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════════════════
# Birdeye OHLCV fetch
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_ohlcv(mint_address: str, interval: str, limit: int) -> list:
    """Fetch OHLCV candle data from Birdeye.

    Args:
        mint_address: Solana token mint address.
        interval: Candle interval (e.g. "1m", "5m").
        limit: Number of candles to fetch.

    Returns:
        List of candle dicts with keys o, h, l, c, v, unixTime,
        or empty list on any error.
    """
    try:
        now = int(time.time())
        # Map interval string to seconds per candle
        interval_seconds = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1H": 3600,
            "4H": 14400,
            "1D": 86400,
        }
        seconds_per_candle = interval_seconds.get(interval, 60)
        time_from = now - (limit * seconds_per_candle)

        resp = requests.get(
            f"{BIRDEYE_API}/defi/ohlcv",
            params={
                "type": interval,
                "address": mint_address,
                "time_from": time_from,
                "time_to": now,
            },
            headers={
                "X-API-KEY": BIRDEYE_API_KEY,
                "x-chain": "solana",
            },
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        return items if isinstance(items, list) else []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# RSI — Wilder's smoothed
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_rsi(closes: list, period: int = RSI_PERIOD) -> float:
    """Calculate RSI using Wilder's smoothing method.

    Args:
        closes: List of closing prices (oldest first).
        period: Look-back period (default from config).

    Returns:
        RSI value between 0 and 100, or 50.0 if insufficient data.
    """
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    # Seed averages with simple mean of first `period` deltas
    gains = [d if d > 0 else 0.0 for d in deltas[:period]]
    losses = [-d if d < 0 else 0.0 for d in deltas[:period]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # Wilder's smoothing for remaining deltas
    for d in deltas[period:]:
        gain = d if d > 0 else 0.0
        loss = -d if d < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# Fibonacci retracement
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_fibonacci(high: float, low: float, current_price: float) -> dict:
    """Calculate Fibonacci retracement levels from a swing high/low range.

    Args:
        high: Swing high price.
        low: Swing low price.
        current_price: Current token price.

    Returns:
        Dictionary with keys: fib_levels, nearest_fib, nearest_fib_level,
        fib_proximity_pct.
    """
    diff = high - low
    if diff <= 0 or high == 0:
        return {
            "fib_levels": {},
            "nearest_fib": 0.0,
            "nearest_fib_level": 0.0,
            "fib_proximity_pct": 100.0,
        }

    # Retracement levels: price at each fib ratio measured down from the high
    fib_prices = {}
    for level in FIB_LEVELS:
        fib_prices[level] = high - (diff * level)

    # Find the nearest fib level to current price
    nearest_level = 0.0
    nearest_price = 0.0
    min_distance = float("inf")

    for level, price in fib_prices.items():
        distance = abs(current_price - price)
        if distance < min_distance:
            min_distance = distance
            nearest_level = level
            nearest_price = price

    # Proximity as percentage distance from nearest fib
    if nearest_price > 0:
        proximity = abs(current_price - nearest_price) / nearest_price * 100.0
    else:
        proximity = 100.0

    return {
        "fib_levels": fib_prices,
        "nearest_fib": nearest_price,
        "nearest_fib_level": nearest_level,
        "fib_proximity_pct": round(proximity, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# VWAP
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_vwap(candles: list) -> float:
    """Calculate Volume-Weighted Average Price from candle data.

    Args:
        candles: List of candle dicts with keys h, l, c, v.

    Returns:
        VWAP price, or 0.0 if no volume data.
    """
    cumulative_tp_vol = 0.0
    cumulative_vol = 0.0

    for c in candles:
        h = float(c.get("h", 0))
        l = float(c.get("l", 0))
        close = float(c.get("c", 0))
        vol = float(c.get("v", 0))

        typical_price = (h + l + close) / 3.0
        cumulative_tp_vol += typical_price * vol
        cumulative_vol += vol

    if cumulative_vol == 0:
        return 0.0

    return cumulative_tp_vol / cumulative_vol


# ═══════════════════════════════════════════════════════════════════════════════
# Volume profile analysis
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_volume_profile(candles: list) -> tuple:
    """Analyze volume profile by comparing dump phase vs recovery phase.

    Splits candles into first half (dump) and second half (recovery),
    compares average volumes.

    Args:
        candles: List of candle dicts with key v.

    Returns:
        Tuple of (trend_string, recovery_ratio).
    """
    if len(candles) < 4:
        return ("UNKNOWN", 1.0)

    mid = len(candles) // 2
    first_half = candles[:mid]
    second_half = candles[mid:]

    first_vol = sum(float(c.get("v", 0)) for c in first_half)
    second_vol = sum(float(c.get("v", 0)) for c in second_half)

    avg_first = first_vol / len(first_half) if first_half else 0
    avg_second = second_vol / len(second_half) if second_half else 0

    if avg_first == 0:
        ratio = 1.0
    else:
        ratio = avg_second / avg_first

    if ratio >= 1.5:
        trend = "STRONG_RECOVERY"
    elif ratio >= 0.8:
        trend = "HEALTHY"
    elif ratio >= 0.4:
        trend = "WEAK"
    else:
        trend = "DEAD_CAT"

    return (trend, round(ratio, 3))


# ═══════════════════════════════════════════════════════════════════════════════
# Support / Resistance detection
# ═══════════════════════════════════════════════════════════════════════════════

def find_support_resistance(candles: list, window: int = 5) -> tuple:
    """Find local minima (support) and maxima (resistance) in close prices.

    Args:
        candles: List of candle dicts with key c.
        window: Number of candles on each side to compare.

    Returns:
        Tuple of (sorted support_levels, sorted resistance_levels).
    """
    closes = [float(c.get("c", 0)) for c in candles]
    supports = []
    resistances = []

    if len(closes) < (2 * window + 1):
        return (supports, resistances)

    for i in range(window, len(closes) - window):
        local_slice = closes[i - window: i + window + 1]
        current = closes[i]

        # Local minimum → support
        if current == min(local_slice):
            supports.append(round(current, 10))

        # Local maximum → resistance
        if current == max(local_slice):
            resistances.append(round(current, 10))

    # De-duplicate and sort
    supports = sorted(set(supports))
    resistances = sorted(set(resistances))

    return (supports, resistances)


# ═══════════════════════════════════════════════════════════════════════════════
# Momentum shift
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_momentum_shift(candles: list) -> tuple:
    """Compare descent rate (first half) vs recovery rate (second half).

    Args:
        candles: List of candle dicts with key c.

    Returns:
        Tuple of (shift_ratio, signal_string).
    """
    if len(candles) < 4:
        return (0.0, "NO_REVERSAL")

    closes = [float(c.get("c", 0)) for c in candles]
    mid = len(closes) // 2

    first_half = closes[:mid]
    second_half = closes[mid:]

    # Descent rate: price drop per candle in first half
    if len(first_half) >= 2:
        descent = (first_half[0] - first_half[-1]) / len(first_half)
    else:
        descent = 0.0

    # Recovery rate: price rise per candle in second half
    if len(second_half) >= 2:
        recovery = (second_half[-1] - second_half[0]) / len(second_half)
    else:
        recovery = 0.0

    # Avoid division by zero
    if abs(descent) < 1e-15:
        shift = recovery * 1e6 if recovery > 0 else 0.0
    else:
        shift = recovery / abs(descent)

    if recovery > abs(descent) and descent > 0:
        signal = "STRONG_REVERSAL"
    elif recovery > 0.5 * abs(descent) and descent > 0:
        signal = "WEAK_REVERSAL"
    else:
        signal = "NO_REVERSAL"

    return (round(shift, 3), signal)


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run_ta(mint_address: str, current_price: float) -> TAResult:
    """Run full technical analysis for a token.

    Fetches 1-minute and 5-minute OHLCV candles from Birdeye, then
    computes RSI, Fibonacci retracements, VWAP, volume profile,
    support/resistance, and momentum shift.

    Args:
        mint_address: Solana token mint address.
        current_price: Current token price in USD.

    Returns:
        TAResult dataclass with all computed values.  If Birdeye data
        is unavailable, returns TAResult with available=False and
        neutral/default values.
    """
    result = TAResult()

    # ------------------------------------------------------------------
    # Fetch candle data
    # ------------------------------------------------------------------
    candles_1m = _fetch_ohlcv(mint_address, "1m", OHLCV_1M_CANDLES)
    candles_5m = _fetch_ohlcv(mint_address, "5m", OHLCV_5M_CANDLES)

    if not candles_1m and not candles_5m:
        return result  # available=False, all defaults

    result.available = True

    # Use whichever dataset has data; prefer 1m for granularity
    primary_candles = candles_1m if candles_1m else candles_5m

    # ------------------------------------------------------------------
    # RSI
    # ------------------------------------------------------------------
    if candles_1m:
        closes_1m = [float(c.get("c", 0)) for c in candles_1m]
        result.rsi_1m = calculate_rsi(closes_1m)

    if candles_5m:
        closes_5m = [float(c.get("c", 0)) for c in candles_5m]
        result.rsi_5m = calculate_rsi(closes_5m)

    # RSI signal determination
    rsi_primary = result.rsi_1m if candles_1m else result.rsi_5m
    if rsi_primary < RSI_OVERSOLD:
        # Check if RSI is rising (bouncing) by comparing last few values
        rising = False
        ref_closes = closes_1m if candles_1m else (closes_5m if candles_5m else [])
        if len(ref_closes) >= RSI_PERIOD + 5:
            rsi_prev = calculate_rsi(ref_closes[:-3])
            rising = rsi_primary > rsi_prev
        result.rsi_signal = "OVERSOLD_BOUNCING" if rising else "OVERSOLD"
    elif rsi_primary > RSI_OVERBOUGHT:
        result.rsi_signal = "OVERBOUGHT"
    else:
        result.rsi_signal = "NEUTRAL"

    # ------------------------------------------------------------------
    # Fibonacci retracement
    # ------------------------------------------------------------------
    highs = [float(c.get("h", 0)) for c in primary_candles]
    lows = [float(c.get("l", 0)) for c in primary_candles]

    swing_high = max(highs) if highs else 0.0
    swing_low = min(lows) if lows else 0.0

    result.swing_high = swing_high
    result.swing_low = swing_low
    result.ath = swing_high

    if swing_high > 0:
        result.retracement_from_ath_pct = round(
            (swing_high - current_price) / swing_high * 100.0, 2
        )

    fib_result = calculate_fibonacci(swing_high, swing_low, current_price)
    result.fib_levels = fib_result["fib_levels"]
    result.nearest_fib = fib_result["nearest_fib"]
    result.nearest_fib_level = fib_result["nearest_fib_level"]
    result.fib_proximity_pct = fib_result["fib_proximity_pct"]

    # ------------------------------------------------------------------
    # VWAP
    # ------------------------------------------------------------------
    result.vwap = calculate_vwap(primary_candles)

    if result.vwap > 0:
        result.price_vs_vwap_pct = round(
            (current_price - result.vwap) / result.vwap * 100.0, 2
        )

    # Detect VWAP reclaim: price was below VWAP but crossed above
    # in the last few candles
    if result.vwap > 0 and len(primary_candles) >= 5:
        recent = primary_candles[-5:]
        below_then_above = False
        for i, c in enumerate(recent):
            c_close = float(c.get("c", 0))
            if c_close < result.vwap and i < len(recent) - 1:
                # Check if any subsequent candle closed above VWAP
                for later in recent[i + 1:]:
                    if float(later.get("c", 0)) > result.vwap:
                        below_then_above = True
                        break
            if below_then_above:
                break
        result.vwap_reclaim = below_then_above

    # ------------------------------------------------------------------
    # Volume profile
    # ------------------------------------------------------------------
    result.volume_trend, result.volume_recovery_ratio = analyze_volume_profile(
        primary_candles
    )

    # ------------------------------------------------------------------
    # Support / Resistance
    # ------------------------------------------------------------------
    result.support_levels, result.resistance_levels = find_support_resistance(
        primary_candles
    )

    # ------------------------------------------------------------------
    # Momentum shift
    # ------------------------------------------------------------------
    result.momentum_shift, result.momentum_signal = calculate_momentum_shift(
        primary_candles
    )

    return result
