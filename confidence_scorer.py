"""
confidence_scorer.py -- Composite confidence scoring with letter grades
and moonshot scoring for degen plays.

Combines Fibonacci proximity, RSI, volume trend, sentiment, holder
distribution, VWAP positioning, and momentum pattern signals into a
single weighted score with an A-D letter grade (F if safety fails).

A separate moonshot scorer uses *inverted* logic -- deeper dips, lower
market caps, and wilder volatility produce higher scores -- to surface
high-risk / high-reward degen opportunities.
"""

from dataclasses import dataclass, field

from config import (
    WEIGHT_FIB, WEIGHT_RSI, WEIGHT_VOLUME, WEIGHT_SENTIMENT,
    WEIGHT_HOLDERS, WEIGHT_VWAP, WEIGHT_PATTERN,
    GRADE_A_MIN, GRADE_B_MIN, GRADE_C_MIN,
    FIB_PROXIMITY_PCT, STOP_LOSS_PCT,
)


# =============================================================================
# Data classes
# =============================================================================

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


# =============================================================================
# Helpers
# =============================================================================

def _safe_get(obj, *keys, default=0.0):
    """Walk nested dicts/objects safely, returning *default* on any miss."""
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif hasattr(current, key):
            current = getattr(current, key, None)
        else:
            return default
        if current is None:
            return default
    try:
        return float(current)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# =============================================================================
# Sub-score functions  (each returns (score, note_or_None))
# =============================================================================

def _score_fib(current_price: float, fib_levels: dict,
               nearest_fib_level: float, proximity_pct: float):
    """0-100. Best when price sits near the 0.618 or 0.786 retracement."""
    if not fib_levels or current_price <= 0:
        return 0.0, None

    # Importance weights per Fibonacci level
    level_weights = {
        0.236: 0.4,
        0.382: 0.6,
        0.5:   0.7,
        0.618: 1.0,
        0.786: 0.9,
    }

    # Base score from the nearest level's importance
    weight = level_weights.get(nearest_fib_level, 0.5)
    importance_score = weight * 60  # up to 60 pts from importance

    # Proximity bonus -- the closer the better
    if proximity_pct <= 0:
        proximity_bonus = 40
    elif proximity_pct <= FIB_PROXIMITY_PCT:
        proximity_bonus = 40 * (1 - proximity_pct / FIB_PROXIMITY_PCT)
    else:
        proximity_bonus = max(0, 20 - proximity_pct)

    score = _clamp(importance_score + proximity_bonus)
    note = None
    if score >= 70:
        note = f"Price near key Fib {nearest_fib_level} ({proximity_pct:.1f}% away)"
    return score, note


def _score_rsi(rsi_1m: float, rsi_5m: float):
    """0-100. Sweet spot is oversold bounce-back (25-40 range)."""
    if rsi_1m <= 0 and rsi_5m <= 0:
        return 0.0, None

    def _single_rsi_score(rsi_val):
        if rsi_val <= 0:
            return 0
        # Oversold bounce zone (25-40) -- best
        if 25 <= rsi_val <= 40:
            return 100
        # Slightly oversold (15-25) -- still strong
        if 15 <= rsi_val < 25:
            return 80
        # Recovering (40-50) -- decent
        if 40 < rsi_val <= 50:
            return 70
        # Neutral (50-60)
        if 50 < rsi_val <= 60:
            return 45
        # Getting hot (60-70)
        if 60 < rsi_val <= 70:
            return 25
        # Overbought (>70) -- risky entry
        if rsi_val > 70:
            return 10
        # Deeply oversold (<15) -- could be dead
        return 40

    score_1m = _single_rsi_score(rsi_1m)
    score_5m = _single_rsi_score(rsi_5m)

    # Weight 5-min more heavily (more reliable)
    score = _clamp(score_1m * 0.4 + score_5m * 0.6)

    note = None
    if score >= 70:
        note = f"RSI in bounce zone (1m: {rsi_1m:.0f}, 5m: {rsi_5m:.0f})"
    return score, note


