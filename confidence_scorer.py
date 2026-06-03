"""
confidence_scorer.py — Composite 0-100 confidence scoring with letter grades.

Safety is a pass/fail gate: if it fails, the token is blocked entirely.
Everything else contributes a weighted sub-score to a composite total.
"""

from dataclasses import dataclass
from config import (
    WEIGHT_FIB, WEIGHT_RSI, WEIGHT_VOLUME, WEIGHT_SENTIMENT,
    WEIGHT_HOLDERS, WEIGHT_VWAP, WEIGHT_PATTERN,
    GRADE_A_MIN, GRADE_B_MIN, GRADE_C_MIN,
    FIB_PROXIMITY_PCT, STOP_LOSS_PCT,
)


@dataclass
class ConfidenceScore:
    total: float = 0.0
    grade: str = "D"
    safety_passed: bool = False

    fib_score: float = 0.0
    rsi_score: float = 0.0
    volume_score: float = 0.0
    sentiment_score: float = 0.0
    holder_score: float = 0.0
    vwap_score: float = 0.0
    pattern_score: float = 0.0

    summary: str = ""
    strengths: list = None
    weaknesses: list = None

    def __post_init__(self):
        if self.strengths is None:
            self.strengths = []
        if self.weaknesses is None:
            self.weaknesses = []


def _score_fib(current_price, fib_levels, nearest_fib_level, proximity_pct):
    """0-100. Best when sitting near 0.618 or 0.786 retracement."""
    if not fib_levels or current_price <= 0:
        return 50.0, None

    level_weight = {
        0.618: 1.0,
        0.786: 0.95,
        0.5: 0.75,
        0.382: 0.55,
        0.236: 0.35,
        0.0: 0.1,
        1.0: 0.1,
    }
    w = level_weight.get(nearest_fib_level, 0.3)

    if proximity_pct < 1.0:
        base = 100
    elif proximity_pct < FIB_PROXIMITY_PCT:
        base = 85
    elif proximity_pct < 5.0:
        base = 65
    elif proximity_pct < 10.0:
        base = 35
    else:
        base = 10

    score = min(base * w, 100)
    note = None
    if proximity_pct < FIB_PROXIMITY_PCT and nearest_fib_level in (0.618, 0.786):
        note = f"Near {nearest_fib_level} fib ({proximity_pct:.1f}% away)"
    return score, note


def _score_rsi(rsi_1m, rsi_5m):
    """0-100. Sweet spot is oversold bouncing back (25-40 range)."""
    score = 0.0
    for rsi in [rsi_1m, rsi_5m]:
        if 25 <= rsi <= 35:
            score += 48
        elif 20 <= rsi < 25:
            score += 38
        elif 35 < rsi <= 45:
            score += 32
        elif rsi < 20:
            score += 22
        elif 45 < rsi <= 55:
            score += 15
        else:
            score += 5

    score = min(score, 100)
    note = None
    avg = (rsi_1m + rsi_5m) / 2
    if avg < 35:
        note = f"RSI oversold (1m={rsi_1m:.0f}, 5m={rsi_5m:.0f})"
    return score, note


def _score_volume(volume_trend, volume_ratio):
    """0-100. Strong recovery volume is bullish."""
    if volume_trend == "STRONG_RECOVERY":
        score = min(volume_ratio * 40, 100)
    elif volume_trend == "HEALTHY":
        score = min(volume_ratio * 50, 80)
    elif volume_trend == "WEAK":
        score = min(volume_ratio * 60, 40)
    elif volume_trend == "DEAD_CAT":
        score = 10
    else:
        score = 45

    note = None
    if volume_trend in ("STRONG_RECOVERY", "HEALTHY"):
        note = f"Volume {volume_trend.lower().replace('_', ' ')} ({volume_ratio:.1f}x)"
    return score, note


def _score_sentiment(txns, boosts, pair_data):
    """0-100 from buy/sell ratios, boosts, and social presence."""
    score = 0.0
    txns = txns or {}

    for tf_key in ("m5", "h1"):
        tf = txns.get(tf_key, {})
        buys = int(tf.get("buys", 0) or 0)
        sells = int(tf.get("sells", 0) or 0)
        total = buys + sells
        if total > 0:
            ratio = buys / total
            if ratio > 0.65:
                score += 20
            elif ratio > 0.55:
                score += 12
            elif ratio > 0.45:
                score += 5

    if boosts and boosts > 0:
        score += min(int(boosts) * 2, 20)

    info = (pair_data or {}).get("info") or {}
    if info.get("websites"):
        score += 8
    for s in info.get("socials") or []:
        stype = (s.get("type") or "").lower()
        if "twitter" in stype:
            score += 8
        if "telegram" in stype:
            score += 5

    score = min(score, 100)
    note = None
    if score >= 60:
        note = f"Strong sentiment (score {score:.0f})"
    return score, note


