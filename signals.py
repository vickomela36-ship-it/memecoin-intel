"""
Memecoin buy/sell signal engine.

Fetches price + volume data from DexScreener (no API key needed) and emits
one of: 'buy now' | 'sell' | 'hold'
"""

import os
import requests
from datetime import datetime, timezone

# Tokens to track — add/remove as needed (DexScreener pair addresses on Solana)
TRACKED_PAIRS = os.environ.get("TRACKED_PAIRS", "").split(",") if os.environ.get("TRACKED_PAIRS") else []

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/pairs/solana/{pair}"


def _fetch_pair(pair_address: str) -> dict | None:
    try:
        url = DEXSCREENER_API.format(pair=pair_address)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        pairs = data.get("pairs") or []
        return pairs[0] if pairs else None
    except Exception as exc:
        print(f"[signals] fetch error for {pair_address}: {exc}")
        return None


def _score_pair(pair: dict) -> tuple[str, dict]:
    """Return (signal, metadata) for one DexScreener pair."""
    try:
        price_change_5m = float(pair.get("priceChange", {}).get("m5", 0))
        price_change_1h = float(pair.get("priceChange", {}).get("h1", 0))
        volume_5m = float(pair.get("volume", {}).get("m5", 0))
        volume_1h = float(pair.get("volume", {}).get("h1", 0) or 1)
        liquidity_usd = float((pair.get("liquidity") or {}).get("usd", 0))
        price_usd = float(pair.get("priceUsd", 0))
        base_symbol = pair.get("baseToken", {}).get("symbol", "?")
        pair_address = pair.get("pairAddress", "")

        meta = {
            "symbol": base_symbol,
            "pair_address": pair_address,
            "price_usd": price_usd,
            "price_change_5m": price_change_5m,
            "price_change_1h": price_change_1h,
            "volume_5m_usd": volume_5m,
            "volume_1h_usd": volume_1h,
            "liquidity_usd": liquidity_usd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # --- Signal logic ---
        # BUY NOW: strong 5-min momentum, accelerating volume, decent liquidity
        volume_ratio = volume_5m / (volume_1h / 12)  # compare 5m vol vs avg 5m slice
        buy_conditions = (
            price_change_5m >= 3.0       # ≥3% gain in last 5 minutes
            and price_change_1h >= 5.0   # ≥5% gain in last hour
            and volume_ratio >= 2.0      # volume 2× above hourly average
            and liquidity_usd >= 10_000  # min $10k liquidity
        )
        sell_conditions = price_change_5m <= -5.0 or price_change_1h <= -15.0

        if buy_conditions:
            return "buy now", meta
        if sell_conditions:
            return "sell", meta
        return "hold", meta

    except Exception as exc:
        print(f"[signals] score error: {exc}")
        return "hold", {}


def run_signals() -> list[dict]:
    """Return list of signal dicts for all tracked pairs."""
    results = []
    for pair_address in TRACKED_PAIRS:
        pair_address = pair_address.strip()
        if not pair_address:
            continue
        pair = _fetch_pair(pair_address)
        if not pair:
            continue
        signal, meta = _score_pair(pair)
        results.append({"signal": signal, **meta})

    if not results:
        # Demo mode when no pairs configured — return a placeholder
        results.append({
            "signal": "hold",
            "symbol": "DEMO",
            "pair_address": "",
            "price_usd": 0.0,
            "price_change_5m": 0.0,
            "price_change_1h": 0.0,
            "volume_5m_usd": 0.0,
            "volume_1h_usd": 0.0,
            "liquidity_usd": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return results


if __name__ == "__main__":
    for item in run_signals():
        print(item)
