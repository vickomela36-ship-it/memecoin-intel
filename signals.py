#!/usr/bin/env python3
"""signals.py - Fetch top Solana memecoin pairs from DexScreener and compute buy/sell/hold signals."""

import json
import sys
import urllib.request
from datetime import datetime, timezone

import config

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search?q={query}"


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "memecoin-intel/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _signal(pair: dict) -> str:
    changes = pair.get("priceChange") or {}
    h1 = float(changes.get("h1") or 0)
    h24 = float(changes.get("h24") or 0)
    vol24 = float((pair.get("volume") or {}).get("h24") or 0)
    liq = float((pair.get("liquidity") or {}).get("usd") or 0)
    txns = (pair.get("txns") or {}).get("h24") or {}
    buys = int(txns.get("buys") or 0)
    sells = int(txns.get("sells") or 0)
    total = buys + sells
    buy_ratio = buys / total if total > 0 else 0.5

    if h1 < config.SELL_1H_CHANGE_PCT or h24 < config.SELL_24H_CHANGE_PCT:
        return "sell"
    if (
        h1 >= config.BUY_1H_CHANGE_PCT
        and h24 >= config.BUY_24H_CHANGE_PCT
        and vol24 >= config.MIN_VOLUME_24H_USD
        and liq >= config.MIN_LIQUIDITY_USD
        and buy_ratio >= config.BUY_PRESSURE_RATIO
    ):
        return "buy now"
    return "hold"


def get_signals() -> list[dict]:
    url = DEXSCREENER_SEARCH.format(query=config.DEXSCREENER_QUERY)
    try:
        data = _fetch(url)
    except Exception as exc:
        print(f"[signals] fetch error: {exc}", file=sys.stderr)
        return []

    pairs = [p for p in (data.get("pairs") or []) if p.get("chainId") == "solana"]
    pairs = pairs[: config.MAX_PAIRS]

    now = datetime.now(timezone.utc).isoformat()
    results = []
    for pair in pairs:
        base = pair.get("baseToken") or {}
        changes = pair.get("priceChange") or {}
        volume = pair.get("volume") or {}
        liq = float((pair.get("liquidity") or {}).get("usd") or 0)
        txns = (pair.get("txns") or {}).get("h24") or {}
        buys = int(txns.get("buys") or 0)
        sells = int(txns.get("sells") or 0)
        total = buys + sells
        buy_pct = round(buys / total * 100, 1) if total > 0 else 50.0

        results.append(
            {
                "token": base.get("name", "Unknown"),
                "symbol": base.get("symbol", "?"),
                "price_usd": pair.get("priceUsd") or "0",
                "price_change_1h": float(changes.get("h1") or 0),
                "price_change_6h": float(changes.get("h6") or 0),
                "price_change_24h": float(changes.get("h24") or 0),
                "volume_24h_usd": float(volume.get("h24") or 0),
                "liquidity_usd": liq,
                "buy_pressure": f"{buy_pct}%",
                "dexscreener_url": pair.get("url") or "",
                "checked_at": now,
                "signal": _signal(pair),
            }
        )
    return results


if __name__ == "__main__":
    print(json.dumps(get_signals(), indent=2))
