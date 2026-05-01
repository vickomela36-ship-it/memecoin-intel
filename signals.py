#!/usr/bin/env python3
"""
Buy/sell signal logic for memecoins using CoinGecko price data.

Signal types: 'buy now', 'sell', 'hold'
Outputs JSON array of signals to stdout.
Exit code 0 = at least one 'buy now' signal found; 1 = none found or all errors.

Override for local testing: create signals_override.json with a list of signal dicts.
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone

# ---------- configuration -------------------------------------------------- #

COINS = {
    "bonk":       "BONK",
    "dogwifcoin": "WIF",
    "popcat":     "POPCAT",
    "pepe":       "PEPE",
    "dogecoin":   "DOGE",
}

BUY_THRESHOLD_PCT  =  5.0    # 24h % change to fire 'buy now'
SELL_THRESHOLD_PCT = -5.0    # 24h % change to fire 'sell'
MIN_VOLUME_USD     = 50_000  # minimum 24h volume for signal to be valid
OVERRIDE_FILE      = os.path.join(os.path.dirname(__file__), "signals_override.json")

# ---------- helpers --------------------------------------------------------- #

def _classify(change_pct: float, volume_usd: float, symbol: str, price: float, ts: str) -> dict:
    if volume_usd < MIN_VOLUME_USD:
        sig, conf = "hold", 0.3
    elif change_pct >= BUY_THRESHOLD_PCT:
        sig, conf = "buy now", round(min(change_pct / 20, 1.0), 2)
    elif change_pct <= SELL_THRESHOLD_PCT:
        sig, conf = "sell", round(min(abs(change_pct) / 20, 1.0), 2)
    else:
        sig, conf = "hold", 0.5

    return {
        "coin":             symbol,
        "signal":           sig,
        "price":            price,
        "price_change_24h": round(change_pct, 4),
        "confidence":       conf,
        "volume_24h_usd":   volume_usd,
        "timestamp":        ts,
        "notes":            f"24h: {change_pct:+.2f}%  vol: ${volume_usd:,.0f}",
    }


# ---------- data sources ---------------------------------------------------- #

def _fetch_coingecko() -> list[dict]:
    ids = ",".join(COINS.keys())
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=usd"
        "&include_24hr_change=true&include_24hr_vol=true"
    )
    resp = requests.get(url, timeout=15, headers={"Accept": "application/json"})
    resp.raise_for_status()
    data = resp.json()

    ts = datetime.now(timezone.utc).isoformat()
    results = []
    for cg_id, symbol in COINS.items():
        info = data.get(cg_id, {})
        price      = float(info.get("usd") or 0)
        change_24h = float(info.get("usd_24h_change") or 0)
        vol_24h    = float(info.get("usd_24h_vol") or 0)
        results.append(_classify(change_24h, vol_24h, symbol, price, ts))
    return results


# ---------- main ------------------------------------------------------------ #

def get_signals() -> list[dict]:
    # local override lets you inject test signals or swap in your own data source
    if os.path.exists(OVERRIDE_FILE):
        with open(OVERRIDE_FILE) as f:
            return json.load(f)

    try:
        return _fetch_coingecko()
    except Exception as exc:
        ts = datetime.now(timezone.utc).isoformat()
        return [
            {
                "coin":      sym,
                "signal":    "error",
                "error":     str(exc),
                "timestamp": ts,
            }
            for sym in COINS.values()
        ]


if __name__ == "__main__":
    results = get_signals()
    print(json.dumps(results, indent=2))
    has_buy = any(s.get("signal") == "buy now" for s in results)
    sys.exit(0 if has_buy else 1)
