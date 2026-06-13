"""
Crypto prediction engine — aggregates quantitative signals for BTC, ETH, SOL,
DOGE into a composite -100 to +100 score, then compares against Polymarket odds
to find mispriced bets.
"""

import time
import json
import os
import math
import requests
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from config import (
    COINGECKO_API, FEAR_GREED_API, BINANCE_FAPI, DEFILLAMA_API,
    POLYMARKET_GAMMA_API, CRYPTO_ASSETS, CRYPTO_SIGNAL_WEIGHTS,
    CRYPTO_CACHE_SECONDS, CRYPTO_STALE_SECONDS,
    CRYPTO_PREDICTIONS_FILE,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Data fetching functions
# ═══════════════════════════════════════════════════════════════════════════════


def _fetch_coingecko_ohlc(coin_id, days=90):
    """GET OHLC candle data from CoinGecko.
    Returns list of [timestamp, open, high, low, close].
    """
    try:
        url = f"{COINGECKO_API}/coins/{coin_id}/ohlc"
        resp = requests.get(
            url,
            params={"vs_currency": "usd", "days": days},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _fetch_coingecko_price(coin_id):
    """GET current price, 24h change, and market cap from CoinGecko."""
    try:
        url = f"{COINGECKO_API}/simple/price"
        resp = requests.get(
            url,
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_market_cap": "true",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def _fetch_fear_greed(limit=30):
    """GET Fear & Greed Index data.
    Returns list of dicts with {value, value_classification, timestamp}.
    """
    try:
        url = f"{FEAR_GREED_API}/"
        resp = requests.get(
            url,
            params={"limit": limit, "format": "json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception:
        return []


def _fetch_funding_rate(symbol):
    """GET funding rate history from Binance Futures.
    Returns list of {fundingRate, fundingTime, symbol}.
    """
    try:
        url = f"{BINANCE_FAPI}/fapi/v1/fundingRate"
        resp = requests.get(
            url,
            params={"symbol": symbol, "limit": 10},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _fetch_tvl(chain):
    """GET historical TVL from DeFiLlama.
    Returns list of {date, tvl}. Returns empty list for None chain (e.g. DOGE).
    """
    if chain is None:
        return []
    try:
        url = f"{DEFILLAMA_API}/v2/historicalChainTvl/{chain}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _fetch_polymarket_markets(query):
    """GET prediction markets from Polymarket Gamma API.
    Returns list of market dicts with question, outcomePrices, volume, slug.
    """
    try:
        url = f"{POLYMARKET_GAMMA_API}/markets"
        resp = requests.get(
            url,
            params={"closed": "false", "limit": 10, "query": query},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Signal computation functions (each returns -100 to +100)
# ═══════════════════════════════════════════════════════════════════════════════


def _compute_rsi_signal(ohlcv):
    """Calculate 14-period RSI from close prices.
    RSI < 30  -> +80 (bullish oversold)
    RSI > 70  -> -80 (bearish overbought)
    Linear interpolation between.
    """
    if not ohlcv or len(ohlcv) < 16:
        return SignalDetail(
            name="RSI (14)",
            value="N/A",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["rsi"],
            weighted_score=0.0,
        )

    closes = [candle[4] for candle in ohlcv]
    period = 14

    # Calculate RSI
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    # Map RSI to signal score: RSI 30 -> +80, RSI 70 -> -80, linear between
    if rsi < 30:
        raw_score = 80.0
    elif rsi > 70:
        raw_score = -80.0
    else:
        # Linear interpolation: rsi=30 -> +80, rsi=50 -> 0, rsi=70 -> -80
        raw_score = 80.0 - (rsi - 30.0) * (160.0 / 40.0)

    if raw_score > 20:
        signal_label = "BULLISH"
    elif raw_score < -20:
        signal_label = "BEARISH"
    else:
        signal_label = "NEUTRAL"

    weight = CRYPTO_SIGNAL_WEIGHTS["rsi"]
    return SignalDetail(
        name="RSI (14)",
        value=f"{rsi:.1f}",
        signal=signal_label,
        raw_score=raw_score,
        weight=weight,
        weighted_score=raw_score * weight,
    )


def _compute_ma_cross_signal(ohlcv):
    """50/200 MA crossover (golden/death cross).
    Falls back to 20/50 if not enough data for 200-period.
    """
    if not ohlcv or len(ohlcv) < 21:
        return SignalDetail(
            name="MA Cross",
            value="N/A",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["ma_cross"],
            weighted_score=0.0,
        )

    closes = [candle[4] for candle in ohlcv]

    if len(closes) >= 200:
        short_period, long_period = 50, 200
    else:
        short_period, long_period = 20, 50

    if len(closes) < long_period:
        short_period, long_period = 20, min(50, len(closes))
        if len(closes) < long_period:
            return SignalDetail(
                name="MA Cross",
                value="N/A",
                signal="NEUTRAL",
                raw_score=0.0,
                weight=CRYPTO_SIGNAL_WEIGHTS["ma_cross"],
                weighted_score=0.0,
            )

    short_ma = sum(closes[-short_period:]) / short_period
    long_ma = sum(closes[-long_period:]) / long_period

    if long_ma == 0:
        raw_score = 0.0
    else:
        # Distance as percentage
        distance_pct = ((short_ma - long_ma) / long_ma) * 100.0
        # Cap at +/- 80, scale: 5% distance -> 80 score
        raw_score = max(-80.0, min(80.0, distance_pct * 16.0))

    label = f"SMA{short_period}/SMA{long_period}"
    if raw_score > 20:
        signal_label = "BULLISH"
    elif raw_score < -20:
        signal_label = "BEARISH"
    else:
        signal_label = "NEUTRAL"

    cross_type = "Golden" if short_ma > long_ma else "Death"
    weight = CRYPTO_SIGNAL_WEIGHTS["ma_cross"]
    return SignalDetail(
        name=f"MA Cross ({label})",
        value=f"{cross_type} ({short_ma:.0f}/{long_ma:.0f})",
        signal=signal_label,
        raw_score=raw_score,
        weight=weight,
        weighted_score=raw_score * weight,
    )


def _compute_macd_signal(ohlcv):
    """MACD = EMA12 - EMA26, Signal = EMA9 of MACD.
    Rising histogram -> bullish, falling -> bearish.
    """
    if not ohlcv or len(ohlcv) < 35:
        return SignalDetail(
            name="MACD",
            value="N/A",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["macd"],
            weighted_score=0.0,
        )

    closes = [candle[4] for candle in ohlcv]

    def _ema(data, period):
        if len(data) < period:
            return data[:]
        multiplier = 2.0 / (period + 1)
        ema_values = [sum(data[:period]) / period]
        for i in range(period, len(data)):
            ema_values.append(
                (data[i] - ema_values[-1]) * multiplier + ema_values[-1]
            )
        return ema_values

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)

    # Align lengths: ema12 starts at index 12, ema26 at index 26
    # So MACD starts at index 26 with length = len(closes) - 26
    offset = 26 - 12  # = 14
    macd_line = []
    for i in range(len(ema26)):
        idx_12 = i + offset
        if idx_12 < len(ema12):
            macd_line.append(ema12[idx_12] - ema26[i])

    if len(macd_line) < 9:
        return SignalDetail(
            name="MACD",
            value="N/A",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["macd"],
            weighted_score=0.0,
        )

    signal_line = _ema(macd_line, 9)

    # Histogram = MACD - Signal
    # Use the last few values to determine trend
    hist_offset = 9  # signal_line starts at index 9 of macd_line
    histogram = []
    for i in range(len(signal_line)):
        idx_macd = i + hist_offset
        if idx_macd < len(macd_line):
            histogram.append(macd_line[idx_macd] - signal_line[i])

    if len(histogram) < 2:
        raw_score = 0.0
    else:
        current_hist = histogram[-1]
        prev_hist = histogram[-2]
        # Rising histogram -> bullish
        hist_delta = current_hist - prev_hist

        # Normalize relative to price level
        price_ref = closes[-1] if closes[-1] != 0 else 1.0
        normalized_delta = (hist_delta / price_ref) * 10000.0
        raw_score = max(-80.0, min(80.0, normalized_delta * 10.0))

    if raw_score > 20:
        signal_label = "BULLISH"
    elif raw_score < -20:
        signal_label = "BEARISH"
    else:
        signal_label = "NEUTRAL"

    weight = CRYPTO_SIGNAL_WEIGHTS["macd"]
    return SignalDetail(
        name="MACD",
        value=f"Hist: {'Rising' if raw_score > 0 else 'Falling'}",
        signal=signal_label,
        raw_score=raw_score,
        weight=weight,
        weighted_score=raw_score * weight,
    )


def _compute_volume_signal(ohlcv):
    """Compare last 7 candles avg volume vs 30-candle avg.
    Volume expansion on green candles -> bullish.
    """
    if not ohlcv or len(ohlcv) < 30:
        return SignalDetail(
            name="Volume",
            value="N/A",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["volume"],
            weighted_score=0.0,
        )

    # OHLC from CoinGecko doesn't have explicit volume; approximate from
    # candle range * (high - low) as a proxy, or use candle body size.
    # Actually CoinGecko OHLC is [timestamp, o, h, l, c] — no volume column.
    # We'll use the candle range (high - low) as a volatility/activity proxy.
    recent_7 = ohlcv[-7:]
    older_30 = ohlcv[-30:]

    def _candle_activity(candle):
        # candle: [timestamp, open, high, low, close]
        return candle[2] - candle[3]  # high - low

    avg_recent = sum(_candle_activity(c) for c in recent_7) / 7.0
    avg_older = sum(_candle_activity(c) for c in older_30) / 30.0

    if avg_older == 0:
        raw_score = 0.0
    else:
        expansion_ratio = avg_recent / avg_older

        # Check if recent candles are green (close > open)
        green_count = sum(1 for c in recent_7 if c[4] > c[1])
        is_bullish_volume = green_count >= 4

        if expansion_ratio > 1.0:
            magnitude = min(80.0, (expansion_ratio - 1.0) * 80.0)
            raw_score = magnitude if is_bullish_volume else -magnitude
        else:
            # Contracting volume — mild neutral/bearish
            raw_score = max(-40.0, (expansion_ratio - 1.0) * 40.0)

    if raw_score > 20:
        signal_label = "BULLISH"
    elif raw_score < -20:
        signal_label = "BEARISH"
    else:
        signal_label = "NEUTRAL"

    weight = CRYPTO_SIGNAL_WEIGHTS["volume"]
    return SignalDetail(
        name="Volume",
        value=f"{'Expanding' if raw_score > 0 else 'Contracting'}",
        signal=signal_label,
        raw_score=raw_score,
        weight=weight,
        weighted_score=raw_score * weight,
    )


def _compute_fear_greed_signal(fg_data):
    """Contrarian indicator from Fear & Greed Index.
    value < 25 (Extreme Fear) -> +80 (buy signal)
    value > 75 (Extreme Greed) -> -80 (sell signal)
    Linear between.
    """
    if not fg_data:
        return SignalDetail(
            name="Fear & Greed",
            value="N/A",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["fear_greed"],
            weighted_score=0.0,
        )

    try:
        current_value = int(fg_data[0].get("value", 50))
        classification = fg_data[0].get("value_classification", "Neutral")
    except (IndexError, ValueError, TypeError):
        current_value = 50
        classification = "Neutral"

    # Contrarian mapping: low fear -> buy, high greed -> sell
    if current_value < 25:
        raw_score = 80.0
    elif current_value > 75:
        raw_score = -80.0
    else:
        # Linear: 25 -> +80, 50 -> 0, 75 -> -80
        raw_score = 80.0 - (current_value - 25.0) * (160.0 / 50.0)

    if raw_score > 20:
        signal_label = "BULLISH"
    elif raw_score < -20:
        signal_label = "BEARISH"
    else:
        signal_label = "NEUTRAL"

    weight = CRYPTO_SIGNAL_WEIGHTS["fear_greed"]
    return SignalDetail(
        name="Fear & Greed",
        value=f"{current_value} ({classification})",
        signal=signal_label,
        raw_score=raw_score,
        weight=weight,
        weighted_score=raw_score * weight,
    )


def _compute_funding_signal(funding_data):
    """Contrarian funding rate signal.
    Positive funding (longs paying) -> bearish.
    Negative funding -> bullish.
    Extreme positive (>0.01%) -> -80. Extreme negative -> +80.
    """
    if not funding_data:
        return SignalDetail(
            name="Funding Rate",
            value="N/A",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["funding_rate"],
            weighted_score=0.0,
        )

    try:
        # Average recent funding rates
        rates = [float(entry.get("fundingRate", 0)) for entry in funding_data]
        avg_rate = sum(rates) / len(rates) if rates else 0.0
    except (ValueError, TypeError):
        avg_rate = 0.0

    # Convert to percentage for display
    rate_pct = avg_rate * 100.0

    # Contrarian: positive funding -> bearish, negative -> bullish
    # 0.01% -> -80, -0.01% -> +80, linear scale
    if avg_rate == 0:
        raw_score = 0.0
    else:
        # Scale: 0.0001 (0.01%) maps to -80
        raw_score = max(-80.0, min(80.0, -avg_rate * 800000.0))

    if raw_score > 20:
        signal_label = "BULLISH"
    elif raw_score < -20:
        signal_label = "BEARISH"
    else:
        signal_label = "NEUTRAL"

    weight = CRYPTO_SIGNAL_WEIGHTS["funding_rate"]
    return SignalDetail(
        name="Funding Rate",
        value=f"{rate_pct:.4f}%",
        signal=signal_label,
        raw_score=raw_score,
        weight=weight,
        weighted_score=raw_score * weight,
    )


def _compute_tvl_signal(tvl_data):
    """Compare recent 7-day TVL vs 30-day avg.
    Growing > 5% -> bullish. Declining > 5% -> bearish.
    Returns 0 if no data (DOGE has no TVL).
    """
    if not tvl_data or len(tvl_data) < 30:
        return SignalDetail(
            name="TVL Trend",
            value="N/A",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["tvl"],
            weighted_score=0.0,
        )

    try:
        recent_7 = tvl_data[-7:]
        older_30 = tvl_data[-30:]

        avg_recent = sum(entry.get("tvl", 0) for entry in recent_7) / 7.0
        avg_30 = sum(entry.get("tvl", 0) for entry in older_30) / 30.0

        if avg_30 == 0:
            raw_score = 0.0
        else:
            change_pct = ((avg_recent - avg_30) / avg_30) * 100.0

            if change_pct > 5:
                raw_score = min(80.0, change_pct * 8.0)
            elif change_pct < -5:
                raw_score = max(-80.0, change_pct * 8.0)
            else:
                # Within +/-5% -> small signal
                raw_score = change_pct * 4.0
    except (TypeError, ZeroDivisionError):
        raw_score = 0.0
        change_pct = 0.0

    if raw_score > 20:
        signal_label = "BULLISH"
    elif raw_score < -20:
        signal_label = "BEARISH"
    else:
        signal_label = "NEUTRAL"

    weight = CRYPTO_SIGNAL_WEIGHTS["tvl"]
    try:
        value_str = f"{change_pct:+.1f}% (7d vs 30d)"
    except UnboundLocalError:
        value_str = "N/A"

    return SignalDetail(
        name="TVL Trend",
        value=value_str,
        signal=signal_label,
        raw_score=raw_score,
        weight=weight,
        weighted_score=raw_score * weight,
    )


def _compute_polymarket_signal(model_prob, market_prob):
    """Edge = model_prob - market_prob.
    Large positive edge -> strong signal.
    No market found -> return neutral SignalDetail with score 0.
    """
    if market_prob is None or market_prob == 0:
        return SignalDetail(
            name="Polymarket Edge",
            value="No market found",
            signal="NEUTRAL",
            raw_score=0.0,
            weight=CRYPTO_SIGNAL_WEIGHTS["polymarket"],
            weighted_score=0.0,
        )

    edge = model_prob - market_prob
    edge_pct = edge * 100.0

    # Scale: 20% edge -> 80 score
    raw_score = max(-80.0, min(80.0, edge_pct * 4.0))

    if raw_score > 20:
        signal_label = "BULLISH"
    elif raw_score < -20:
        signal_label = "BEARISH"
    else:
        signal_label = "NEUTRAL"

    weight = CRYPTO_SIGNAL_WEIGHTS["polymarket"]
    return SignalDetail(
        name="Polymarket Edge",
        value=f"Model: {model_prob:.0%} vs Market: {market_prob:.0%}",
        signal=signal_label,
        raw_score=raw_score,
        weight=weight,
        weighted_score=raw_score * weight,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SignalDetail:
    name: str = ""
    value: str = ""
    signal: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    raw_score: float = 0.0
    weight: float = 0.0
    weighted_score: float = 0.0


@dataclass
class PredictionMarketEdge:
    market_question: str = ""
    market_odds: float = 0.0
    model_implied: float = 0.0
    edge_pct: float = 0.0
    play: str = ""
    market_url: str = ""


@dataclass
class CryptoPrediction:
    asset: str = ""
    composite_score: float = 0.0
    direction: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    confidence: str = "LOW"  # HIGH, MEDIUM, LOW
    signals: list = None  # list of SignalDetail
    prediction_market_edge: PredictionMarketEdge = None
    suggested_play: str = ""
    updated_at: str = ""
    is_stale: bool = False

    def __post_init__(self):
        if self.signals is None:
            self.signals = []
        if self.prediction_market_edge is None:
            self.prediction_market_edge = PredictionMarketEdge()


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════


def _score_to_probability(score):
    """Maps -100..+100 to 0..1 via sigmoid: 1 / (1 + exp(-score / 40))."""
    return 1.0 / (1.0 + math.exp(-score / 40.0))


def _generate_play_text(asset, score, direction, edge):
    """Generates human-readable suggested play text.
    Returns 'NO PLAY' if edge is too small.
    """
    if edge is None or abs(edge.edge_pct) < 10:
        prob = _score_to_probability(score)
        return (
            f"{asset}: {direction} (composite {score:+.1f}, "
            f"implied prob {prob:.0%}). No actionable Polymarket edge found. "
            f"NO PLAY."
        )

    side = "YES" if edge.edge_pct > 0 else "NO"
    return (
        f"{asset}: {direction} (composite {score:+.1f}). "
        f"Polymarket edge: {edge.edge_pct:+.1f}% on "
        f"\"{edge.market_question}\". "
        f"Suggested: {side} at {edge.market_odds:.0%} "
        f"(model implies {edge.model_implied:.0%})."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Main prediction functions
# ═══════════════════════════════════════════════════════════════════════════════


def _predict_single_asset(asset, config):
    """Predict a single crypto asset by fetching data in parallel and
    computing all signals.

    Parameters
    ----------
    asset : str
        Ticker symbol, e.g. "BTC".
    config : dict
        Asset config from CRYPTO_ASSETS, e.g.
        {"coingecko_id": "bitcoin", "binance_symbol": "BTCUSDT", "chain": "Bitcoin"}.

    Returns
    -------
    CryptoPrediction
    """
    coin_id = config["coingecko_id"]
    binance_symbol = config["binance_symbol"]
    chain = config.get("chain")

    # Fetch all data sources in parallel
    futures = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures["ohlcv"] = executor.submit(_fetch_coingecko_ohlc, coin_id, 90)
        futures["price"] = executor.submit(_fetch_coingecko_price, coin_id)
        futures["fear_greed"] = executor.submit(_fetch_fear_greed, 30)
        futures["funding"] = executor.submit(_fetch_funding_rate, binance_symbol)
        futures["tvl"] = executor.submit(_fetch_tvl, chain)
        futures["polymarket"] = executor.submit(
            _fetch_polymarket_markets, f"{asset} crypto price"
        )

    # Collect results
    results = {}
    for key, future in futures.items():
        try:
            results[key] = future.result(timeout=30)
        except Exception:
            results[key] = [] if key != "price" else {}

    ohlcv = results["ohlcv"]
    fg_data = results["fear_greed"]
    funding_data = results["funding"]
    tvl_data = results["tvl"]
    polymarket_markets = results["polymarket"]

    # Compute individual signals
    signals = []
    signals.append(_compute_rsi_signal(ohlcv))
    signals.append(_compute_ma_cross_signal(ohlcv))
    signals.append(_compute_macd_signal(ohlcv))
    signals.append(_compute_volume_signal(ohlcv))
    signals.append(_compute_fear_greed_signal(fg_data))
    signals.append(_compute_funding_signal(funding_data))
    signals.append(_compute_tvl_signal(tvl_data))

    # Composite score (without polymarket, added after)
    composite = sum(s.weighted_score for s in signals)

    # Convert composite to probability via sigmoid
    model_prob = _score_to_probability(composite)

    # Parse Polymarket odds
    market_prob = None
    best_market = None
    if polymarket_markets and isinstance(polymarket_markets, list):
        for market in polymarket_markets:
            try:
                outcome_prices = json.loads(
                    market.get("outcomePrices", "[]")
                )
                if outcome_prices and len(outcome_prices) >= 1:
                    yes_price = float(outcome_prices[0])
                    if 0.01 < yes_price < 0.99:
                        market_prob = yes_price
                        best_market = market
                        break
            except (json.JSONDecodeError, ValueError, TypeError, IndexError):
                continue

    # Compute polymarket signal and add to signals list
    poly_signal = _compute_polymarket_signal(model_prob, market_prob)
    signals.append(poly_signal)

    # Recalculate composite with polymarket signal included
    composite = sum(s.weighted_score for s in signals)

    # Clamp to -100..+100
    composite = max(-100.0, min(100.0, composite))

    # Direction
    if composite > 20:
        direction = "BULLISH"
    elif composite < -20:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    # Confidence
    abs_score = abs(composite)
    if abs_score > 60:
        confidence = "HIGH"
    elif abs_score > 30:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Build prediction market edge
    edge = PredictionMarketEdge()
    if best_market and market_prob is not None:
        edge_pct = (model_prob - market_prob) * 100.0
        edge = PredictionMarketEdge(
            market_question=best_market.get("question", ""),
            market_odds=market_prob,
            model_implied=model_prob,
            edge_pct=edge_pct,
            play="YES" if edge_pct > 0 else "NO",
            market_url=f"https://polymarket.com/event/{best_market.get('slug', '')}",
        )

    # Suggested play text
    suggested_play = _generate_play_text(asset, composite, direction, edge)

    return CryptoPrediction(
        asset=asset,
        composite_score=round(composite, 2),
        direction=direction,
        confidence=confidence,
        signals=signals,
        prediction_market_edge=edge,
        suggested_play=suggested_play,
        updated_at=datetime.now(timezone.utc).isoformat(),
        is_stale=False,
    )


def get_all_predictions():
    """Generate predictions for all configured crypto assets.

    Returns
    -------
    list[CryptoPrediction]
        One prediction per asset (BTC, ETH, SOL, DOGE).
    """
    predictions = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for asset, config in CRYPTO_ASSETS.items():
        try:
            prediction = _predict_single_asset(asset, config)
            prediction.updated_at = timestamp
            predictions.append(prediction)
        except Exception:
            # Return a default prediction on failure
            predictions.append(
                CryptoPrediction(
                    asset=asset,
                    composite_score=0.0,
                    direction="NEUTRAL",
                    confidence="LOW",
                    signals=[],
                    prediction_market_edge=PredictionMarketEdge(),
                    suggested_play=f"{asset}: Unable to generate prediction.",
                    updated_at=timestamp,
                    is_stale=True,
                )
            )

    return predictions


# ═══════════════════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════════════════


def log_prediction(prediction):
    """Append a CryptoPrediction to the predictions log file.

    Parameters
    ----------
    prediction : CryptoPrediction
        The prediction to log.
    """
    entry = {
        "asset": prediction.asset,
        "composite_score": prediction.composite_score,
        "direction": prediction.direction,
        "confidence": prediction.confidence,
        "timestamp": prediction.updated_at,
        "signals_summary": [
            {
                "name": s.name,
                "value": s.value,
                "signal": s.signal,
                "raw_score": s.raw_score,
            }
            for s in prediction.signals
        ],
        "suggested_play": prediction.suggested_play,
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
    """Load prediction history from the log file.

    Parameters
    ----------
    asset : str, optional
        If provided, filter to only this asset's predictions.

    Returns
    -------
    list
        List of prediction log entries.
    """
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
        history = [entry for entry in history if entry.get("asset") == asset]

    return history
