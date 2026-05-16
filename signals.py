"""Fetch trending token profiles from DexScreener and generate buy/sell signals."""

import time
import requests
from dataclasses import dataclass, field

from config import (
    MAX_PROFILES,
    MIN_LIQUIDITY_USD,
    MIN_PRICE_CHANGE_24H,
    MIN_VOLUME_24H_USD,
)

_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
_PAIRS_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"


@dataclass
class TokenSignal:
    signal_name: str
    coin_symbol: str
    chain: str
    dex: str
    pair_address: str
    price_usd: float
    price_change_24h: float
    volume_24h_usd: float
    liquidity_usd: float
    signal: str          # "Buy Now" | "Hold" | "Sell"
    notes: str = field(default="")


def _best_pair(pairs: list[dict]) -> dict | None:
    """Return the pair with the highest liquidity."""
    valid = [p for p in pairs if (p.get("liquidity") or {}).get("usd")]
    return max(valid, key=lambda p: p["liquidity"]["usd"], default=None)


def _evaluate(price_change: float, volume: float, liquidity: float) -> tuple[str, str]:
    """Return (signal_label, human-readable notes)."""
    if (
        price_change >= MIN_PRICE_CHANGE_24H
        and volume >= MIN_VOLUME_24H_USD
        and liquidity >= MIN_LIQUIDITY_USD
    ):
        notes = (
            f"+{price_change:.1f}% 24h | "
            f"vol ${volume:,.0f} | "
            f"liq ${liquidity:,.0f}"
        )
        return "Buy Now", notes

    if price_change <= -20:
        return "Sell", f"{price_change:.1f}% 24h drop"

    parts = []
    if price_change > 0:
        parts.append(f"+{price_change:.1f}% 24h")
    if volume:
        parts.append(f"vol ${volume:,.0f}")
    return "Hold", " | ".join(parts) if parts else "below threshold"


def scan_signals() -> list[TokenSignal]:
    """Scan the latest trending token profiles and return all generated signals."""
    try:
        resp = requests.get(_PROFILES_URL, timeout=30)
        resp.raise_for_status()
        profiles: list[dict] = resp.json()
    except Exception as exc:
        print(f"[signals] Could not fetch profiles: {exc}")
        return []

    results: list[TokenSignal] = []
    seen: set[str] = set()

    for profile in profiles[:MAX_PROFILES]:
        chain = profile.get("chainId", "")
        address = profile.get("tokenAddress", "")
        if not address or address in seen:
            continue
        seen.add(address)

        try:
            pairs_resp = requests.get(
                _PAIRS_URL.format(address=address), timeout=15
            )
            pairs_resp.raise_for_status()
            pairs: list[dict] = pairs_resp.json().get("pairs") or []
        except Exception:
            continue

        pair = _best_pair(pairs)
        if not pair:
            continue

        price_change = float((pair.get("priceChange") or {}).get("h24", 0) or 0)
        volume = float((pair.get("volume") or {}).get("h24", 0) or 0)
        liquidity = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
        price_usd = float(pair.get("priceUsd") or 0)
        symbol = (pair.get("baseToken") or {}).get("symbol", address[:8])
        dex = pair.get("dexId", "unknown")
        pair_address = pair.get("pairAddress", "")

        signal, notes = _evaluate(price_change, volume, liquidity)

        results.append(
            TokenSignal(
                signal_name=f"{symbol} — {signal}",
                coin_symbol=symbol,
                chain=chain,
                dex=dex,
                pair_address=pair_address,
                price_usd=price_usd,
                price_change_24h=price_change,
                volume_24h_usd=volume,
                liquidity_usd=liquidity,
                signal=signal,
                notes=notes,
            )
        )

        time.sleep(0.15)  # stay well under DexScreener's rate limit

    return results
