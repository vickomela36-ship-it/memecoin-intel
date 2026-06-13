"""
Crypto price forecast engine — fetches market data for BTC, ETH, SOL, DOGE
and produces forecasted price targets at two tiers:
  1. High-probability forecast (conservative, based on trend + momentum)
  2. Low-probability / high-upside scenarios (breakout / breakdown extremes)
"""

import json
import os
import math
import requests
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from config import (
    COINGECKO_API, FEAR_GREED_API, BINANCE_FAPI,
    CRYPTO_ASSETS, CRYPTO_PREDICTIONS_FILE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Fetching
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_coingecko_ohlc(coin_id, days=90):
    try:
        url = f"{COINGECKO_API}/coins/{coin_id}/ohlc"
        resp = requests.get(url, params={"vs_currency": "usd", "days": days}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _fetch_coingecko_price(coin_id):
    try:
        url = f"{COINGECKO_API}/simple/price"
        resp = requests.get(url, params={
            "ids": coin_id, "vs_currencies": "usd",
            "include_24hr_change": "true", "include_market_cap": "true",
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def _fetch_fear_greed():
    try:
        resp = requests.get(f"{FEAR_GREED_API}/", params={"limit": 1, "format": "json"}, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if data:
            return int(data[0].get("value", 50)), data[0].get("value_classification", "Neutral")
    except Exception:
        pass
    return 50, "Neutral"


def _fetch_funding_rate(symbol):
    try:
        url = f"{BINANCE_FAPI}/fapi/v1/fundingRate"
        resp = requests.get(url, params={"symbol": symbol, "limit": 10}, timeout=15)
        resp.raise_for_status()
        rates = [float(e.get("fundingRate", 0)) for e in resp.json()]
        return sum(rates) / len(rates) if rates else 0.0
    except Exception:
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Technical Analysis Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_sma(closes, period):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _compute_volatility(closes, period=30):
    if len(closes) < period + 1:
        return 0.0
    returns = [(closes[i] / closes[i - 1]) - 1.0 for i in range(-period, 0)]
    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    return math.sqrt(variance)


def _find_support_resistance(ohlcv):
    if not ohlcv or len(ohlcv) < 10:
        return None, None
    lows = [c[3] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    recent_lows = sorted(lows[-30:]) if len(lows) >= 30 else sorted(lows)
    recent_highs = sorted(highs[-30:], reverse=True) if len(highs) >= 30 else sorted(highs, reverse=True)
    support = recent_lows[len(recent_lows) // 5] if recent_lows else None
    resistance = recent_highs[len(recent_highs) // 5] if recent_highs else None
    return support, resistance


# ═══════════════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PriceTarget:
    label: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    probability: str = ""
    timeframe: str = "7 days"
    rationale: str = ""


@dataclass
class CryptoPrediction:
    asset: str = ""
    current_price: float = 0.0
    price_24h_change: float = 0.0
    market_cap: float = 0.0
    # Trend
    direction: str = "NEUTRAL"
    confidence: str = "LOW"
    trend_summary: str = ""
    # Key levels
    support: float = 0.0
    resistance: float = 0.0
    # Indicators
    rsi: float = 50.0
    sma_20: float = 0.0
    sma_50: float = 0.0
    fear_greed: int = 50
    fear_greed_label: str = "Neutral"
    funding_rate: float = 0.0
    volatility_daily: float = 0.0
    # Forecasts
    high_prob_targets: list = field(default_factory=list)
    low_prob_upside: list = field(default_factory=list)
    # Meta
    updated_at: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Forecast Engine
# ═══════════════════════════════════════════════════════════════════════════════

def _build_forecast(asset, config):
    coin_id = config["coingecko_id"]
    binance_symbol = config["binance_symbol"]

    # Fetch data in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        f_ohlc = executor.submit(_fetch_coingecko_ohlc, coin_id, 90)
        f_price = executor.submit(_fetch_coingecko_price, coin_id)
        f_fg = executor.submit(_fetch_fear_greed)
        f_fund = executor.submit(_fetch_funding_rate, binance_symbol)

    ohlcv = f_ohlc.result()
    price_data = f_price.result()
    fg_value, fg_label = f_fg.result()
    avg_funding = f_fund.result()

    # Current price
    coin_data = price_data.get(coin_id, {})
    current_price = coin_data.get("usd", 0.0)
    change_24h = coin_data.get("usd_24h_change", 0.0)
    market_cap = coin_data.get("usd_market_cap", 0.0)

    if not current_price or not ohlcv:
        return CryptoPrediction(
            asset=asset, current_price=current_price,
            direction="NEUTRAL", confidence="LOW",
            trend_summary="Insufficient data to generate forecast.",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    closes = [c[4] for c in ohlcv]

    # Technical indicators
    rsi = _compute_rsi(closes)
    sma_20 = _compute_sma(closes, 20) or current_price
    sma_50 = _compute_sma(closes, 50) or current_price
    daily_vol = _compute_volatility(closes, 30)
    support, resistance = _find_support_resistance(ohlcv)
    support = support or current_price * 0.9
    resistance = resistance or current_price * 1.1

    # Trend direction scoring
    score = 0.0

    # RSI
    if rsi < 30:
        score += 30
    elif rsi < 40:
        score += 15
    elif rsi > 70:
        score -= 30
    elif rsi > 60:
        score -= 15

    # MA alignment
    if sma_20 > sma_50:
        score += 20
    else:
        score -= 20

    # Price vs MAs
    if current_price > sma_20:
        score += 10
    else:
        score -= 10

    # Funding rate (contrarian)
    if avg_funding > 0.0005:
        score -= 15
    elif avg_funding < -0.0005:
        score += 15

    # Fear & Greed (contrarian)
    if fg_value < 25:
        score += 15
    elif fg_value > 75:
        score -= 15

    # 24h momentum
    if change_24h > 3:
        score += 10
    elif change_24h < -3:
        score -= 10

    # Direction and confidence
    if score > 25:
        direction = "BULLISH"
    elif score < -25:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    abs_score = abs(score)
    if abs_score > 50:
        confidence = "HIGH"
    elif abs_score > 25:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # ── Build price targets ──────────────────────────────────────────────
    weekly_move = daily_vol * math.sqrt(7) * current_price
    monthly_move = daily_vol * math.sqrt(30) * current_price

    high_prob_targets = []
    low_prob_upside = []

    if direction == "BULLISH":
        # High probability: conservative upside
        conservative_target = current_price + weekly_move * 0.5
        moderate_target = min(resistance, current_price + weekly_move)

        high_prob_targets.append(PriceTarget(
            label="Base Case (Bull)",
            price=round(conservative_target, 2),
            change_pct=round((conservative_target / current_price - 1) * 100, 1),
            probability="65-75%",
            timeframe="7 days",
            rationale=f"Trend momentum + RSI {rsi:.0f} supports continued upside to this level.",
        ))
        high_prob_targets.append(PriceTarget(
            label="Resistance Test",
            price=round(moderate_target, 2),
            change_pct=round((moderate_target / current_price - 1) * 100, 1),
            probability="45-55%",
            timeframe="7-14 days",
            rationale=f"Next major resistance at ${moderate_target:,.0f}. Needs volume confirmation.",
        ))

        # Downside risk
        high_prob_targets.append(PriceTarget(
            label="Pullback Risk",
            price=round(current_price - weekly_move * 0.3, 2),
            change_pct=round((-weekly_move * 0.3 / current_price) * 100, 1),
            probability="20-30%",
            timeframe="7 days",
            rationale="Normal pullback within bullish trend. Support should hold.",
        ))

        # Low prob / high upside
        breakout_target = current_price + monthly_move * 1.5
        low_prob_upside.append(PriceTarget(
            label="Breakout Moonshot",
            price=round(breakout_target, 2),
            change_pct=round((breakout_target / current_price - 1) * 100, 1),
            probability="10-15%",
            timeframe="30 days",
            rationale=f"If resistance at ${resistance:,.0f} breaks with volume, next leg up targets this zone.",
        ))

    elif direction == "BEARISH":
        conservative_drop = current_price - weekly_move * 0.5
        moderate_drop = max(support, current_price - weekly_move)

        high_prob_targets.append(PriceTarget(
            label="Base Case (Bear)",
            price=round(conservative_drop, 2),
            change_pct=round((conservative_drop / current_price - 1) * 100, 1),
            probability="65-75%",
            timeframe="7 days",
            rationale=f"Bearish momentum + RSI {rsi:.0f} suggests further downside.",
        ))
        high_prob_targets.append(PriceTarget(
            label="Support Test",
            price=round(moderate_drop, 2),
            change_pct=round((moderate_drop / current_price - 1) * 100, 1),
            probability="45-55%",
            timeframe="7-14 days",
            rationale=f"Key support at ${moderate_drop:,.0f}. Break below = acceleration.",
        ))

        # Relief bounce
        high_prob_targets.append(PriceTarget(
            label="Relief Bounce",
            price=round(current_price + weekly_move * 0.3, 2),
            change_pct=round((weekly_move * 0.3 / current_price) * 100, 1),
            probability="20-30%",
            timeframe="7 days",
            rationale="Dead cat bounce possible. Don't chase — wait for confirmation.",
        ))

        # Low prob / high upside
        crash_target = current_price - monthly_move * 1.5
        reversal_target = current_price + monthly_move * 1.2
        low_prob_upside.append(PriceTarget(
            label="Capitulation Wick",
            price=round(max(crash_target, current_price * 0.6), 2),
            change_pct=round((max(crash_target, current_price * 0.6) / current_price - 1) * 100, 1),
            probability="5-10%",
            timeframe="30 days",
            rationale="Flash crash / liquidation cascade. Great buy zone if it hits.",
        ))
        low_prob_upside.append(PriceTarget(
            label="V-Shape Reversal",
            price=round(reversal_target, 2),
            change_pct=round((reversal_target / current_price - 1) * 100, 1),
            probability="10-15%",
            timeframe="30 days",
            rationale="Macro catalyst or short squeeze could trigger violent reversal.",
        ))

    else:
        # Neutral — range-bound
        upper_range = current_price + weekly_move * 0.4
        lower_range = current_price - weekly_move * 0.4

        high_prob_targets.append(PriceTarget(
            label="Range High",
            price=round(upper_range, 2),
            change_pct=round((upper_range / current_price - 1) * 100, 1),
            probability="55-65%",
            timeframe="7 days",
            rationale="Choppy market. Expect price to oscillate within this range.",
        ))
        high_prob_targets.append(PriceTarget(
            label="Range Low",
            price=round(lower_range, 2),
            change_pct=round((lower_range / current_price - 1) * 100, 1),
            probability="55-65%",
            timeframe="7 days",
            rationale="Downside of the expected range. Good accumulation zone.",
        ))

        # Low prob breakout either way
        low_prob_upside.append(PriceTarget(
            label="Breakout Up",
            price=round(current_price + monthly_move, 2),
            change_pct=round((monthly_move / current_price) * 100, 1),
            probability="15-20%",
            timeframe="30 days",
            rationale=f"Break above ${resistance:,.0f} with catalyst could trigger trend.",
        ))
        low_prob_upside.append(PriceTarget(
            label="Breakdown",
            price=round(current_price - monthly_move, 2),
            change_pct=round((-monthly_move / current_price) * 100, 1),
            probability="15-20%",
            timeframe="30 days",
            rationale=f"Loss of ${support:,.0f} support would accelerate selling.",
        ))

    # Trend summary
    funding_note = ""
    if abs(avg_funding) > 0.0003:
        side = "longs" if avg_funding > 0 else "shorts"
        funding_note = f" Funding rate favors {side} getting squeezed."

    trend_summary = (
        f"{direction} bias. RSI at {rsi:.0f}, price "
        f"{'above' if current_price > sma_20 else 'below'} 20-SMA "
        f"(${sma_20:,.0f}). "
        f"Fear & Greed: {fg_value} ({fg_label}). "
        f"Daily vol: {daily_vol * 100:.1f}%.{funding_note}"
    )

    return CryptoPrediction(
        asset=asset,
        current_price=round(current_price, 2),
        price_24h_change=round(change_24h, 2),
        market_cap=market_cap,
        direction=direction,
        confidence=confidence,
        trend_summary=trend_summary,
        support=round(support, 2),
        resistance=round(resistance, 2),
        rsi=round(rsi, 1),
        sma_20=round(sma_20, 2),
        sma_50=round(sma_50, 2),
        fear_greed=fg_value,
        fear_greed_label=fg_label,
        funding_rate=round(avg_funding * 100, 4),
        volatility_daily=round(daily_vol * 100, 2),
        high_prob_targets=high_prob_targets,
        low_prob_upside=low_prob_upside,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_predictions():
    predictions = []
    ts = datetime.now(timezone.utc).isoformat()
    for asset, config in CRYPTO_ASSETS.items():
        try:
            pred = _build_forecast(asset, config)
            pred.updated_at = ts
            predictions.append(pred)
        except Exception:
            predictions.append(CryptoPrediction(
                asset=asset, direction="NEUTRAL", confidence="LOW",
                trend_summary="Failed to fetch data.",
                updated_at=ts,
            ))
    return predictions


def log_prediction(prediction):
    entry = {
        "asset": prediction.asset,
        "current_price": prediction.current_price,
        "direction": prediction.direction,
        "confidence": prediction.confidence,
        "high_prob": [
            {"label": t.label, "price": t.price, "probability": t.probability}
            for t in prediction.high_prob_targets
        ],
        "low_prob_upside": [
            {"label": t.label, "price": t.price, "probability": t.probability}
            for t in prediction.low_prob_upside
        ],
        "updated_at": prediction.updated_at,
    }

    history = []
    if os.path.exists(CRYPTO_PREDICTIONS_FILE):
        try:
            with open(CRYPTO_PREDICTIONS_FILE, "r") as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        except (json.JSONDecodeError, IOError):
            history = []

    history.append(entry)
    try:
        with open(CRYPTO_PREDICTIONS_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except IOError:
        pass


def get_prediction_history(asset=None):
    if not os.path.exists(CRYPTO_PREDICTIONS_FILE):
        return []
    try:
        with open(CRYPTO_PREDICTIONS_FILE, "r") as f:
            history = json.load(f)
            if not isinstance(history, list):
                return []
    except (json.JSONDecodeError, IOError):
        return []
    if asset is not None:
        history = [e for e in history if e.get("asset") == asset]
    return history