def _score_volume(volume_trend: str, volume_ratio: float):
    """0-100. STRONG_RECOVERY is highest; DEAD_CAT lowest."""
    trend_scores = {
        "STRONG_RECOVERY": 90,
        "RECOVERY":        70,
        "INCREASING":      65,
        "STABLE":          45,
        "DECLINING":       25,
        "DEAD_CAT":        10,
    }

    base = trend_scores.get(str(volume_trend).upper(), 30)

    # Volume ratio bonus (how current vol compares to average)
    ratio_bonus = 0
    if volume_ratio > 3.0:
        ratio_bonus = 20
    elif volume_ratio > 2.0:
        ratio_bonus = 12
    elif volume_ratio > 1.5:
        ratio_bonus = 6

    score = _clamp(base + ratio_bonus)
    note = None
    if score >= 65:
        note = f"Volume trend {volume_trend} (ratio: {volume_ratio:.1f}x)"
    return score, note


def _score_sentiment(txns: dict, boosts: int, pair_data: dict):
    """0-100. Buy/sell ratios across timeframes, boosts, social presence."""
    score = 0.0

    # -- Buy/sell ratio in 5-minute window --
    if txns and isinstance(txns, dict):
        m5 = txns.get("m5", {})
        if isinstance(m5, dict):
            buys_m5 = float(m5.get("buys", 0))
            sells_m5 = float(m5.get("sells", 0))
            if sells_m5 > 0:
                ratio_m5 = buys_m5 / sells_m5
                if ratio_m5 >= 2.0:
                    score += 25
                elif ratio_m5 >= 1.3:
                    score += 18
                elif ratio_m5 >= 1.0:
                    score += 10
                else:
                    score += 3

        # -- Buy/sell ratio in 1-hour window --
        h1 = txns.get("h1", {})
        if isinstance(h1, dict):
            buys_h1 = float(h1.get("buys", 0))
            sells_h1 = float(h1.get("sells", 0))
            if sells_h1 > 0:
                ratio_h1 = buys_h1 / sells_h1
                if ratio_h1 >= 2.0:
                    score += 20
                elif ratio_h1 >= 1.3:
                    score += 14
                elif ratio_h1 >= 1.0:
                    score += 8
                else:
                    score += 2

    # -- DexScreener boosts --
    if boosts >= 50:
        score += 20
    elif boosts >= 20:
        score += 15
    elif boosts >= 5:
        score += 10
    elif boosts >= 1:
        score += 5

    # -- Social / website presence from pair_data --
    if pair_data and isinstance(pair_data, dict):
        info = pair_data.get("info", {})
        if isinstance(info, dict):
            websites = info.get("websites", [])
            socials = info.get("socials", [])

            if websites:
                score += 10
            if socials:
                for social in socials:
                    s_type = ""
                    if isinstance(social, dict):
                        s_type = social.get("type", "").lower()
                    elif isinstance(social, str):
                        s_type = social.lower()
                    if "twitter" in s_type:
                        score += 8
                    elif "telegram" in s_type:
                        score += 7

    score = _clamp(score)
    note = None
    if score >= 55:
        note = f"Strong sentiment (score {score:.0f}, {boosts} boosts)"
    return score, note


def _score_holders(top10_pct: float, holder_count: int):
    """0-100. Lower concentration + more holders = higher score."""
    score = 0.0

    # -- Top-10 holder concentration (lower is better) --
    if top10_pct <= 0:
        conc_score = 30  # no data, neutral
    elif top10_pct <= 20:
        conc_score = 100
    elif top10_pct <= 35:
        conc_score = 80
    elif top10_pct <= 50:
        conc_score = 55
    elif top10_pct <= 70:
        conc_score = 30
    else:
        conc_score = 10

    # -- Holder count (more is better) --
    if holder_count >= 1000:
        count_score = 100
    elif holder_count >= 500:
        count_score = 80
    elif holder_count >= 200:
        count_score = 60
    elif holder_count >= 50:
        count_score = 40
    elif holder_count >= 20:
        count_score = 25
    else:
        count_score = 10

    # Blend 60/40 concentration vs count
    score = _clamp(conc_score * 0.6 + count_score * 0.4)
    note = None
    if score >= 60:
        note = f"Healthy holders ({holder_count}, top-10 own {top10_pct:.1f}%)"
    return score, note


