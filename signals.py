"""
Signal engine — detects dump events and recovery entry opportunities.

Strategy: "Swing Recovery After Dump"
1. Identify tokens that dumped ≥30% from a recent high within the last 6h
2. Confirm the dump had elevated volume (panic selling)
3. Wait for early recovery signs: price bounce + buy pressure returning
4. Enter when RSI is oversold and buy volume dominates
5. Target 2x–3x with a -20% stop-loss
"""

from dataclasses import dataclass
from config import (
    DUMP_LOOKBACK_HOURS,
    DUMP_THRESHOLD_PCT,
    VOLUME_SPIKE_MULTIPLIER,
    RECOVERY_BOUNCE_PCT,
    RSI_OVERSOLD_THRESHOLD,
    MIN_BUY_VOLUME_RATIO,
    MIN_TOKEN_AGE_HOURS,
    MIN_MARKET_CAP_USD,
    MIN_24H_VOLUME_USD,
)


@dataclass
class DumpEvent:
    """A detected dump in a token's price history."""
    peak_price: float
    bottom_price: float
    current_price: float
    dump_pct: float            # negative, e.g. -45.0
    bounce_pct: float          # positive if recovering
    avg_volume_before: float
    volume_during_dump: float
    volume_spike: float        # multiplier vs normal


@dataclass
class Signal:
    """A buy/sell signal."""
    mint_address: str
    token_name: str
    signal_type: str           # "RECOVERY_ENTRY", "TAKE_PROFIT_2X", "TAKE_PROFIT_3X", "STOP_LOSS"
    price: float
    rsi: float | None
    buy_volume_ratio: float
    dump_event: DumpEvent | None
    market_cap: float
    confidence: float          # 0.0 – 1.0
    reason: str


def compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """Compute RSI from a list of closing prices (oldest → newest)."""
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))

    # Use the last `period` changes
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]

    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def detect_dump(candles: list[dict]) -> DumpEvent | None:
    """
    Analyze OHLCV candles to detect a significant dump.
    Candles should span the lookback window (e.g. 6h of 15m candles).
    Expected candle format: {open, high, low, close, volume, unixTime}
    """
    if len(candles) < 4:
        return None

    # Find the peak price in the lookback window
    highs = [c.get("high", c.get("close", 0)) for c in candles]
    peak_price = max(highs)
    peak_idx = highs.index(peak_price)

    if peak_price == 0:
        return None

    # Find the lowest price AFTER the peak (the dump bottom)
    post_peak = candles[peak_idx:]
    if len(post_peak) < 2:
        return None

    lows = [c.get("low", c.get("close", 0)) for c in post_peak]
    bottom_price = min(lows)

    if bottom_price == 0:
        return None

    dump_pct = ((bottom_price - peak_price) / peak_price) * 100
    current_price = candles[-1].get("close", 0)

    # Bounce from bottom
    bounce_pct = 0.0
    if bottom_price > 0 and current_price > bottom_price:
        bounce_pct = ((current_price - bottom_price) / bottom_price) * 100

    # Volume analysis: compare dump period volume to pre-dump average
    volumes = [c.get("volume", 0) for c in candles]
    pre_peak_volumes = volumes[:max(peak_idx, 1)]
    avg_vol_before = sum(pre_peak_volumes) / len(pre_peak_volumes) if pre_peak_volumes else 1
    dump_volumes = volumes[peak_idx:]
    vol_during_dump = sum(dump_volumes) / len(dump_volumes) if dump_volumes else 0
    volume_spike = vol_during_dump / avg_vol_before if avg_vol_before > 0 else 1.0

    return DumpEvent(
        peak_price=peak_price,
        bottom_price=bottom_price,
        current_price=current_price,
        dump_pct=dump_pct,
        bounce_pct=bounce_pct,
        avg_volume_before=avg_vol_before,
        volume_during_dump=vol_during_dump,
        volume_spike=volume_spike,
    )


