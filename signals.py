#!/usr/bin/env python3
"""
Memecoin signal engine.
Fetches live market data from DexScreener and evaluates buy conditions.

Output: JSON array of signal objects, one per tracked token.
Each object has a "signal" field of either "buy now" or "hold".
"""
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

from config import TRACKED_TOKENS, BUY_SIGNAL_CONDITIONS

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens/{address}"


def fetch_pair(token_address: str) -> dict | None:
    """Return the highest-liquidity DexScreener pair for a token address."""
    url = DEXSCREENER_API.format(address=token_address)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            pairs = data.get("pairs") or []
            if not pairs:
                return None
            return max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
    except Exception as exc:
        print(f"[warn] fetch failed for {token_address}: {exc}", file=sys.stderr)
        return None


def evaluate(pair: dict, conds: dict) -> tuple[str, str]:
    """Return (signal_label, reason_string)."""
    ch = pair.get("priceChange") or {}
    vol = pair.get("volume") or {}
    liq = pair.get("liquidity") or {}

    change_1h  = float(ch.get("h1")  or 0)
    change_6h  = float(ch.get("h6")  or 0)
    change_24h = float(ch.get("h24") or 0)
    vol_24h    = float(vol.get("h24") or 0)
    liq_usd    = float(liq.get("usd") or 0)

    if (
        change_1h >= conds["min_1h_price_change_pct"]
        and vol_24h  >= conds["min_volume_24h_usd"]
        and liq_usd  >= conds["min_liquidity_usd"]
    ):
        reason = (
            f"1h +{change_1h:.1f}%  |  6h +{change_6h:.1f}%  |  24h +{change_24h:.1f}%  |  "
            f"vol ${vol_24h:,.0f}  |  liq ${liq_usd:,.0f}"
        )
        return "buy now", reason

    return "hold", ""


def run() -> list[dict]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []

    for token in TRACKED_TOKENS:
        pair = fetch_pair(token["address"])
        if pair is None:
            continue

        signal, reason = evaluate(pair, BUY_SIGNAL_CONDITIONS)
        base = pair.get("baseToken") or {}

        results.append({
            "signal":          signal,
            "token_symbol":    base.get("symbol") or token["symbol"],
            "token_name":      base.get("name")   or token["name"],
            "token_address":   token["address"],
            "chain":           pair.get("chainId", ""),
            "dex":             pair.get("dexId", ""),
            "price_usd":       pair.get("priceUsd", ""),
            "change_1h_pct":   (pair.get("priceChange") or {}).get("h1",  ""),
            "change_6h_pct":   (pair.get("priceChange") or {}).get("h6",  ""),
            "change_24h_pct":  (pair.get("priceChange") or {}).get("h24", ""),
            "volume_24h_usd":  (pair.get("volume")      or {}).get("h24", ""),
            "liquidity_usd":   (pair.get("liquidity")   or {}).get("usd", ""),
            "dex_url":         pair.get("url", f"https://dexscreener.com/search?q={token['address']}"),
            "reason":          reason,
            "checked_at":      now,
        })

    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
