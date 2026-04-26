#!/usr/bin/env python3
"""
Memecoin signal checker — queries DexScreener for momentum signals.
Outputs a JSON list of coins currently signalling 'buy now'.
"""
import json
import sys
import requests
from datetime import datetime, timezone

WATCHLIST = [
    "DOGE", "SHIB", "PEPE", "FLOKI", "BONK",
    "WIF", "POPCAT", "BRETT", "MEME", "TURBO",
]

# Minimum thresholds to generate a 'buy now' signal
BUY_THRESHOLD_1H_PCT = 5.0      # ≥ 5 % gain in the last hour
MIN_VOLUME_24H_USD   = 500_000  # ≥ $500k daily volume (liquidity filter)

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/search?q={symbol}"


def fetch_best_pair(symbol: str) -> dict | None:
    """Return the highest-volume DexScreener pair matching symbol, or None."""
    try:
        r = requests.get(
            DEXSCREENER_URL.format(symbol=symbol),
            timeout=10,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        pairs = r.json().get("pairs") or []
        # Keep only exact base-token symbol matches
        pairs = [
            p for p in pairs
            if p.get("baseToken", {}).get("symbol", "").upper() == symbol
        ]
        if not pairs:
            return None
        return max(pairs, key=lambda p: float(p.get("volume", {}).get("h24") or 0))
    except Exception:
        return None


def confidence(change_1h: float, volume_24h: float) -> str:
    if change_1h > 20 and volume_24h > 5_000_000:
        return "high"
    if change_1h > 10 or volume_24h > 2_000_000:
        return "medium"
    return "low"


def check_signals() -> list[dict]:
    results = []
    now = datetime.now(timezone.utc)

    for symbol in WATCHLIST:
        pair = fetch_best_pair(symbol)
        if not pair:
            continue

        change_1h  = float(pair.get("priceChange", {}).get("h1")  or 0)
        volume_24h = float(pair.get("volume",      {}).get("h24") or 0)
        price_usd  = float(pair.get("priceUsd") or 0)
        name       = pair.get("baseToken", {}).get("name", symbol)

        if change_1h >= BUY_THRESHOLD_1H_PCT and volume_24h >= MIN_VOLUME_24H_USD:
            results.append({
                "signal":          "buy now",
                "coin":            f"{name} ({symbol})",
                "symbol":          symbol,
                "price_usd":       price_usd,
                "price_change_1h": change_1h,
                "volume_24h":      volume_24h,
                "confidence":      confidence(change_1h, volume_24h),
                "timestamp":       now.isoformat(),
                "dex_url":         pair.get("url", ""),
                "notes":           f"{change_1h:+.1f}% in 1h · ${volume_24h:,.0f} 24h vol",
            })

    return results


if __name__ == "__main__":
    signals = check_signals()
    print(json.dumps(signals, indent=2))
    sys.exit(0 if signals else 1)
