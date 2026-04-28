"""
Fetches pair data from DexScreener and emits buy / sell / hold signals.

Signal is 'buy now' when ALL thresholds in config.py are met:
  - 1h price change >= BUY_SIGNAL_1H_CHANGE_MIN
  - 24h volume     >= BUY_SIGNAL_VOLUME_24H_MIN
  - liquidity      >= BUY_SIGNAL_LIQUIDITY_MIN
  - buy pressure   >= BUY_SIGNAL_BUY_PRESSURE_MIN  (buys / total 1h txns)

Signal is 'sell' when price is dumping hard (1h < -10 %) or buy pressure < 30 %.
Everything else is 'hold'.
"""

from __future__ import annotations

import requests
from datetime import datetime, timezone

DEXSCREENER_PAIRS_API = "https://api.dexscreener.com/latest/dex/pairs"


def _fetch_pair(address: str) -> dict | None:
    try:
        resp = requests.get(f"{DEXSCREENER_PAIRS_API}/{address}", timeout=10)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        return pairs[0] if pairs else None
    except Exception as exc:
        print(f"[signals] fetch error for {address}: {exc}")
        return None


def _buy_pressure(pair: dict) -> float:
    txns = pair.get("txns", {}).get("h1", {})
    buys  = txns.get("buys", 0)
    sells = txns.get("sells", 0)
    total = buys + sells
    return buys / total if total > 0 else 0.5


def _compute_signal(pair: dict) -> str:
    from config import (
        BUY_SIGNAL_1H_CHANGE_MIN,
        BUY_SIGNAL_VOLUME_24H_MIN,
        BUY_SIGNAL_LIQUIDITY_MIN,
        BUY_SIGNAL_BUY_PRESSURE_MIN,
    )

    ch = pair.get("priceChange", {})
    change_1h  = float(ch.get("h1",  0) or 0)
    volume_24h = float((pair.get("volume")    or {}).get("h24", 0) or 0)
    liquidity  = float((pair.get("liquidity") or {}).get("usd",  0) or 0)
    pressure   = _buy_pressure(pair)

    is_buy = (
        change_1h  >= BUY_SIGNAL_1H_CHANGE_MIN
        and volume_24h >= BUY_SIGNAL_VOLUME_24H_MIN
        and liquidity  >= BUY_SIGNAL_LIQUIDITY_MIN
        and pressure   >= BUY_SIGNAL_BUY_PRESSURE_MIN
    )
    is_sell = change_1h < -10 or (pressure < 0.30 and change_1h < 0)

    if is_buy:
        return "buy now"
    if is_sell:
        return "sell"
    return "hold"


def get_signals() -> list[dict]:
    """Return a signal record for every token in TOKENS_TO_WATCH."""
    from config import TOKENS_TO_WATCH

    results: list[dict] = []
    for token in TOKENS_TO_WATCH:
        pair = _fetch_pair(token["address"])
        if not pair:
            continue

        ch       = pair.get("priceChange", {})
        vol      = pair.get("volume", {})
        pressure = _buy_pressure(pair)
        buys     = pair.get("txns", {}).get("h1", {}).get("buys", 0)
        sells    = pair.get("txns", {}).get("h1", {}).get("sells", 0)
        total    = buys + sells

        results.append({
            "token":          token["name"],
            "symbol":         pair.get("baseToken", {}).get("symbol", token["name"]),
            "signal":         _compute_signal(pair),
            "price_usd":      pair.get("priceUsd", "N/A"),
            "1h_change":      f"{float(ch.get('h1',  0) or 0):+.2f}%",
            "6h_change":      f"{float(ch.get('h6',  0) or 0):+.2f}%",
            "24h_change":     f"{float(ch.get('h24', 0) or 0):+.2f}%",
            "volume_24h":     f"${float(vol.get('h24', 0) or 0):,.0f}",
            "liquidity_usd":  f"${float((pair.get('liquidity') or {}).get('usd', 0) or 0):,.0f}",
            "buy_pressure":   f"{pressure * 100:.1f}%" if total > 0 else "N/A",
            "dexscreener_url": pair.get("url", "") or "",
            "checked_at":     datetime.now(timezone.utc).isoformat(),
        })

    return results
