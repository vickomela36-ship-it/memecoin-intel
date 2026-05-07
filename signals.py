"""Buy/sell signal logic — uses DexScreener (no API key required)."""

import json
import sys
import requests
from datetime import datetime, timezone

from config import BUY_CRITERIA

_BOOST_API = "https://api.dexscreener.com/token-boosts/top/v1"
_TOKEN_API = "https://api.dexscreener.com/latest/dex/tokens/{address}"


def _confidence(volume_24h: float, price_change_1h: float, txns_1h: int) -> int:
    """Return a 0-100 confidence score."""
    vol_score = min(volume_24h / 2_000_000, 1.0) * 40
    chg_score = min(price_change_1h / 20.0, 1.0) * 40
    txn_score = min(txns_1h / 500, 1.0) * 20
    return int(vol_score + chg_score + txn_score)


def get_signals() -> list[dict]:
    """
    Fetch top boosted Solana tokens from DexScreener and return any that
    meet the BUY_CRITERIA thresholds as 'buy now' signals.
    Returns a list of dicts; each has at minimum a 'signal' key.
    """
    try:
        resp = requests.get(_BOOST_API, timeout=10)
        resp.raise_for_status()
        tokens = resp.json()
    except Exception as exc:
        return [{"signal": "error", "error": f"Token list fetch failed: {exc}",
                 "timestamp": datetime.now(timezone.utc).isoformat()}]

    results = []
    for token in tokens[:30]:
        address = token.get("tokenAddress")
        if not address:
            continue
        try:
            pr = requests.get(_TOKEN_API.format(address=address), timeout=8)
            if pr.status_code != 200:
                continue
            sol_pairs = [
                p for p in pr.json().get("pairs", [])
                if p.get("chainId") == "solana"
            ]
            if not sol_pairs:
                continue

            best = max(sol_pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0)
            vol = best.get("volume", {}).get("h24", 0) or 0
            chg = best.get("priceChange", {}).get("h1", 0) or 0
            liq = best.get("liquidity", {}).get("usd", 0) or 0
            txns = best.get("txns", {}).get("h1", {})
            total_txns = (txns.get("buys", 0) or 0) + (txns.get("sells", 0) or 0)

            if (vol >= BUY_CRITERIA["min_volume_24h"]
                    and chg >= BUY_CRITERIA["min_price_change_1h"]
                    and liq >= BUY_CRITERIA["min_liquidity"]
                    and total_txns >= BUY_CRITERIA["min_txns_1h"]):

                name = best.get("baseToken", {}).get("name", "Unknown")
                symbol = best.get("baseToken", {}).get("symbol", "???")
                price = float(best.get("priceUsd", 0) or 0)

                results.append({
                    "signal": "buy now",
                    "coin": f"{name} ({symbol})",
                    "price": price,
                    "confidence": _confidence(vol, chg, total_txns),
                    "volume_24h": round(vol, 2),
                    "price_change_1h": round(chg, 2),
                    "liquidity": round(liq, 2),
                    "txns_1h": total_txns,
                    "pair_url": best.get("url", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            continue

    results.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    if not results:
        return [{"signal": "hold", "message": "No buy signals at this time",
                 "timestamp": datetime.now(timezone.utc).isoformat()}]
    return results


if __name__ == "__main__":
    print(json.dumps(get_signals(), indent=2))
