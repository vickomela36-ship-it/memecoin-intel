"""
technical_analysis.py — Fibonacci, RSI, VWAP, volume profile, support/resistance,
and momentum shift detection using Birdeye OHLCV candle data.

Falls back gracefully when Birdeye is unavailable — returns neutral scores.
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


@dataclass
class TAResult:
    available: bool = False

    # Fibonacci
    swing_high: float = 0.0
    swing_low: float = 0.0
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

    # Volume profile
    volume_recovery_ratio: float = 0.0
    volume_trend: str = "UNKNOWN"

    # Support / Resistance
    support_levels: list = field(default_factory=list)
    resistance_levels: list = field(default_factory=list)

    # Momentum
    momentum_shift: float = 0.0
    momentum_signal: str = "UNKNOWN"

    # ATH tracking
    ath: float = 0.0
    retracement_from_ath_pct: float = 0.0


def _fetch_ohlcv(address: str, interval: str = "5m", limit: int = 288) -> list:
    """Fetch OHLCV candles from Birdeye."""
    now = int(time.time())
    if interval == "1m":
        time_from = now - limit * 60
    elif interval == "5m":
        time_from = now - limit * 300
    elif interval == "1H":
        time_from = now - limit * 3600
    else:
        time_from = now - limit * 300

    try:
        r = requests.get(
            f"{BIRDEYE_API}/defi/ohlcv",
            params={
                "address": address,
                "type": interval,
                "time_from": time_from,
                "time_to": now,
            },
            headers={
                "X-API-KEY": BIRDEYE_API_KEY,
                "x-chain": "solana",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        items = (data.get("data") or {}).get("items") or []
        return items
    except Exception:
        return []


def calculate_rsi(closes: list, period: int = RSI_PERIOD) -> float:
    """Wilder's smoothed RSI."""
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_fibonacci(high: float, low: float) -> dict:
    """Fibonacci retracement levels from swing high to swing low."""
    if high <= low or high == 0:
        return {}
    diff = high - low
    levels = {0.0: high, 1.0: low}
    for lvl in FIB_LEVELS:
        levels[lvl] = high - diff * lvl
    return levels


def calculate_vwap(candles: list) -> float:
    """Volume-weighted average price from candle data."""
    cum_vol = 0.0
    cum_tp_vol = 0.0
    for c in candles:
        h = float(c.get("h", 0) or 0)
        l = float(c.get("l", 0) or 0)
        cl = float(c.get("c", 0) or 0)
        v = float(c.get("v", 0) or 0)
        typical = (h + l + cl) / 3
        cum_tp_vol += typical * v
        cum_vol += v
    return cum_tp_vol / cum_vol if cum_vol > 0 else 0


def analyze_volume_profile(candles: list) -> dict:
    """Compare volume during dump vs recovery to detect dead cat bounces."""
    if len(candles) < 10:
        return {"trend": "UNKNOWN", "ratio": 0.0}

    closes = [float(c.get("c", 0) or 0) for c in candles]
    volumes = [float(c.get("v", 0) or 0) for c in candles]

    if not closes or min(closes) == 0:
        return {"trend": "UNKNOWN", "ratio": 0.0}

    min_idx = closes.index(min(closes))

    dump_vols = volumes[max(0, min_idx - 8) : min_idx + 1]
    recovery_vols = volumes[min_idx + 1 :]

    avg_dump = sum(dump_vols) / len(dump_vols) if dump_vols else 1.0
    avg_recovery = sum(recovery_vols) / len(recovery_vols) if recovery_vols else 0.0

    ratio = avg_recovery / avg_dump if avg_dump > 0 else 0.0

    if ratio > 1.5:
        trend = "STRONG_RECOVERY"
    elif ratio > 0.8:
        trend = "HEALTHY"
    elif ratio > 0.3:
        trend = "WEAK"
    else:
        trend = "DEAD_CAT"

    return {"trend": trend, "ratio": ratio}


def find_support_resistance(candles: list, num_levels: int = 3) -> tuple:
    """Detect support and resistance from swing highs/lows."""
    if len(candles) < 5:
        return [], []

    lows = [float(c.get("l", 0) or 0) for c in candles]
    highs = [float(c.get("h", 0) or 0) for c in candles]

    supports = []
    resistances = []

    for i in range(2, len(candles) - 2):
        if lows[i] <= min(lows[i - 1], lows[i - 2], lows[i + 1], lows[i + 2]):
            supports.append(lows[i])
        if highs[i] >= max(
            highs[i - 1], highs[i - 2], highs[i + 1], highs[i + 2]
        ):
            resistances.append(highs[i])

    supports = _cluster_levels(supports, num_levels)
    resistances = _cluster_levels(resistances, num_levels)
    return supports, resistances


def _cluster_levels(levels: list, n: int) -> list:
    """Cluster nearby price levels and return the n most significant."""
    if not levels:
        return []
    levels = sorted(levels)
    clusters = []
    current = [levels[0]]

    for i in range(1, len(levels)):
        if current and levels[i] / current[-1] < 1.02:
            current.append(levels[i])
        else:
            clusters.append(sum(current) / len(current))
            current = [levels[i]]
    if current:
        clusters.append(sum(current) / len(current))

    clusters.sort()
    if len(clusters) <= n:
        return clusters
    step = len(clusters) // n
    return [clusters[i * step] for i in range(n)]


