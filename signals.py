import logging
from dataclasses import dataclass

import requests

from config import (
    CHAIN,
    BUY_CONFIDENCE_THRESHOLD,
    MIN_PRICE_CHANGE_5M,
    MIN_PRICE_CHANGE_1H,
    MIN_VOLUME_1H_USD,
    MIN_LIQUIDITY_USD,
)

logger = logging.getLogger(__name__)

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/dex/tokens/{}"


@dataclass
class Signal:
    coin: str
    address: str
    chain: str
    signal_type: str  # 'buy now' | 'sell' | 'hold'
    price: float
    confidence: float
    notes: str


def _fetch_top_boosted_tokens(chain: str) -> list[dict]:
    resp = requests.get(DEXSCREENER_BOOSTS_URL, timeout=15)
    resp.raise_for_status()
    tokens = resp.json()
    return [t for t in tokens if t.get("chainId") == chain][:25]


def _fetch_best_pair(address: str) -> dict | None:
    url = DEXSCREENER_TOKENS_URL.format(address)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("DexScreener request failed for %s: %s", address, e)
        return None

    pairs = resp.json().get("pairs") or []
    if not pairs:
        return None
    return max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)


def _compute_signal(pair: dict) -> tuple[str, float, str]:
    price_change = pair.get("priceChange") or {}
    p5m = float(price_change.get("m5") or 0)
    p1h = float(price_change.get("h1") or 0)
    p24h = float(price_change.get("h24") or 0)

    volume = pair.get("volume") or {}
    vol_1h = float(volume.get("h1") or 0)

    liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)

    score = 0.0
    notes = []

    if p5m >= MIN_PRICE_CHANGE_5M:
        score += 0.20
        notes.append(f"5m +{p5m:.1f}%")
    if p1h >= MIN_PRICE_CHANGE_1H:
        score += 0.30
        notes.append(f"1h +{p1h:.1f}%")
    if vol_1h >= MIN_VOLUME_1H_USD:
        score += 0.25
        notes.append(f"vol ${vol_1h/1000:.0f}k")
    if liquidity >= MIN_LIQUIDITY_USD:
        score += 0.15
        notes.append(f"liq ${liquidity/1000:.0f}k")
    if p24h >= 20:
        score += 0.10
        notes.append(f"24h +{p24h:.1f}%")

    # Penalties
    if p24h <= -50:
        score -= 0.40
        notes.append(f"24h {p24h:.1f}%")
    if liquidity < MIN_LIQUIDITY_USD:
        score -= 0.30
        notes.append("low liq")

    score = round(max(0.0, min(1.0, score)), 2)

    if score >= BUY_CONFIDENCE_THRESHOLD:
        signal_type = "buy now"
    elif score <= 0.20 and p1h <= -10:
        signal_type = "sell"
    else:
        signal_type = "hold"

    return signal_type, score, "; ".join(notes) or "no notable factors"


def get_signals(chain: str = CHAIN) -> list[Signal]:
    try:
        tokens = _fetch_top_boosted_tokens(chain)
    except requests.RequestException as e:
        logger.error("Failed to fetch boosted tokens: %s", e)
        return []

    signals: list[Signal] = []
    for token in tokens:
        address = token.get("tokenAddress", "")
        pair = _fetch_best_pair(address)
        if not pair:
            continue

        symbol = (pair.get("baseToken") or {}).get("symbol") or address[:8]
        price = float(pair.get("priceUsd") or 0)
        signal_type, confidence, notes = _compute_signal(pair)

        signals.append(
            Signal(
                coin=symbol,
                address=address,
                chain=chain,
                signal_type=signal_type,
                price=price,
                confidence=confidence,
                notes=notes,
            )
        )
        logger.debug("%s -> %s (%.0f%%)", symbol, signal_type, confidence * 100)

    return signals
