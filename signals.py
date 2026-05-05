"""Buy/sell signal logic for Solana memecoins using DexScreener."""

import requests
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

import config


@dataclass
class Signal:
    coin: str
    symbol: str
    address: str
    signal: str          # 'buy now' | 'sell' | 'watch' | 'hold'
    price_usd: float
    price_change_1h: float
    price_change_6h: float
    price_change_24h: float
    volume_24h: float
    liquidity_usd: float
    fdv: Optional[float]
    reason: str
    timestamp: str


def get_signals() -> list[Signal]:
    """Return signals for the top trending Solana memecoins."""
    try:
        resp = requests.get(
            f"{config.DEXSCREENER_BASE}/token-profiles/latest/v1",
            timeout=15,
        )
        resp.raise_for_status()
        profiles = resp.json()

        # Filter to Solana tokens and get their addresses
        solana_addresses = [
            p["tokenAddress"]
            for p in profiles
            if p.get("chainId") == config.SOLANA_CHAIN
        ][:30]
    except Exception:
        return []

    if not solana_addresses:
        return []

    try:
        # Batch-fetch pair data for up to 30 tokens
        addr_str = ",".join(solana_addresses)
        resp = requests.get(
            f"{config.DEXSCREENER_BASE}/latest/dex/tokens/{addr_str}",
            timeout=15,
        )
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
    except Exception:
        return []

    seen: set[str] = set()
    signals: list[Signal] = []

    for pair in pairs:
        if pair.get("chainId") != config.SOLANA_CHAIN:
            continue

        base = pair.get("baseToken", {})
        address = base.get("address", "")
        if address in seen:
            continue
        seen.add(address)

        pc = pair.get("priceChange", {})
        vol = pair.get("volume", {})

        price_usd   = float(pair.get("priceUsd", 0) or 0)
        change_1h   = float(pc.get("h1",  0) or 0)
        change_6h   = float(pc.get("h6",  0) or 0)
        change_24h  = float(pc.get("h24", 0) or 0)
        vol_24h     = float(vol.get("h24", 0) or 0)
        liquidity   = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
        fdv         = float(pair.get("fdv", 0) or 0) or None

        signal, reason = _score(change_1h, change_6h, change_24h,
                                vol_24h, liquidity, fdv or 0)

        signals.append(Signal(
            coin=base.get("name", ""),
            symbol=base.get("symbol", ""),
            address=address,
            signal=signal,
            price_usd=price_usd,
            price_change_1h=change_1h,
            price_change_6h=change_6h,
            price_change_24h=change_24h,
            volume_24h=vol_24h,
            liquidity_usd=liquidity,
            fdv=fdv,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    return signals


def _score(c1h, c6h, c24h, vol, liq, fdv) -> tuple[str, str]:
    if vol < config.MIN_VOLUME_24H:
        return "watch", f"Vol too low (${vol:,.0f})"
    if liq < config.MIN_LIQUIDITY:
        return "watch", f"Liquidity too low (${liq:,.0f})"
    if c24h < config.MAX_DROP_24H:
        return "sell", f"Down {c24h:.1f}% in 24h — possible rug"
    if (c1h >= config.BUY_MOMENTUM_1H
            and c6h >= config.BUY_MOMENTUM_6H
            and (fdv == 0 or fdv <= config.MAX_FDV)):
        return (
            "buy now",
            f"Strong momentum: +{c1h:.1f}% (1h), +{c6h:.1f}% (6h), "
            f"vol ${vol:,.0f}, liq ${liq:,.0f}",
        )
    if c6h > 5 and vol > config.MIN_VOLUME_24H * 2:
        return "watch", f"Building momentum: +{c6h:.1f}% (6h)"
    return "hold", "No clear signal"