def calculate_momentum_shift(candles: list) -> tuple:
    """Compare rate of descent vs rate of recovery. Higher = stronger reversal."""
    if len(candles) < 12:
        return 0.0, "UNKNOWN"

    closes = [float(c.get("c", 0) or 0) for c in candles]
    if not closes or min(closes) == 0:
        return 0.0, "UNKNOWN"

    min_idx = closes.index(min(closes))
    if min_idx < 3 or min_idx >= len(closes) - 3:
        return 0.0, "UNKNOWN"

    descent_start = max(0, min_idx - 10)
    descent_changes = [
        closes[i] - closes[i - 1] for i in range(descent_start + 1, min_idx + 1)
    ]
    avg_descent = (
        sum(descent_changes) / len(descent_changes) if descent_changes else 0
    )

    recovery_end = min(len(closes), min_idx + 10)
    recovery_changes = [
        closes[i] - closes[i - 1] for i in range(min_idx + 1, recovery_end)
    ]
    avg_recovery = (
        sum(recovery_changes) / len(recovery_changes) if recovery_changes else 0
    )

    if avg_descent >= 0:
        return 0.0, "NO_REVERSAL"

    shift = abs(avg_recovery / avg_descent) if avg_descent != 0 else 0.0

    if shift > 1.5:
        signal = "STRONG_REVERSAL"
    elif shift > 0.8:
        signal = "WEAK_REVERSAL"
    else:
        signal = "NO_REVERSAL"

    return round(shift, 3), signal


def _detect_vwap_reclaim(candles: list, vwap: float) -> bool:
    """Check if price recently crossed from below to above VWAP."""
    if len(candles) < 5 or vwap <= 0:
        return False
    recent = candles[-10:]
    below_then_above = False
    was_below = False
    for c in recent:
        cl = float(c.get("c", 0) or 0)
        if cl < vwap:
            was_below = True
        elif was_below and cl >= vwap:
            below_then_above = True
    return below_then_above


def run_ta(mint_address: str, current_price: float = 0) -> TAResult:
    """Run full technical analysis. Returns TAResult with all indicators."""
    result = TAResult()

    candles_5m = _fetch_ohlcv(mint_address, "5m", OHLCV_5M_CANDLES)
    candles_1m = _fetch_ohlcv(mint_address, "1m", OHLCV_1M_CANDLES)

    if not candles_5m and not candles_1m:
        return result

    result.available = True
    primary = candles_5m if candles_5m else candles_1m

    closes_5m = [float(c.get("c", 0) or 0) for c in candles_5m] if candles_5m else []
    closes_1m = [float(c.get("c", 0) or 0) for c in candles_1m] if candles_1m else []

    # ── ATH + Fibonacci ──────────────────────────────────────────────────
    if primary:
        all_highs = [float(c.get("h", 0) or 0) for c in primary]
        all_lows = [float(c.get("l", 0) or 0) for c in primary if float(c.get("l", 0) or 0) > 0]

        if all_highs and all_lows:
            result.swing_high = max(all_highs)
            result.swing_low = min(all_lows)
            result.ath = result.swing_high

            if current_price > 0 and result.ath > 0:
                result.retracement_from_ath_pct = (
                    (result.ath - current_price) / result.ath * 100
                )

            result.fib_levels = calculate_fibonacci(
                result.swing_high, result.swing_low
            )

            if current_price > 0 and result.fib_levels:
                best_dist = float("inf")
                for lvl, price in result.fib_levels.items():
                    if price <= 0:
                        continue
                    dist = abs(current_price - price) / price * 100
                    if dist < best_dist:
                        best_dist = dist
                        result.nearest_fib = price
                        result.nearest_fib_level = lvl
                result.fib_proximity_pct = best_dist

    # ── RSI ──────────────────────────────────────────────────────────────
    if closes_5m:
        result.rsi_5m = calculate_rsi(closes_5m)
    if closes_1m:
        result.rsi_1m = calculate_rsi(closes_1m)

    avg_rsi = (result.rsi_1m + result.rsi_5m) / 2
    if avg_rsi < RSI_OVERSOLD and (
        (closes_1m and closes_1m[-1] > closes_1m[-3])
        if len(closes_1m) >= 3
        else False
    ):
        result.rsi_signal = "OVERSOLD_BOUNCING"
    elif avg_rsi < RSI_OVERSOLD:
        result.rsi_signal = "OVERSOLD"
    elif avg_rsi > RSI_OVERBOUGHT:
        result.rsi_signal = "OVERBOUGHT"
    else:
        result.rsi_signal = "NEUTRAL"

    # ── VWAP ─────────────────────────────────────────────────────────────
    if primary:
        result.vwap = calculate_vwap(primary)
        if result.vwap > 0 and current_price > 0:
            result.price_vs_vwap_pct = (
                (current_price - result.vwap) / result.vwap * 100
            )
            result.vwap_reclaim = _detect_vwap_reclaim(primary, result.vwap)

    # ── Volume profile ───────────────────────────────────────────────────
    if primary:
        vp = analyze_volume_profile(primary)
        result.volume_recovery_ratio = vp["ratio"]
        result.volume_trend = vp["trend"]

    # ── Support / Resistance ─────────────────────────────────────────────
    if primary:
        supports, resistances = find_support_resistance(primary)
        result.support_levels = supports
        result.resistance_levels = resistances

    # ── Momentum shift ───────────────────────────────────────────────────
    if primary:
        shift, signal = calculate_momentum_shift(primary)
        result.momentum_shift = shift
        result.momentum_signal = signal

    return result