def _score_vwap(price_vs_vwap_pct: float, vwap_reclaim: str, vwap: float):
    """0-100. VWAP reclaim is bullish, above is good, below varies."""
    if vwap <= 0:
        return 0.0, None

    reclaim_upper = str(vwap_reclaim).upper() if vwap_reclaim else ""

    if reclaim_upper == "RECLAIM" or reclaim_upper == "VWAP_RECLAIM":
        score = 90.0
        note = "VWAP reclaimed -- bullish"
    elif price_vs_vwap_pct > 0:
        # Above VWAP
        if price_vs_vwap_pct <= 2:
            score = 75.0
        elif price_vs_vwap_pct <= 5:
            score = 70.0
        else:
            score = 60.0
        note = f"Price {price_vs_vwap_pct:.1f}% above VWAP"
    else:
        # Below VWAP
        dist = abs(price_vs_vwap_pct)
        if dist <= 2:
            score = 55.0
        elif dist <= 5:
            score = 40.0
        elif dist <= 10:
            score = 25.0
        else:
            score = 10.0
        note = f"Price {dist:.1f}% below VWAP"

    score = _clamp(score)
    if score < 50:
        note = None  # only surface as strength if decent
    return score, note


def _score_pattern(momentum_shift: str, momentum_signal: str):
    """0-100. STRONG_REVERSAL is the best entry pattern."""
    shift_upper = str(momentum_shift).upper() if momentum_shift else ""
    signal_upper = str(momentum_signal).upper() if momentum_signal else ""

    # Primary: momentum_shift
    if "STRONG_REVERSAL" in shift_upper or "STRONG_REVERSAL" in signal_upper:
        base = 85
    elif "WEAK_REVERSAL" in shift_upper or "WEAK_REVERSAL" in signal_upper:
        base = 50
    elif "NO_REVERSAL" in shift_upper or "NO_REVERSAL" in signal_upper:
        base = 15
    elif "CONTINUATION" in shift_upper or "CONTINUATION" in signal_upper:
        base = 60
    else:
        base = 20

    # Signal-based bonus
    bonus = 0
    if "BULLISH" in signal_upper:
        bonus = 10
    elif "BEARISH" in signal_upper:
        bonus = -10

    score = _clamp(base + bonus)
    note = None
    if score >= 50:
        note = f"Pattern: {momentum_shift or momentum_signal}"
    return score, note


# =============================================================================
# Main confidence computation
# =============================================================================

