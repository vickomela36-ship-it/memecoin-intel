"""
Buy/sell signal logic using DexScreener public API.
Outputs JSON to stdout — run directly or import get_signals().
"""
import json
import sys
from datetime import datetime, timezone

import requests

from config import SIGNAL_THRESHOLDS, TOKENS_TO_MONITOR


def _fetch_pair(token_address: str) -> dict | None:
    """Return the highest-liquidity pair for a token, or None on failure."""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        if not pairs:
            return None
        return max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0))
    except Exception as exc:
        return {"_error": str(exc)}


def _classify(pair: dict) -> dict:
    """Turn a DexScreener pair dict into a signal result dict."""
    pc = pair.get("priceChange") or {}
    vol = pair.get("volume") or {}
    liq = pair.get("liquidity") or {}
    base = pair.get("baseToken") or {}
    t = SIGNAL_THRESHOLDS

    price_change_5m = float(pc.get("m5") or 0)
    price_change_1h = float(pc.get("h1") or 0)
    price_change_6h = float(pc.get("h6") or 0)
    volume_1h = float(vol.get("h1") or 0)
    liquidity = float(liq.get("usd") or 0)
    price_usd = float(pair.get("priceUsd") or 0)

    buy_signal = (
        price_change_5m >= t["price_change_5m_buy"]
        and price_change_1h >= t["price_change_1h_buy"]
        and volume_1h >= t["volume_usd_1h_min"]
        and liquidity >= t["liquidity_usd_min"]
    )
    sell_signal = (
        price_change_1h <= t["price_change_1h_sell"]
        or price_change_6h <= t["price_change_6h_sell"]
    )

    if buy_signal:
        signal = "buy now"
    elif sell_signal:
        signal = "sell"
    else:
        signal = "hold"

    return {
        "signal": signal,
        "token": base.get("symbol", "UNKNOWN"),
        "token_name": base.get("name", "Unknown"),
        "price_usd": price_usd,
        "price_change_5m_pct": price_change_5m,
        "price_change_1h_pct": price_change_1h,
        "price_change_6h_pct": price_change_6h,
        "volume_usd_1h": volume_1h,
        "liquidity_usd": liquidity,
        "dex_url": pair.get("url", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_signals() -> list[dict]:
    """Return a signal dict for every token in TOKENS_TO_MONITOR."""
    results = []
    for address, symbol, _chain in TOKENS_TO_MONITOR:
        pair = _fetch_pair(address)
        if pair is None:
            results.append({
                "signal": "error",
                "token": symbol,
                "error": "No pairs found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        elif "_error" in pair:
            results.append({
                "signal": "error",
                "token": symbol,
                "error": pair["_error"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        else:
            results.append(_classify(pair))
    return results


if __name__ == "__main__":
    signals = get_signals()
    if not signals:
        print(json.dumps({"info": "No tokens configured in config.py"}))
        sys.exit(0)
    print(json.dumps(signals, indent=2))