def _score_holders(top10_pct, holder_count):
    """0-100 based on distribution health."""
    score = 0.0

    if top10_pct < 20:
        score += 60
    elif top10_pct < 30:
        score += 45
    elif top10_pct < 40:
        score += 30
    elif top10_pct < 50:
        score += 15
    else:
        score += 5

    if holder_count >= 1000:
        score += 40
    elif holder_count >= 500:
        score += 30
    elif holder_count >= 200:
        score += 25
    elif holder_count >= 100:
        score += 18
    elif holder_count >= 50:
        score += 10

    score = min(score, 100)
    note = None
    if top10_pct < 30 and holder_count >= 200:
        note = f"Healthy distribution ({holder_count} holders, top 10 = {top10_pct:.0f}%)"
    return score, note


def _score_vwap(price_vs_vwap_pct, vwap_reclaim, vwap):
    """0-100 for VWAP position."""
    if vwap <= 0:
        return 50.0, None

    if vwap_reclaim:
        score = 90.0
        note = "Price reclaiming VWAP"
    elif price_vs_vwap_pct > 0:
        score = 70.0
        note = f"Above VWAP (+{price_vs_vwap_pct:.1f}%)"
    elif price_vs_vwap_pct > -5:
        score = 50.0
        note = None
    elif price_vs_vwap_pct > -10:
        score = 30.0
        note = None
    else:
        score = 10.0
        note = None
    return score, note


def _score_pattern(momentum_shift, momentum_signal):
    """0-100 for momentum reversal pattern."""
    if momentum_signal == "STRONG_REVERSAL":
        score = 85.0
    elif momentum_signal == "WEAK_REVERSAL":
        score = 50.0
    elif momentum_signal == "NO_REVERSAL":
        score = 15.0
    else:
        score = 40.0

    note = None
    if momentum_signal == "STRONG_REVERSAL":
        note = f"Strong reversal ({momentum_shift:.2f}x recovery vs descent)"
    return score, note


def compute_confidence(safety_result, ta_result, pair_data, txns=None,
                       boosts=0, current_price=0.0) -> ConfidenceScore:
    """
    Compute the composite confidence score.
    Safety is a gate — if it fails, score is 0 and grade is D.
    """
    cs = ConfidenceScore()
    cs.safety_passed = safety_result.passed

    if not safety_result.passed:
        cs.total = 0
        cs.grade = "F"
        fails = safety_result.fail_reasons
        cs.summary = f"BLOCKED: {'; '.join(fails[:3])}"
        cs.weaknesses = fails
        return cs

    strengths = []
    weaknesses = []

    # ── Sub-scores ───────────────────────────────────────────────────────
    fib_s, fib_n = _score_fib(
        current_price,
        ta_result.fib_levels,
        ta_result.nearest_fib_level,
        ta_result.fib_proximity_pct,
    )
    cs.fib_score = fib_s
    if fib_n:
        strengths.append(fib_n)
    elif fib_s < 30:
        weaknesses.append("Not near a key fib level")

    rsi_s, rsi_n = _score_rsi(ta_result.rsi_1m, ta_result.rsi_5m)
    cs.rsi_score = rsi_s
    if rsi_n:
        strengths.append(rsi_n)
    elif rsi_s < 30:
        weaknesses.append("RSI not in reversal zone")

    vol_s, vol_n = _score_volume(
        ta_result.volume_trend, ta_result.volume_recovery_ratio
    )
    cs.volume_score = vol_s
    if vol_n:
        strengths.append(vol_n)
    elif vol_s < 30:
        weaknesses.append(f"Volume trend: {ta_result.volume_trend}")

    sent_s, sent_n = _score_sentiment(txns, boosts, pair_data)
    cs.sentiment_score = sent_s
    if sent_n:
        strengths.append(sent_n)

    hold_s, hold_n = _score_holders(
        safety_result.top10_holder_pct, safety_result.holder_count
    )
    cs.holder_score = hold_s
    if hold_n:
        strengths.append(hold_n)
    elif hold_s < 30:
        weaknesses.append(
            f"Concentrated holders (top 10 = {safety_result.top10_holder_pct:.0f}%)"
        )

    vwap_s, vwap_n = _score_vwap(
        ta_result.price_vs_vwap_pct, ta_result.vwap_reclaim, ta_result.vwap
    )
    cs.vwap_score = vwap_s
    if vwap_n:
        strengths.append(vwap_n)

    pat_s, pat_n = _score_pattern(
        ta_result.momentum_shift, ta_result.momentum_signal
    )
    cs.pattern_score = pat_s
    if pat_n:
        strengths.append(pat_n)
    elif pat_s < 30:
        weaknesses.append("No momentum reversal detected")

    # ── Composite ────────────────────────────────────────────────────────
    cs.total = round(
        fib_s * WEIGHT_FIB
        + rsi_s * WEIGHT_RSI
        + vol_s * WEIGHT_VOLUME
        + sent_s * WEIGHT_SENTIMENT
        + hold_s * WEIGHT_HOLDERS
        + vwap_s * WEIGHT_VWAP
        + pat_s * WEIGHT_PATTERN,
        1,
    )

    if cs.total >= GRADE_A_MIN:
        cs.grade = "A"
    elif cs.total >= GRADE_B_MIN:
        cs.grade = "B"
    elif cs.total >= GRADE_C_MIN:
        cs.grade = "C"
    else:
        cs.grade = "D"

    cs.strengths = strengths
    cs.weaknesses = weaknesses

    top_strength = strengths[0] if strengths else "Moderate setup"
    cs.summary = f"Grade {cs.grade} ({cs.total:.0f}/100) — {top_strength}"

    return cs


