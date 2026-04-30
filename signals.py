"""
Fetch live memecoin data from DexScreener and emit buy/sell/hold signals.
Outputs a JSON array to stdout so callers can parse it easily.
"""

import json
import sys
from datetime import datetime, timezone

import requests

from config import (
    BUY_PRICE_CHANGE_1H,
    BUY_VOLUME_RATIO,
    SELL_PRICE_CHANGE_1H,
    WATCH_LIST,
)

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search?q={symbol}"


def fetch_best_pair(symbol: str, preferred_chain: str) -> dict | None:
    """Return the most-liquid pair for a symbol, preferring the given chain."""
    try:
        resp = requests.get(
            DEXSCREENER_SEARCH.format(symbol=symbol), timeout=10
        )
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
    except Exception as exc:
        print(f"[signals] fetch error for {symbol}: {exc}", file=sys.stderr)
        return None

    if not pairs:
        return None

    preferred = [p for p in pairs if p.get("chainId") == preferred_chain]
    pool = preferred if preferred else pairs
    return max(pool, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))


def classify(pair: dict) -> dict:
    """Derive a signal dict from a DexScreener pair object."""
    pct = pair.get("priceChange") or {}
    vol = pair.get("volume") or {}

    ch_1h  = float(pct.get("h1") or 0)
    ch_6h  = float(pct.get("h6") or 0)
    vol_1h = float(vol.get("h1") or 0)
    vol_6h = float(vol.get("h6") or 1)

    avg_hourly_vol = vol_6h / 6
    vol_ratio = vol_1h / avg_hourly_vol if avg_hourly_vol else 1.0

    price = float(pair.get("priceUsd") or 0)
    coin  = (pair.get("baseToken") or {}).get("symbol", "?")

    if ch_1h >= BUY_PRICE_CHANGE_1H and vol_ratio >= BUY_VOLUME_RATIO and ch_6h < 50:
        signal = "buy now"
        confidence = round(min(0.95, 0.45 + ch_1h / 60 + vol_ratio / 12), 2)
    elif ch_1h <= SELL_PRICE_CHANGE_1H:
        signal = "sell"
        confidence = round(min(0.95, 0.45 + abs(ch_1h) / 60), 2)
    else:
        signal = "hold"
        confidence = 0.0

    return {
        "signal":     signal,
        "coin":       coin,
        "price":      price,
        "confidence": confidence,
        "notes":      f"1h {ch_1h:+.1f}%  |  vol ratio {vol_ratio:.1f}x  |  6h {ch_6h:+.1f}%",
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }


def run() -> list[dict]:
    results = []
    for token in WATCH_LIST:
        pair = fetch_best_pair(token["symbol"], token["chain"])
        if pair:
            results.append(classify(pair))
    return results


def mock_signals() -> list[dict]:
    """Return one synthetic buy-now signal for pipeline testing."""
    ts = datetime.now(timezone.utc).isoformat()
    return [
        {"signal": "buy now", "coin": "BONK", "price": 0.000021,
         "confidence": 0.78, "notes": "1h +8.3%  |  vol ratio 2.3x  |  6h +12.1%",
         "timestamp": ts},
        {"signal": "hold",    "coin": "WIF",  "price": 1.84,
         "confidence": 0.0,  "notes": "1h +1.2%  |  vol ratio 0.9x  |  6h +3.4%",
         "timestamp": ts},
    ]


if __name__ == "__main__":
    if "--mock" in sys.argv:
        print(json.dumps(mock_signals(), indent=2))
    else:
        print(json.dumps(run(), indent=2))
