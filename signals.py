#!/usr/bin/env python3
"""
Memecoin buy signal scanner.

Signal source: reads from signals_input.json (populated by the user's data feed).
Alternatively, set SIGNALS_URL env var to an internal/local API endpoint.

Output: JSON array of buy-now signals to stdout.

signals_input.json format — array of token objects:
[
  {
    "token": "BONK",
    "token_name": "Bonk",
    "token_address": "DezXAZ8z...",
    "chain": "solana",
    "price_usd": 0.00002341,
    "price_change_1h_pct": 12.5,
    "liquidity_usd": 850000,
    "volume_24h_usd": 4200000,
    "dexscreener_url": "https://dexscreener.com/solana/DezXAZ8z..."
  }
]
"""
import json
import os
import sys
from pathlib import Path

SIGNAL_CRITERIA = {
    "min_liquidity_usd": float(os.getenv("MIN_LIQUIDITY", "10000")),
    "min_volume_24h": float(os.getenv("MIN_VOLUME_24H", "50000")),
    "min_price_change_1h_pct": float(os.getenv("MIN_PRICE_CHANGE_1H", "5.0")),
    "max_price_change_1h_pct": float(os.getenv("MAX_PRICE_CHANGE_1H", "200.0")),
}

INPUT_FILE = Path(__file__).parent / "signals_input.json"


def load_candidates() -> list[dict]:
    signals_url = os.getenv("SIGNALS_URL")
    if signals_url:
        import urllib.request
        with urllib.request.urlopen(signals_url, timeout=10) as r:
            return json.loads(r.read())

    if not INPUT_FILE.exists():
        print(
            f"[signals.py] No input: create {INPUT_FILE} or set SIGNALS_URL",
            file=sys.stderr,
        )
        return []

    with INPUT_FILE.open() as f:
        return json.load(f)


def evaluate(token: dict) -> dict | None:
    try:
        liquidity = float(token.get("liquidity_usd") or 0)
        volume_24h = float(token.get("volume_24h_usd") or 0)
        price_change = float(token.get("price_change_1h_pct") or 0)

        c = SIGNAL_CRITERIA
        if not (
            liquidity >= c["min_liquidity_usd"]
            and volume_24h >= c["min_volume_24h"]
            and c["min_price_change_1h_pct"] <= price_change <= c["max_price_change_1h_pct"]
        ):
            return None

        return {
            "signal": "buy now",
            "token": token.get("token", "UNKNOWN"),
            "token_name": token.get("token_name", ""),
            "token_address": token.get("token_address", ""),
            "chain": token.get("chain", ""),
            "price_usd": float(token.get("price_usd") or 0),
            "price_change_1h_pct": price_change,
            "liquidity_usd": liquidity,
            "volume_24h_usd": volume_24h,
            "dexscreener_url": token.get("dexscreener_url", ""),
        }
    except (TypeError, ValueError):
        return None


def main() -> None:
    try:
        candidates = load_candidates()
    except Exception as exc:
        print(f"[signals.py] Failed to load candidates: {exc}", file=sys.stderr)
        print("[]")
        return

    buy_signals = [s for t in candidates if (s := evaluate(t))]
    print(json.dumps(buy_signals, indent=2))


if __name__ == "__main__":
    main()