def check_recovery_entry(
    mint_address: str,
    token_name: str,
    candles: list[dict],
    buy_volume_ratio: float,
    market_cap: float,
    token_age_hours: float,
    volume_24h: float,
) -> Signal | None:
    """
    Check if a token qualifies for a recovery swing entry.
    Returns a Signal if all conditions are met, None otherwise.
    """
    # ── Filter checks ────────────────────────────────────────────────────
    if token_age_hours < MIN_TOKEN_AGE_HOURS:
        return None
    if market_cap < MIN_MARKET_CAP_USD:
        return None
    if volume_24h < MIN_24H_VOLUME_USD:
        return None

    # ── Dump detection ───────────────────────────────────────────────────
    dump = detect_dump(candles)
    if dump is None:
        return None

    # Must be a significant dump
    if dump.dump_pct > DUMP_THRESHOLD_PCT:  # dump_pct is negative
        return None

    # Dump should have had elevated volume (panic selling)
    if dump.volume_spike < VOLUME_SPIKE_MULTIPLIER:
        return None

    # ── Recovery signals ─────────────────────────────────────────────────
    # Price must be bouncing off the bottom
    if dump.bounce_pct < RECOVERY_BOUNCE_PCT:
        return None

    # Buy pressure should be returning
    if buy_volume_ratio < MIN_BUY_VOLUME_RATIO:
        return None

    # RSI should be oversold (or near it)
    closes = [c.get("close", 0) for c in candles]
    rsi = compute_rsi(closes)
    if rsi is not None and rsi > RSI_OVERSOLD_THRESHOLD:
        return None

    # ── Confidence scoring ───────────────────────────────────────────────
    confidence = _compute_confidence(dump, rsi, buy_volume_ratio, market_cap)

    current_price = candles[-1].get("close", 0)

    reason_parts = [
        f"Dumped {dump.dump_pct:.1f}% from ${dump.peak_price:.6f}",
        f"Bounced {dump.bounce_pct:.1f}% off bottom ${dump.bottom_price:.6f}",
        f"Volume spike {dump.volume_spike:.1f}x during dump",
        f"RSI={rsi:.1f}" if rsi else "RSI=N/A",
        f"Buy ratio={buy_volume_ratio:.0%}",
        f"MCap=${market_cap:,.0f}",
    ]

    return Signal(
        mint_address=mint_address,
        token_name=token_name,
        signal_type="RECOVERY_ENTRY",
        price=current_price,
        rsi=rsi,
        buy_volume_ratio=buy_volume_ratio,
        dump_event=dump,
        market_cap=market_cap,
        confidence=confidence,
        reason=" | ".join(reason_parts),
    )


def _compute_confidence(
    dump: DumpEvent, rsi: float | None, buy_ratio: float, market_cap: float
) -> float:
    """
    Score confidence 0.0–1.0 based on how well the setup looks.
    Higher = stronger signal.
    """
    score = 0.0

    # Deeper dump = more room for recovery (up to a point)
    if dump.dump_pct <= -50:
        score += 0.25
    elif dump.dump_pct <= -40:
        score += 0.20
    elif dump.dump_pct <= -30:
        score += 0.15

    # Bigger bounce already happening = momentum
    if dump.bounce_pct >= 15:
        score += 0.20
    elif dump.bounce_pct >= 10:
        score += 0.15
    elif dump.bounce_pct >= 5:
        score += 0.10

    # Volume spike during dump = real capitulation
    if dump.volume_spike >= 4.0:
        score += 0.20
    elif dump.volume_spike >= 3.0:
        score += 0.15
    elif dump.volume_spike >= 2.0:
        score += 0.10

    # RSI deep oversold = strong
    if rsi is not None:
        if rsi < 20:
            score += 0.20
        elif rsi < 25:
            score += 0.15
        elif rsi < 30:
            score += 0.10
        elif rsi < 35:
            score += 0.05

    # Strong buy pressure
    if buy_ratio >= 0.70:
        score += 0.15
    elif buy_ratio >= 0.60:
        score += 0.10
    elif buy_ratio >= 0.55:
        score += 0.05

    return min(score, 1.0)


def check_exit_signals(
    entry_price: float, current_price: float, take_profit_2x: float, take_profit_3x: float, stop_loss_pct: float
) -> str | None:
    """
    Check if we should exit a position.
    Returns signal type or None.
    """
    if current_price <= 0 or entry_price <= 0:
        return None

    pnl_pct = ((current_price - entry_price) / entry_price) * 100

    if current_price >= entry_price * take_profit_3x:
        return "TAKE_PROFIT_3X"
    if current_price >= entry_price * take_profit_2x:
        return "TAKE_PROFIT_2X"
    if pnl_pct <= stop_loss_pct:
        return "STOP_LOSS"
    return None
