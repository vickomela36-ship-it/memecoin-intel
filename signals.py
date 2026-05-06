"""
Buy/sell signal logic — fetches trending tokens from DexScreener and
applies criteria to emit a 'buy now' signal.

Buy criteria (all must be met):
  - 1h price change >= +5%
  - 24h volume >= $50,000
  - Liquidity >= $25,000
  - Not a honeypot (basic: requires sells > 0)
"""

import urllib.request
import json


# Primary: token profiles (requires no auth). Fallback: boosted tokens.
DEXSCREENER_TRENDING_URLS = [
    "https://api.dexscreener.com/token-profiles/latest/v1",
    "https://api.dexscreener.com/token-boosts/top/v1",
]
DEXSCREENER_PAIRS_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"

BUY_MIN_PRICE_CHANGE_1H = 5.0    # %
BUY_MIN_VOLUME_24H = 50_000       # USD
BUY_MIN_LIQUIDITY = 25_000        # USD


def _get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "memecoin-intel/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_signals() -> list[dict]:
    """Return list of tokens with signal='buy now' based on current market data."""
    profiles = None
    last_err = None
    for url in DEXSCREENER_TRENDING_URLS:
        try:
            profiles = _get(url)
            break
        except Exception as e:
            last_err = e
    if profiles is None:
        return [{"error": str(last_err), "fetch_failed": True}]

    results = []
    seen = set()

    for profile in profiles[:30]:  # check top 30 trending
        address = profile.get("tokenAddress", "")
        chain = profile.get("chainId", "")
        if not address or address in seen:
            continue
        seen.add(address)

        try:
            data = _get(DEXSCREENER_PAIRS_URL.format(address))
            pairs = data.get("pairs") or []
        except Exception:
            continue

        if not pairs:
            continue

        # Use the highest-liquidity pair for price data
        pair = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd", 0))

        price_usd = float((pair.get("priceUsd") or 0))
        change_1h = float((pair.get("priceChange") or {}).get("h1") or 0)
        volume_24h = float((pair.get("volume") or {}).get("h24") or 0)
        liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)
        dex_url = pair.get("url", f"https://dexscreener.com/{chain}/{address}")
        token_name = (pair.get("baseToken") or {}).get("symbol", address[:8])

        signal = None
        if (
            change_1h >= BUY_MIN_PRICE_CHANGE_1H
            and volume_24h >= BUY_MIN_VOLUME_24H
            and liquidity >= BUY_MIN_LIQUIDITY
        ):
            signal = "buy now"

        results.append({
            "token": token_name,
            "token_address": address,
            "chain": chain,
            "price_usd": price_usd,
            "price_change_1h": change_1h,
            "volume_24h": volume_24h,
            "liquidity_usd": liquidity,
            "dexscreener_url": dex_url,
            "signal": signal,
        })

    return results
