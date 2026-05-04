"""
Buy/sell signal logic for memecoins using DexScreener's free public API.

Signal criteria for 'buy now':
  - 24h volume >= $50k
  - Liquidity (USD) >= $10k
  - 1h price change >= +5%
  - 24h price change >= +10%
  - Token age >= 1 hour (filters brand-new unvetted launches)

Supports Solana by default; tweak CHAINS to add others.
"""

import time
from dataclasses import dataclass
from typing import Optional

import requests

CHAINS = ["solana"]
DEXSCREENER_BOOSTED_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
DEXSCREENER_PAIRS_URL    = "https://api.dexscreener.com/latest/dex/tokens/{address}"

# --- thresholds -----------------------------------------------------------
MIN_VOLUME_24H    = 50_000      # USD
MIN_LIQUIDITY_USD = 10_000      # USD
MIN_PRICE_CHG_1H  = 5.0         # %
MIN_PRICE_CHG_24H = 10.0        # %
MIN_AGE_HOURS     = 1           # hours since first trade


@dataclass
class SignalResult:
    token:           str
    token_address:   str
    chain:           str
    signal:          str           # 'buy now' | 'hold' | 'sell'
    price_usd:       float
    price_change_1h: float
    volume_24h:      float
    liquidity_usd:   float
    dexscreener_url: str


def _get_boosted_tokens() -> list[dict]:
    try:
        r = requests.get(DEXSCREENER_BOOSTED_URL, timeout=10)
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []


def _get_pair_data(token_address: str) -> Optional[dict]:
    url = DEXSCREENER_PAIRS_URL.format(address=token_address)
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        pairs = r.json().get("pairs") or []
        # prefer the pair with the highest liquidity
        pairs = [p for p in pairs if p.get("chainId") in CHAINS]
        if not pairs:
            return None
        return max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
    except Exception:
        return None


def _pair_age_hours(pair: dict) -> float:
    created_at = pair.get("pairCreatedAt")
    if not created_at:
        return float("inf")
    age_ms = time.time() * 1000 - float(created_at)
    return age_ms / (1000 * 3600)


def _score_pair(pair: dict) -> Optional[SignalResult]:
    try:
        volume_24h    = float(pair.get("volume",    {}).get("h24",  0) or 0)
        liquidity_usd = float(pair.get("liquidity", {}).get("usd",  0) or 0)
        price_chg_1h  = float(pair.get("priceChange", {}).get("h1",  0) or 0)
        price_chg_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
        price_usd     = float(pair.get("priceUsd", 0) or 0)
        age_hours     = _pair_age_hours(pair)

        if (
            volume_24h    >= MIN_VOLUME_24H    and
            liquidity_usd >= MIN_LIQUIDITY_USD and
            price_chg_1h  >= MIN_PRICE_CHG_1H  and
            price_chg_24h >= MIN_PRICE_CHG_24H and
            age_hours     >= MIN_AGE_HOURS
        ):
            signal = "buy now"
        else:
            signal = "hold"

        base_token = pair.get("baseToken", {})
        return SignalResult(
            token           = base_token.get("symbol", "UNKNOWN"),
            token_address   = base_token.get("address", ""),
            chain           = pair.get("chainId", ""),
            signal          = signal,
            price_usd       = price_usd,
            price_change_1h = price_chg_1h,
            volume_24h      = volume_24h,
            liquidity_usd   = liquidity_usd,
            dexscreener_url = pair.get("url", ""),
        )
    except (TypeError, ValueError):
        return None


def get_signals(limit: int = 50) -> list[SignalResult]:
    """Return signal results for the top boosted tokens on supported chains."""
    boosted = _get_boosted_tokens()
    seen_addresses: set[str] = set()
    results: list[SignalResult] = []

    for entry in boosted[:limit]:
        address = entry.get("tokenAddress", "")
        chain   = entry.get("chainId", "")
        if not address or chain not in CHAINS or address in seen_addresses:
            continue
        seen_addresses.add(address)

        pair = _get_pair_data(address)
        if not pair:
            continue

        result = _score_pair(pair)
        if result:
            results.append(result)

    return results


def get_buy_now_signals(limit: int = 50) -> list[SignalResult]:
    """Convenience wrapper — only 'buy now' signals."""
    return [s for s in get_signals(limit) if s.signal == "buy now"]