def compute_confidence(safety_result, ta_result, pair_data: dict,
                       txns: dict = None, boosts: int = 0,
                       current_price: float = 0.0) -> ConfidenceScore:
    """Build a composite confidence score from safety, TA, and market data.

    Parameters
    ----------
    safety_result : SafetyResult
        Output of ``check_token_safety``.
    ta_result : object
        Technical analysis result with attributes like ``rsi_1m``,
        ``rsi_5m``, ``volume_trend``, ``nearest_fib_level``, etc.
    pair_data : dict
        DexScreener pair data.
    txns : dict, optional
        Transaction buy/sell counts per timeframe.
    boosts : int
        DexScreener boost count.
    current_price : float
        Current token price in USD.

    Returns
    -------
    ConfidenceScore
    """
    cs = ConfidenceScore()
    cs.safety_passed = getattr(safety_result, "passed", False)

    # -- Immediate fail if safety did not pass --
    if not cs.safety_passed:
        cs.total = 0.0
        cs.grade = "F"
        cs.summary = "SAFETY FAILED -- do not trade"
        cs.weaknesses.append("Token failed safety checks")
        fail_reasons = getattr(safety_result, "fail_reasons", [])
        for reason in fail_reasons:
            cs.weaknesses.append(reason)
        return cs

    # -- Extract TA attributes safely --
    fib_levels = getattr(ta_result, "fib_levels", {})
    nearest_fib_level = getattr(ta_result, "nearest_fib_level", 0.0)
    fib_proximity_pct = getattr(ta_result, "fib_proximity_pct", 100.0)
    rsi_1m = getattr(ta_result, "rsi_1m", 0.0)
    rsi_5m = getattr(ta_result, "rsi_5m", 0.0)
    volume_trend = getattr(ta_result, "volume_trend", "")
    volume_ratio = getattr(ta_result, "volume_ratio", 0.0)
    price_vs_vwap_pct = getattr(ta_result, "price_vs_vwap_pct", 0.0)
    vwap_reclaim = getattr(ta_result, "vwap_reclaim", "")
    vwap = getattr(ta_result, "vwap", 0.0)
    momentum_shift = getattr(ta_result, "momentum_shift", "")
    momentum_signal = getattr(ta_result, "momentum_signal", "")

    top10_pct = getattr(safety_result, "top10_holder_pct", 0.0)
    holder_count = getattr(safety_result, "holder_count", 0)

    # -- Compute each sub-score --
    cs.fib_score, fib_note = _score_fib(
        current_price, fib_levels, nearest_fib_level, fib_proximity_pct,
    )
    cs.rsi_score, rsi_note = _score_rsi(rsi_1m, rsi_5m)
    cs.volume_score, vol_note = _score_volume(volume_trend, volume_ratio)
    cs.sentiment_score, sent_note = _score_sentiment(txns, boosts, pair_data)
    cs.holder_score, hold_note = _score_holders(top10_pct, holder_count)
    cs.vwap_score, vwap_note = _score_vwap(
        price_vs_vwap_pct, vwap_reclaim, vwap,
    )
    cs.pattern_score, pat_note = _score_pattern(momentum_shift, momentum_signal)

    # -- Collect strengths & weaknesses --
    scored = [
        ("Fibonacci", cs.fib_score, fib_note),
        ("RSI", cs.rsi_score, rsi_note),
        ("Volume", cs.volume_score, vol_note),
        ("Sentiment", cs.sentiment_score, sent_note),
        ("Holders", cs.holder_score, hold_note),
        ("VWAP", cs.vwap_score, vwap_note),
        ("Pattern", cs.pattern_score, pat_note),
    ]
    for name, sc, note in scored:
        if sc >= 60:
            cs.strengths.append(note if note else f"{name} score {sc:.0f}")
        elif sc <= 30:
            cs.weaknesses.append(f"{name} weak ({sc:.0f}/100)")

    # -- Weighted composite --
    cs.total = _clamp(
        cs.fib_score * WEIGHT_FIB
        + cs.rsi_score * WEIGHT_RSI
        + cs.volume_score * WEIGHT_VOLUME
        + cs.sentiment_score * WEIGHT_SENTIMENT
        + cs.holder_score * WEIGHT_HOLDERS
        + cs.vwap_score * WEIGHT_VWAP
        + cs.pattern_score * WEIGHT_PATTERN
    )

    # -- Letter grade --
    if cs.total >= GRADE_A_MIN:
        cs.grade = "A"
    elif cs.total >= GRADE_B_MIN:
        cs.grade = "B"
    elif cs.total >= GRADE_C_MIN:
        cs.grade = "C"
    else:
        cs.grade = "D"

    # -- Summary --
    top_strength = cs.strengths[0] if cs.strengths else "no standout signals"
    cs.summary = (
        f"Grade {cs.grade} ({cs.total:.1f}/100) -- {top_strength}"
    )

    return cs


# =============================================================================
# Entry / exit computation
# =============================================================================

