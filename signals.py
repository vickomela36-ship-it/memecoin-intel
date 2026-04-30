#!/usr/bin/env python3
"""Memecoin signal generator — fetches data from DexScreener and emits buy/hold/sell signals."""

import json
import sys
from datetime import datetime, timezone

import requests

DEXSCREENER_API = "https://api.dexscreener.com"

# Criteria for a "buy now" signal
BUY_CRITERIA = {
    "min_price_change_1h": 5.0,    # at least +5% in the last hour
    "min_price_change_6h": 8.0,    # at least +8% over 6 hours
    "min_volume_24h": 100_000,     # $100k+ daily volume
    "min_liquidity_usd": 50_000,   # $50k+ liquidity
    "max_market_cap": 50_000_000,  # stay in small-cap memecoin territory
}

CHAINS = ["solana", "ethereum", "bsc"]


def _get(url: str, **kwargs) -> dict | list | None:
    try:
        r = requests.get(url, timeout=12, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_pairs() -> list[dict]:
    """Pull the latest meme-related pairs from multiple chains."""
    pairs: list[dict] = []
    seen: set[str] = set()

    for chain in CHAINS:
        data = _get(f"{DEXSCREENER_API}/latest/dex/search", params={"q": "meme"})
        if not data:
            continue
        for p in data.get("pairs", [])[:30]:
            addr = p.get("baseToken", {}).get("address", "")
            key = f"{p.get('chainId')}:{addr}"
            if key not in seen:
                seen.add(key)
                pairs.append(p)

    # Also pull the current boosted/trending tokens
    boosted = _get(f"{DEXSCREENER_API}/token-boosts/top/v1")
    if isinstance(boosted, list):
        for item in boosted[:20]:
            token_addr = item.get("tokenAddress", "")
            chain_id = item.get("chainId", "solana")
            key = f"{chain_id}:{token_addr}"
            if key in seen:
                continue
            seen.add(key)
            detail = _get(f"{DEXSCREENER_API}/latest/dex/tokens/{token_addr}")
            for p in (detail or {}).get("pairs", [])[:1]:
                pairs.append(p)

    return pairs


def evaluate(pair: dict) -> str:
    """Return 'buy now', 'hold', or 'sell' for a single pair."""
    try:
        pc = pair.get("priceChange", {}) or {}
        h1 = float(pc.get("h1") or 0)
        h6 = float(pc.get("h6") or 0)
        vol = float((pair.get("volume") or {}).get("h24") or 0)
        liq = float((pair.get("liquidity") or {}).get("usd") or 0)
        mcap = float(pair.get("marketCap") or pair.get("fdv") or 0)
    except (TypeError, ValueError):
        return "hold"

    c = BUY_CRITERIA
    if (
        h1 >= c["min_price_change_1h"]
        and h6 >= c["min_price_change_6h"]
        and vol >= c["min_volume_24h"]
        and liq >= c["min_liquidity_usd"]
        and (mcap == 0 or mcap <= c["max_market_cap"])
    ):
        return "buy now"

    if h1 < -10 or h6 < -15:
        return "sell"

    return "hold"


def generate_signals() -> list[dict]:
    pairs = fetch_pairs()
    results: list[dict] = []

    for pair in pairs:
        signal = evaluate(pair)
        if signal != "buy now":
            continue

        pc = pair.get("priceChange", {}) or {}
        vol = pair.get("volume", {}) or {}
        liq = pair.get("liquidity", {}) or {}
        base = pair.get("baseToken", {}) or {}

        h1 = float(pc.get("h1") or 0)
        h6 = float(pc.get("h6") or 0)
        h24 = float(pc.get("h24") or 0)

        results.append({
            "token": f"{base.get('name', 'Unknown')} ({base.get('symbol', '???')})",
            "symbol": base.get("symbol", "???"),
            "chain": pair.get("chainId", "unknown"),
            "signal": "buy now",
            "price_usd": float(pair.get("priceUsd") or 0),
            "change_1h": h1,
            "change_6h": h6,
            "change_24h": h24,
            "volume_24h": float(vol.get("h24") or 0),
            "liquidity_usd": float(liq.get("usd") or 0),
            "market_cap": float(pair.get("marketCap") or pair.get("fdv") or 0),
            "pair_url": pair.get("url", ""),
            "reason": (
                f"+{h1:.1f}% (1h) / +{h6:.1f}% (6h) / +{h24:.1f}% (24h) — "
                f"vol ${float(vol.get('h24') or 0):,.0f}"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return results


if __name__ == "__main__":
    signals = generate_signals()
    output = {
        "signals": signals,
        "count": len(signals),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
    json.dump(output, sys.stdout, indent=2)
    print()  # trailing newline