def compute_entry_exit(current_price, ta_result, confidence_score):
    """Compute entry price, stop-loss, and take-profit levels."""
    if current_price <= 0:
        return {}

    stop_loss = current_price * (1 - STOP_LOSS_PCT / 100)
    target_2x = current_price * 2
    target_3x = current_price * 3

    nearest_support = None
    if ta_result.support_levels:
        below = [s for s in ta_result.support_levels if s < current_price]
        if below:
            nearest_support = max(below)

    entry_low = nearest_support if nearest_support else current_price * 0.95
    entry_high = current_price * 1.02

    if ta_result.nearest_fib and ta_result.fib_proximity_pct < 5:
        fib_entry = ta_result.nearest_fib
        if fib_entry < current_price:
            entry_low = min(entry_low, fib_entry)

    return {
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "stop_loss_pct": STOP_LOSS_PCT,
        "target_2x": target_2x,
        "target_3x": target_3x,
        "target_5x": current_price * 5,
        "target_10x": current_price * 10,
        "target_100x": current_price * 100,
        "nearest_support": nearest_support,
        "nearest_resistance": (
            min(ta_result.resistance_levels)
            if ta_result.resistance_levels
            else None
        ),
    }


@dataclass
class MoonshotScore:
    total: float = 0.0
    tier: str = ""
    multiplier_target: str = ""

    dip_depth_score: float = 0.0
    mcap_score: float = 0.0
    volume_spike_score: float = 0.0
    volatility_score: float = 0.0
    momentum_score: float = 0.0
    buy_pressure_score: float = 0.0

    risk_level: str = "EXTREME"
    reasons: list = None
    warnings: list = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.warnings is None:
            self.warnings = []


