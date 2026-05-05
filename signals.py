"""
Buy/sell signal logic using DexScreener public API.

Scoring (0-100):
  Volume 24h > $500k   → +30
  Volume 24h > $100k   → +15
  1h price change > 10% → +25
  1h price change > 5%  → +15
  6h price change > 20% → +20
  24h price change > 0%  → +10

Signal:
  score >= 60  → 'buy now'
  score >= 30  → 'watch'
  else         → 'hold'
"""

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from config import MIN_LIQUIDITY_USD, MIN_VOLUME_24H_USD, BUY_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

DEXSCREENER_PROFILES = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens/{}"
DEXSCREENER_BOOSTED = "https://api.dexscreener.com/token-boosts/active/v1"


@dataclass
class Signal:
    coin: str
    token_address: str
    signal: str          # 'buy now' | 'watch' | 'hold'
    confidence: float    # 0-100
    price: float
    volume_24h: float
    liquidity_usd: float
    notes: str


def _best_pair(pairs: list[dict]) -> Optional[dict]:
    """Return the most liquid pair from a list."""
    solana = [p for p in pairs if p.get("chainId") == "solana"]
    pool = solana or pairs
    if not pool:
        return None
    return max(pool, key=lambda p: float(p.get("liquidity", {}).get("usd") or 0))


def _score_pair(pair: dict) -> tuple[float, list[str]]:
    """Score a pair 0-100 and return (score, reason_list)."""
    score = 0.0
    reasons: list[str] = []

    volume_24h = float(pair.get("volume", {}).get("h24") or 0)
    liq = float(pair.get("liquidity", {}).get("usd") or 0)
    ch1h = float(pair.get("priceChange", {}).get("h1") or 0)
    ch6h = float(pair.get("priceChange", {}).get("h6") or 0)
    ch24h = float(pair.get("priceChange", {}).get("h24") or 0)

    if liq < MIN_LIQUIDITY_USD:
        return 0.0, []

    if volume_24h >= 500_000:
        score += 30
        reasons.append(f"High 24h vol: ${volume_24h:,.0f}")
    elif volume_24h >= MIN_VOLUME_24H_USD:
        score += 15
        reasons.append(f"Good 24h vol: ${volume_24h:,.0f}")
    else:
        return 0.0, []     # too low volume

    if ch1h >= 10:
        score += 25
        reasons.append(f"1h +{ch1h:.1f}%")
    elif ch1h >= 5:
        score += 15
        reasons.append(f"1h +{ch1h:.1f}%")

    if ch6h >= 20:
        score += 20
        reasons.append(f"6h +{ch6h:.1f}%")

    if ch24h > 0:
        score += 10
        reasons.append(f"24h +{ch24h:.1f}%")

    return min(score, 100.0), reasons


def _evaluate_address(address: str) -> Optional[Signal]:
    try:
        resp = requests.get(DEXSCREENER_TOKEN.format(address), timeout=10)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
    except Exception as exc:
        logger.warning("DexScreener fetch failed for %s: %s", address, exc)
        return None

    pair = _best_pair(pairs)
    if not pair:
        return None

    score, reasons = _score_pair(pair)
    if score == 0:
        return None

    if score >= BUY_CONFIDENCE_THRESHOLD:
        signal_type = "buy now"
    elif score >= 30:
        signal_type = "watch"
    else:
        signal_type = "hold"

    return Signal(
        coin=pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
        token_address=address,
        signal=signal_type,
        confidence=score,
        price=float(pair.get("priceUsd") or 0),
        volume_24h=float(pair.get("volume", {}).get("h24") or 0),
        liquidity_usd=float(pair.get("liquidity", {}).get("usd") or 0),
        notes="; ".join(reasons),
    )


def _trending_addresses() -> list[str]:
    """Fetch the latest trending Solana token addresses from DexScreener."""
    addresses: list[str] = []
    for url in (DEXSCREENER_PROFILES, DEXSCREENER_BOOSTED):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                addresses += [
                    t["tokenAddress"]
                    for t in data
                    if t.get("chainId") == "solana" and t.get("tokenAddress")
                ]
        except Exception as exc:
            logger.warning("Trending fetch from %s failed: %s", url, exc)
    # deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for a in addresses:
        if a not in seen:
            seen.add(a)
            unique.append(a)
    return unique[:40]  # cap to avoid rate-limiting


def get_signals(watch_tokens: list[str] | None = None) -> list[Signal]:
    """
    Return all signals for the given token list (or trending tokens if empty).
    Only 'buy now' and 'watch' signals are returned (holds are filtered out).
    """
    addresses = watch_tokens if watch_tokens else _trending_addresses()
    if not addresses:
        logger.warning("No token addresses to evaluate.")
        return []

    signals: list[Signal] = []
    for addr in addresses:
        sig = _evaluate_address(addr)
        if sig and sig.signal != "hold":
            signals.append(sig)
            logger.info("[%s] %s – confidence %.0f", sig.signal.upper(), sig.coin, sig.confidence)

    signals.sort(key=lambda s: s.confidence, reverse=True)
    return signals
