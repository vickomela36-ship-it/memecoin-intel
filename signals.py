"""Buy/sell signal logic using DEXScreener public API (no key required)."""

import requests
from dataclasses import dataclass
from datetime import datetime

_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
_PAIRS_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"

# Minimum thresholds for a valid signal
_MIN_PRICE_CHANGE_PCT = 20.0
_MIN_VOLUME_24H = 100_000
_MIN_LIQUIDITY = 50_000

# Strong signal thresholds
_STRONG_PRICE_CHANGE = 50.0
_STRONG_VOLUME = 500_000
_STRONG_LIQUIDITY = 100_000


@dataclass
class Signal:
    token: str
    address: str
    chain: str
    price_usd: float
    price_change_24h: float
    volume_24h: float
    liquidity_usd: float
    signal_strength: str  # "Strong" | "Moderate" | "Weak"
    verdict: str          # "buy now" | "hold"
    notes: str
    timestamp: datetime


def _classify_strength(price_change: float, volume: float, liquidity: float) -> str:
    if (
        price_change >= _STRONG_PRICE_CHANGE
        and volume >= _STRONG_VOLUME
        and liquidity >= _STRONG_LIQUIDITY
    ):
        return "Strong"
    if (
        price_change >= 30
        and volume >= 200_000
        and liquidity >= _MIN_LIQUIDITY
    ):
        return "Moderate"
    return "Weak"


def _fetch_trending_addresses(chain: str = "solana", limit: int = 30) -> list[str]:
    resp = requests.get(_BOOSTS_URL, timeout=15)
    resp.raise_for_status()
    tokens = resp.json()
    seen: set[str] = set()
    addresses = []
    for t in tokens:
        if t.get("chainId") != chain:
            continue
        addr = t.get("tokenAddress", "")
        if addr and addr not in seen:
            seen.add(addr)
            addresses.append(addr)
        if len(addresses) >= limit:
            break
    return addresses


def _analyze_address(address: str) -> list[Signal]:
    resp = requests.get(_PAIRS_URL.format(address=address), timeout=15)
    resp.raise_for_status()
    pairs = resp.json().get("pairs") or []
    if not pairs:
        return []

    # Use the pair with the highest liquidity
    pairs.sort(key=lambda p: (p.get("liquidity") or {}).get("usd") or 0, reverse=True)
    pair = pairs[0]

    price_change = float((pair.get("priceChange") or {}).get("h24") or 0)
    volume_24h = float((pair.get("volume") or {}).get("h24") or 0)
    liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)
    price_usd = float(pair.get("priceUsd") or 0)

    if (
        price_change < _MIN_PRICE_CHANGE_PCT
        or volume_24h < _MIN_VOLUME_24H
        or liquidity < _MIN_LIQUIDITY
    ):
        return []

    strength = _classify_strength(price_change, volume_24h, liquidity)
    verdict = "buy now"

    note_parts: list[str] = []
    if price_change > 100:
        note_parts.append(f"Moonshot +{price_change:.0f}% in 24h")
    if volume_24h > liquidity * 3:
        note_parts.append("Extreme vol/liq ratio")
    elif volume_24h > liquidity:
        note_parts.append("High vol/liq ratio")
    fdv = float(pair.get("fdv") or 0)
    if fdv and fdv < 1_000_000:
        note_parts.append("Micro-cap <$1M FDV")

    return [
        Signal(
            token=(pair.get("baseToken") or {}).get("symbol") or "?",
            address=address,
            chain=pair.get("chainId") or "solana",
            price_usd=price_usd,
            price_change_24h=price_change,
            volume_24h=volume_24h,
            liquidity_usd=liquidity,
            signal_strength=strength,
            verdict=verdict,
            notes=" | ".join(note_parts),
            timestamp=datetime.utcnow(),
        )
    ]


def run_scan(chain: str = "solana") -> list[Signal]:
    """Return all 'buy now' signals from today's top trending tokens."""
    addresses = _fetch_trending_addresses(chain=chain)
    buy_signals: list[Signal] = []
    for addr in addresses:
        try:
            buy_signals.extend(
                s for s in _analyze_address(addr) if s.verdict == "buy now"
            )
        except Exception as exc:
            print(f"  [warn] Could not analyze {addr}: {exc}")
    return buy_signals
