import requests
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import config


@dataclass
class Signal:
    token_name: str
    token_address: str
    signal_type: str          # 'buy now'
    signal_strength: str      # 'Strong' | 'Moderate' | 'Weak'
    price_usd: float
    price_change_24h: float   # percent
    volume_24h: float
    chain: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


def _get(url: str) -> dict:
    resp = requests.get(url, timeout=15, headers={"User-Agent": "memecoin-intel/1.0"})
    resp.raise_for_status()
    return resp.json()


def _fetch_top_boosted() -> list[dict]:
    """Return top boosted token addresses from DexScreener."""
    data = _get("https://api.dexscreener.com/token-boosts/top/v1")
    # API returns a list directly
    return data if isinstance(data, list) else []


def _fetch_pairs(token_address: str) -> list[dict]:
    data = _get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}")
    return data.get("pairs") or []


def _evaluate(pair: dict) -> Optional[Signal]:
    """Return a Signal if pair meets buy criteria, else None."""
    volume_24h = float((pair.get("volume") or {}).get("h24") or 0)
    price_change_24h = float((pair.get("priceChange") or {}).get("h24") or 0)
    liquidity_usd = float((pair.get("liquidity") or {}).get("usd") or 0)
    price_usd = float(pair.get("priceUsd") or 0)

    if (
        volume_24h < config.BUY_SIGNAL_MIN_VOLUME_USD
        or price_change_24h < config.BUY_SIGNAL_MIN_PRICE_CHANGE_PCT
        or liquidity_usd < config.BUY_SIGNAL_MIN_LIQUIDITY_USD
    ):
        return None

    if price_change_24h >= 20 and volume_24h >= 500_000:
        strength = "Strong"
    elif price_change_24h >= 10 and volume_24h >= 200_000:
        strength = "Moderate"
    else:
        strength = "Weak"

    base = pair.get("baseToken") or {}
    return Signal(
        token_name=base.get("symbol", "UNKNOWN"),
        token_address=base.get("address", ""),
        signal_type="buy now",
        signal_strength=strength,
        price_usd=price_usd,
        price_change_24h=price_change_24h,
        volume_24h=volume_24h,
        chain=pair.get("chainId", "unknown"),
        notes=f"DEX: {pair.get('dexId','')} | Pair: {pair.get('pairAddress','')}",
    )


def run_signals(top_n: int = 30) -> list[Signal]:
    """Fetch top boosted tokens, evaluate, and return all buy-now signals."""
    buy_signals: list[Signal] = []
    seen: set[str] = set()

    try:
        boosted = _fetch_top_boosted()
    except Exception as exc:
        print(f"[signals] Failed to fetch trending tokens: {exc}")
        return buy_signals

    for item in boosted[:top_n]:
        addr = item.get("tokenAddress", "")
        if not addr or addr in seen:
            continue
        seen.add(addr)

        try:
            pairs = _fetch_pairs(addr)
        except Exception as exc:
            print(f"[signals] Skipping {addr}: {exc}")
            continue

        if not pairs:
            continue

        # Pick pair with highest USD liquidity
        best = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
        signal = _evaluate(best)
        if signal:
            buy_signals.append(signal)

    return buy_signals