def compute_moonshot(price_usd, fdv, h1, h6, h24, vol_5m, vol_h1, vol_24h,
                     liquidity, txns, ta_result, safety_result):
    """
    Score tokens for high-risk/high-reward degen plays.
    Inverts the normal logic: deeper dip + lower mcap + higher volatility = better.
    """
    ms = MoonshotScore()
    reasons = []
    warnings = []

    if price_usd <= 0:
        return ms

    # ── Dip depth (30%) — deeper crash = bigger potential bounce ─────────
    if h24 < -70:
        ms.dip_depth_score = 100
        reasons.append(f"Massive crash {h24:.0f}% in 24h — max rebound potential")
    elif h24 < -50:
        ms.dip_depth_score = 85
        reasons.append(f"Deep crash {h24:.0f}% in 24h")
    elif h24 < -35:
        ms.dip_depth_score = 65
        reasons.append(f"Strong dip {h24:.0f}% in 24h")
    elif h6 < -30:
        ms.dip_depth_score = 60
        reasons.append(f"Fast dump {h6:.0f}% in 6h")
    elif h6 < -15 or h24 < -20:
        ms.dip_depth_score = 35
    else:
        ms.dip_depth_score = 10

    # ── Market cap (25%) — micro/nano cap = biggest multiplier room ─────
    if fdv < 100_000:
        ms.mcap_score = 100
        reasons.append(f"Nano-cap {fdv/1000:.0f}K — massive upside if it catches")
    elif fdv < 500_000:
        ms.mcap_score = 90
        reasons.append(f"Micro-cap {fdv/1000:.0f}K — huge room to run")
    elif fdv < 2_000_000:
        ms.mcap_score = 70
        reasons.append(f"Low-cap {fdv/1e6:.1f}M")
    elif fdv < 10_000_000:
        ms.mcap_score = 45
    elif fdv < 50_000_000:
        ms.mcap_score = 25
    else:
        ms.mcap_score = 5

    # ── Volume spike (20%) — sudden volume = attention ──────────────────
    if vol_h1 > 0 and vol_24h > 0:
        hourly_rate = vol_h1 * 24
        vol_ratio = hourly_rate / vol_24h if vol_24h > 0 else 0
        if vol_ratio > 5:
            ms.volume_spike_score = 100
            reasons.append(f"Volume exploding {vol_ratio:.1f}x above average")
        elif vol_ratio > 3:
            ms.volume_spike_score = 80
            reasons.append(f"Volume surging {vol_ratio:.1f}x")
        elif vol_ratio > 1.5:
            ms.volume_spike_score = 55
        elif vol_ratio > 1:
            ms.volume_spike_score = 35
        else:
            ms.volume_spike_score = 15
    else:
        ms.volume_spike_score = 20

    # ── Volatility (10%) — high swings = bigger potential moves ─────────
    swing = abs(h1) + abs(h6)
    if swing > 50:
        ms.volatility_score = 100
        reasons.append(f"Extreme volatility ({swing:.0f}% combined swings)")
    elif swing > 30:
        ms.volatility_score = 75
    elif swing > 15:
        ms.volatility_score = 50
    else:
        ms.volatility_score = 20

    # ── Momentum reversal (10%) — catching the turn ─────────────────────
    if ta_result.available and ta_result.momentum_signal == "STRONG_REVERSAL":
        ms.momentum_score = 100
        reasons.append("Strong momentum reversal detected")
    elif ta_result.available and ta_result.momentum_signal == "WEAK_REVERSAL":
        ms.momentum_score = 60
    elif h1 > 5 and (h6 < -20 or h24 < -30):
        ms.momentum_score = 70
        reasons.append(f"Bouncing {h1:+.1f}% off deep dip")
    elif h1 > 0:
        ms.momentum_score = 40
    else:
        ms.momentum_score = 15

    # ── Buy pressure (5%) — are buyers stepping in? ─────────────────────
    recent_ratio = 0
    for tf_key in ("m5", "h1"):
        tf = (txns or {}).get(tf_key, {})
        buys = int(tf.get("buys", 0) or 0)
        sells = int(tf.get("sells", 0) or 0)
        total = buys + sells
        if total > 0:
            recent_ratio = max(recent_ratio, buys / total)
    if recent_ratio > 0.70:
        ms.buy_pressure_score = 100
        reasons.append(f"Heavy buy pressure ({recent_ratio:.0%} buys)")
    elif recent_ratio > 0.55:
        ms.buy_pressure_score = 60
    else:
        ms.buy_pressure_score = 25

    # ── Composite ────────────────────────────────────────────────────────
    ms.total = round(
        ms.dip_depth_score * 0.30
        + ms.mcap_score * 0.25
        + ms.volume_spike_score * 0.20
        + ms.volatility_score * 0.10
        + ms.momentum_score * 0.10
        + ms.buy_pressure_score * 0.05,
        1,
    )

    # ── Tier + target ────────────────────────────────────────────────────
    if ms.total >= 80 and fdv < 500_000:
        ms.tier = "100x MOONSHOT"
        ms.multiplier_target = "100x"
        ms.risk_level = "EXTREME"
    elif ms.total >= 70 and fdv < 2_000_000:
        ms.tier = "10x RUNNER"
        ms.multiplier_target = "10x"
        ms.risk_level = "VERY HIGH"
    elif ms.total >= 55:
        ms.tier = "5x POTENTIAL"
        ms.multiplier_target = "5x"
        ms.risk_level = "HIGH"
    elif ms.total >= 40:
        ms.tier = "3x POSSIBLE"
        ms.multiplier_target = "3x"
        ms.risk_level = "HIGH"
    else:
        ms.tier = "LOW POTENTIAL"
        ms.multiplier_target = "2x"
        ms.risk_level = "MODERATE"

    # ── Warnings ─────────────────────────────────────────────────────────
    if liquidity < 5_000:
        warnings.append(f"Very low liquidity (${liquidity:,.0f}) — slippage risk")
    if safety_result.has_mint_authority:
        warnings.append("Mint authority active — supply can be inflated")
    if safety_result.has_freeze_authority:
        warnings.append("Freeze authority active — tokens can be frozen")
    if fdv < 100_000:
        warnings.append("Nano-cap — could go to zero instantly")
    if vol_24h < 20_000:
        warnings.append("Very low volume — may not be able to exit")

    ms.reasons = reasons
    ms.warnings = warnings
    return ms
