"""
Buy/sell signal logic — queries DexScreener for trending Solana memecoins
and returns a 'buy now' signal when criteria are met.

Signal criteria (all must pass):
  - 1h price change >= BUY_MIN_CHANGE_1H (default 20%)
  - Liquidity >= BUY_MIN_LIQUIDITY (default $10k, filters rugs)
  - Volume/Liquidity ratio >= BUY_MIN_VOL_LIQ_RATIO (default 0.5)
"""

import os
import requests
from datetime import datetime, timezone

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKEN_URL  = "https://api.dexscreener.com/latest/dex/tokens/{address}"

BUY_MIN_CHANGE_1H     = float(os.getenv("BUY_MIN_CHANGE_1H", 20))
BUY_MIN_LIQUIDITY     = float(os.getenv("BUY_MIN_LIQUIDITY", 10_000))
BUY_MIN_VOL_LIQ_RATIO = float(os.getenv("BUY_MIN_VOL_LIQ_RATIO", 0.5))
TARGET_CHAIN          = os.getenv("TARGET_CHAIN", "solana")   # e.g. "solana", "ethereum", "" for all


def get_signal() -> dict:
    """
    Returns a dict with at minimum keys: signal, timestamp.
    signal values: 'buy now' | 'hold' | 'error'
    'buy now' dicts include full token/pair metrics.
    """
    try:
        resp = requests.get(DEXSCREENER_BOOSTS_URL, timeout=10)
        resp.raise_for_status()
        boosts = resp.json()
    except Exception as exc:
        return _error(f"DexScreener boosts fetch failed: {exc}")

    for item in boosts[:30]:
        chain   = item.get("chainId", "")
        address = item.get("tokenAddress", "")

        if TARGET_CHAIN and chain.lower() != TARGET_CHAIN.lower():
            continue

        try:
            pair_resp = requests.get(
                DEXSCREENER_TOKEN_URL.format(address=address), timeout=10
            )
            pair_resp.raise_for_status()
            pairs = pair_resp.json().get("pairs") or []
        except Exception:
            continue

        if not pairs:
            continue

        # Use the pair with highest 24h volume
        best = max(pairs, key=lambda p: float((p.get("volume") or {}).get("h24") or 0))

        change_1h  = float((best.get("priceChange") or {}).get("h1") or 0)
        price_usd  = float(best.get("priceUsd") or 0)
        liquidity  = float((best.get("liquidity") or {}).get("usd") or 0)
        volume_24h = float((best.get("volume") or {}).get("h24") or 0)
        dex_url    = best.get("url", "")
        symbol     = (best.get("baseToken") or {}).get("symbol", "UNKNOWN")

        vol_liq_ratio = volume_24h / max(liquidity, 1)

        if (
            change_1h  >= BUY_MIN_CHANGE_1H
            and liquidity  >= BUY_MIN_LIQUIDITY
            and vol_liq_ratio >= BUY_MIN_VOL_LIQ_RATIO
        ):
            return {
                "signal":         "buy now",
                "token":          symbol,
                "token_address":  address,
                "chain":          chain,
                "price_usd":      price_usd,
                "price_change_1h": change_1h,
                "liquidity_usd":  liquidity,
                "volume_24h":     volume_24h,
                "dex_url":        dex_url,
                "timestamp":      _now(),
            }

    return {"signal": "hold", "reason": "No tokens met buy criteria", "timestamp": _now()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(msg: str) -> dict:
    return {"signal": "error", "reason": msg, "timestamp": _now()}


def _demo_buy_signal() -> dict:
    """Returns a fake 'buy now' signal for pipeline testing."""
    return {
        "signal":          "buy now",
        "token":           "DEMO",
        "token_address":   "DemoAddress111111111111111111111111111111111",
        "chain":           "solana",
        "price_usd":       0.00004269,
        "price_change_1h": 42.0,
        "liquidity_usd":   85_000,
        "volume_24h":      210_000,
        "dex_url":         "https://dexscreener.com/solana/demo",
        "timestamp":       _now(),
    }


if __name__ == "__main__":
    import json
    import sys
    if "--demo" in sys.argv:
        print(json.dumps(_demo_buy_signal(), indent=2))
    else:
        print(json.dumps(get_signal(), indent=2))