def compute_entry_exit(current_price: float, ta_result, confidence_score: ConfidenceScore) -> dict:
    """Compute entry zone, stop-loss, and take-profit targets.

    Parameters
    ----------
    current_price : float
        Current token price in USD.
    ta_result : object
        TA result with ``support_levels``, ``resistance_levels``,
        ``fib_levels``, ``nearest_fib_level``.
    confidence_score : ConfidenceScore
        The computed confidence score (used for adaptive sizing).

    Returns
    -------
    dict
        Keys: entry_low, entry_high, stop_loss, stop_loss_pct,
        target_2x ... target_100x, nearest_support, nearest_resistance.
    """
    if current_price <= 0:
        return {
            "entry_low": 0, "entry_high": 0,
            "stop_loss": 0, "stop_loss_pct": STOP_LOSS_PCT,
            "target_2x": 0, "target_3x": 0, "target_5x": 0,
            "target_10x": 0, "target_100x": 0,
            "nearest_support": 0, "nearest_resistance": 0,
        }

    # -- Support & resistance --
    support_levels = getattr(ta_result, "support_levels", [])
    resistance_levels = getattr(ta_result, "resistance_levels", [])
    fib_levels = getattr(ta_result, "fib_levels", {})

    # Find nearest support below current price
    supports_below = [s for s in support_levels if s < current_price]
    nearest_support = max(supports_below) if supports_below else current_price * 0.90

    # Find nearest resistance above current price
    resistances_above = [r for r in resistance_levels if r > current_price]
    nearest_resistance = min(resistances_above) if resistances_above else current_price * 1.50

    # -- Entry zone --
    # Use support levels and fib levels for the entry zone
    fib_prices = []
    if isinstance(fib_levels, dict):
        fib_prices = sorted(
            v for v in fib_levels.values()
            if isinstance(v, (int, float)) and 0 < v < current_price
        )
    elif isinstance(fib_levels, list):
        fib_prices = sorted(
            v for v in fib_levels
            if isinstance(v, (int, float)) and 0 < v < current_price
        )

    # Entry low: best nearby support or fib level
    if fib_prices:
        # Closest fib level below price
        entry_low = fib_prices[-1]
    elif supports_below:
        entry_low = nearest_support
    else:
        entry_low = current_price * 0.95

    # Entry high: slightly below current price (buy the dip, not the top)
    entry_high = current_price * 0.99

    # Clamp entry_low to not be absurdly far from current price
    if entry_low < current_price * 0.80:
        entry_low = current_price * 0.92

    # -- Stop loss --
    stop_loss_pct = STOP_LOSS_PCT
    stop_loss = current_price * (1 - stop_loss_pct / 100.0)

    # -- Take-profit targets --
    result = {
        "entry_low": round(entry_low, 10),
        "entry_high": round(entry_high, 10),
        "stop_loss": round(stop_loss, 10),
        "stop_loss_pct": stop_loss_pct,
        "target_2x": round(current_price * 2, 10),
        "target_3x": round(current_price * 3, 10),
        "target_5x": round(current_price * 5, 10),
        "target_10x": round(current_price * 10, 10),
        "target_100x": round(current_price * 100, 10),
        "nearest_support": round(nearest_support, 10),
        "nearest_resistance": round(nearest_resistance, 10),
    }

    return result


# =============================================================================
# Moonshot (degen) scoring
# =============================================================================

