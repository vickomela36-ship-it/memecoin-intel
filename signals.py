#!/usr/bin/env python3
"""
Buy/sell signal logic for memecoins using Dexscreener price data.

Signal types: 'buy now', 'sell', 'hold'
Outputs JSON array of signals to stdout.
"""

import json
import sys
import requests
from datetime import datetime, timezone

# Coins to monitor: add/remove as needed
COINS = [
    {"symbol": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "chain": "solana"},
    {"symbol": "WIF",  "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "chain": "solana"},
    {"symbol": "POPCAT", "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "chain": "solana"},
    {"symbol": "PEPE", "address": "0x6982508145454ce325ddbe47a25d4ec3d2311933", "chain": "ethereum"},
    {"symbol": "DOGE", "address": "0xba2ae424d960c26247dd6c32edc70b295c744c43", "chain": "bsc"},
]

# Thresholds
BUY_THRESHOLD_PCT  = 5.0   # 24h price change % to trigger 'buy now'
SELL_THRESHOLD_PCT = -5.0  # 24h price change % to trigger 'sell'
MIN_VOLUME_USD     = 50_000  # minimum 24h volume to consider signal valid


def _fetch_pair(coin: dict) -> dict | None:
    url = f"https://api.dexscreener.com/latest/dex/tokens/{coin['address']}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    pairs = resp.json().get("pairs") or []
    if not pairs:
        return None
    # highest-liquidity pair
    return max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd", 0)))


def get_signals() -> list[dict]:
    signals = []
    ts = datetime.now(timezone.utc).isoformat()

    for coin in COINS:
        try:
            pair = _fetch_pair(coin)
            if not pair:
                continue

            price       = float(pair.get("priceUsd") or 0)
            change_24h  = float((pair.get("priceChange") or {}).get("h24") or 0)
            volume_24h  = float((pair.get("volume") or {}).get("h24") or 0)

            if volume_24h < MIN_VOLUME_USD:
                signal_type = "hold"
                confidence  = 0.3
            elif change_24h >= BUY_THRESHOLD_PCT:
                signal_type = "buy now"
                confidence  = round(min(change_24h / 20, 1.0), 2)
            elif change_24h <= SELL_THRESHOLD_PCT:
                signal_type = "sell"
                confidence  = round(min(abs(change_24h) / 20, 1.0), 2)
            else:
                signal_type = "hold"
                confidence  = 0.5

            signals.append({
                "coin":           coin["symbol"],
                "signal":         signal_type,
                "price":          price,
                "price_change_24h": change_24h,
                "confidence":     confidence,
                "volume_24h_usd": volume_24h,
                "timestamp":      ts,
                "notes":          f"24h: {change_24h:+.2f}%  vol: ${volume_24h:,.0f}",
            })

        except Exception as exc:
            signals.append({
                "coin":      coin["symbol"],
                "signal":    "error",
                "error":     str(exc),
                "timestamp": ts,
            })

    return signals


if __name__ == "__main__":
    results = get_signals()
    print(json.dumps(results, indent=2))
    has_buy = any(s.get("signal") == "buy now" for s in results)
    sys.exit(0 if has_buy else 1)