def compute_moonshot(price_usd: float, fdv: float,
                     h1: float, h6: float, h24: float,
                     vol_5m: float, vol_h1: float, vol_24h: float,
                     liquidity: float, txns: dict,
                     ta_result, safety_result) -> MoonshotScore:
    """Inverted scoring for degen plays: deeper dips, lower mcap, and
    higher volatility produce higher moonshot scores.

    Parameters
    ----------
    price_usd : float
        Current price in USD.
    fdv : float
        Fully diluted valuation in USD.
    h1, h6, h24 : float
        Price change percentages for 1h, 6h, 24h.
    vol_5m, vol_h1, vol_24h : float
        Volume in USD for the respective timeframes.
    liquidity : float
        Current liquidity in USD.
    txns : dict
        Transaction buy/sell data per timeframe.
    ta_result : object
        Technical analysis result.
    safety_result : object
        Safety check result.

    Returns
    -------
    MoonshotScore
    """
    ms = MoonshotScore()

    # ── 1. Dip depth (30% weight) ───────────────────────────────────────
    if h24 < -70:
        ms.dip_depth_score = 100
        ms.reasons.append(f"24h crash {h24:.1f}% -- max dip opportunity")
    elif h24 < -50:
        ms.dip_depth_score = 85
        ms.reasons.append(f"24h dump {h24:.1f}% -- deep dip")
    elif h24 < -35:
        ms.dip_depth_score = 65
        ms.reasons.append(f"24h decline {h24:.1f}% -- solid dip")
    elif h6 < -30:
        ms.dip_depth_score = 60
        ms.reasons.append(f"6h drop {h6:.1f}% -- recent dump")
    elif h6 < -20:
        ms.dip_depth_score = 45
        ms.reasons.append(f"6h dip {h6:.1f}%")
    elif h1 < -15:
        ms.dip_depth_score = 40
        ms.reasons.append(f"1h drop {h1:.1f}% -- fresh dip")
    elif h24 < -20:
        ms.dip_depth_score = 35
        ms.reasons.append(f"24h dip {h24:.1f}%")
    else:
        ms.dip_depth_score = 10

    # ── 2. Market cap / FDV (25% weight) ────────────────────────────────
    if fdv <= 0:
        ms.mcap_score = 50  # unknown, neutral
    elif fdv < 100_000:
        ms.mcap_score = 100
        ms.reasons.append(f"Nano-cap ${fdv:,.0f} FDV -- max moon potential")
    elif fdv < 500_000:
        ms.mcap_score = 90
        ms.reasons.append(f"Micro-cap ${fdv:,.0f} FDV")
    elif fdv < 2_000_000:
        ms.mcap_score = 70
        ms.reasons.append(f"Low-cap ${fdv:,.0f} FDV")
    elif fdv < 10_000_000:
        ms.mcap_score = 45
        ms.reasons.append(f"Small-cap ${fdv:,.0f} FDV")
    elif fdv < 50_000_000:
        ms.mcap_score = 25
    else:
        ms.mcap_score = 10

    # ── 3. Volume spike (20% weight) ────────────────────────────────────
    hourly_rate = vol_h1 * 24 if vol_h1 > 0 else 0
    if vol_24h > 0 and hourly_rate > 0:
        vol_ratio = hourly_rate / vol_24h
        if vol_ratio >= 5.0:
            ms.volume_spike_score = 100
            ms.reasons.append(f"Volume spike {vol_ratio:.1f}x hourly vs 24h avg")
        elif vol_ratio >= 3.0:
            ms.volume_spike_score = 80
            ms.reasons.append(f"Volume surge {vol_ratio:.1f}x")
        elif vol_ratio >= 2.0:
            ms.volume_spike_score = 60
        elif vol_ratio >= 1.5:
            ms.volume_spike_score = 40
        else:
            ms.volume_spike_score = 20
    elif vol_5m > 0:
        # Fallback: project 5m volume to hourly
        projected = vol_5m * 12
        if vol_24h > 0:
            ratio = (projected * 24) / vol_24h
            ms.volume_spike_score = _clamp(ratio * 20)
        else:
            ms.volume_spike_score = 30
    else:
        ms.volume_spike_score = 5

    # ── 4. Volatility (10% weight) ──────────────────────────────────────
    combined_swing = abs(h1) + abs(h6)
    if combined_swing >= 80:
        ms.volatility_score = 100
        ms.reasons.append(f"Extreme volatility (combined swing {combined_swing:.0f}%)")
    elif combined_swing >= 50:
        ms.volatility_score = 80
    elif combined_swing >= 30:
        ms.volatility_score = 60
    elif combined_swing >= 15:
        ms.volatility_score = 40
    else:
        ms.volatility_score = 15

    # ── 5. Momentum (10% weight) ────────────────────────────────────────
    momentum_signal = getattr(ta_result, "momentum_signal", "") if ta_result else ""
    signal_upper = str(momentum_signal).upper()

    if "STRONG_REVERSAL" in signal_upper:
        ms.momentum_score = 90
        ms.reasons.append("TA shows strong reversal signal")
    elif "WEAK_REVERSAL" in signal_upper:
        ms.momentum_score = 60
    elif "BULLISH" in signal_upper:
        ms.momentum_score = 70
    elif momentum_signal:
        ms.momentum_score = 30
    else:
        # Fallback: h1 positive while h6/h24 deep negative = momentum shift
        if h1 > 5 and (h6 < -20 or h24 < -30):
            ms.momentum_score = 75
            ms.reasons.append(
                f"Momentum shift: 1h +{h1:.1f}% vs 6h {h6:.1f}%"
            )
        elif h1 > 0 and h6 < -10:
            ms.momentum_score = 50
        else:
            ms.momentum_score = 20

    # ── 6. Buy pressure (5% weight) ─────────────────────────────────────
    if txns and isinstance(txns, dict):
        # Check m5 and h1 buy/sell ratios
        best_ratio = 0.0
        for tf in ("m5", "h1"):
            tf_data = txns.get(tf, {})
            if isinstance(tf_data, dict):
                buys = float(tf_data.get("buys", 0))
                sells = float(tf_data.get("sells", 0))
                if sells > 0:
                    ratio = buys / sells
                    best_ratio = max(best_ratio, ratio)

        if best_ratio >= 3.0:
            ms.buy_pressure_score = 100
            ms.reasons.append(f"Strong buy pressure ({best_ratio:.1f}x buy/sell)")
        elif best_ratio >= 2.0:
            ms.buy_pressure_score = 80
        elif best_ratio >= 1.5:
            ms.buy_pressure_score = 60
        elif best_ratio >= 1.0:
            ms.buy_pressure_score = 40
        else:
            ms.buy_pressure_score = 15
    else:
        ms.buy_pressure_score = 20

    # ── Weighted total ──────────────────────────────────────────────────
    ms.total = _clamp(
        ms.dip_depth_score * 0.30
        + ms.mcap_score * 0.25
        + ms.volume_spike_score * 0.20
        + ms.volatility_score * 0.10
        + ms.momentum_score * 0.10
        + ms.buy_pressure_score * 0.05
    )

    # ── Tier assignment ─────────────────────────────────────────────────
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
        ms.risk_level = "MODERATE-HIGH"
    else:
        ms.tier = "LOW POTENTIAL"
        ms.multiplier_target = "2x"
        ms.risk_level = "HIGH"

    # ── Warnings ────────────────────────────────────────────────────────
    if liquidity < 10_000:
        ms.warnings.append(
            f"Very low liquidity ${liquidity:,.0f} -- high slippage risk"
        )
    elif liquidity < 30_000:
        ms.warnings.append(f"Low liquidity ${liquidity:,.0f}")

    if safety_result:
        if getattr(safety_result, "has_mint_authority", False):
            ms.warnings.append("Mint authority enabled -- infinite supply risk")
        if getattr(safety_result, "has_freeze_authority", False):
            ms.warnings.append("Freeze authority enabled -- funds can be frozen")

    if fdv > 0 and fdv < 100_000:
        ms.warnings.append(
            f"Nano-cap (${fdv:,.0f}) -- extreme volatility, low liquidity likely"
        )

    if vol_24h < 10_000:
        ms.warnings.append(
            f"Very low 24h volume ${vol_24h:,.0f} -- difficult to exit"
        )
    elif vol_24h < 50_000:
        ms.warnings.append(f"Low 24h volume ${vol_24h:,.0f}")

    return ms
