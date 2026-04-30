"""
Memecoin signal detection via DexScreener API.

Fetches trending Solana memecoins and applies momentum/volume analysis
to produce BUY NOW / HOLD / SELL signals with a confidence score.

Returns JSON to stdout so signal_runner.py (or Claude loop) can act on it.
"""

import json
import sys
import time
from datetime import datetime, timezone

import requests

DEXSCREENER_TRENDING = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_PAIRS = "https://api.dexscreener.com/latest/dex/tokens/{address}"
CHAIN = "solana"

# Thresholds
MIN_LIQUIDITY_USD = 50_000
MIN_VOLUME_24H = 100_000
VOLUME_SURGE_RATIO = 3.0      # 1h volume vs expected (24h / 24)
PRICE_CHANGE_1H_MIN = 5.0     # % minimum 1h price change to consider
PRICE_CHANGE_6H_MAX = 80.0    # % cap – avoid chasing blow-off tops
CONFIDENCE_THRESHOLD = 60     # 0-100; signals below this are HOLD


def _score_pair(pair: dict) -> dict:
    """Score a single pair dict from DexScreener and return a signal dict."""
    price_usd = float(pair.get("priceUsd", 0) or 0)
    liquidity = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
    volume_24h = float((pair.get("volume") or {}).get("h24", 0) or 0)
    volume_1h = float((pair.get("volume") or {}).get("h1", 0) or 0)
    change_1h = float((pair.get("priceChange") or {}).get("h1", 0) or 0)
    change_6h = float((pair.get("priceChange") or {}).get("h6", 0) or 0)
    change_24h = float((pair.get("priceChange") or {}).get("h24", 0) or 0)

    base_token = pair.get("baseToken", {})
    coin = base_token.get("symbol", "UNKNOWN")
    name = base_token.get("name", coin)
    pair_url = pair.get("url", "")

    # Gate on minimum viability
    if liquidity < MIN_LIQUIDITY_USD or volume_24h < MIN_VOLUME_24H:
        return None
    if price_usd <= 0:
        return None

    # --- Scoring (each component 0-25, total 0-100) ---
    score = 0

    # 1. Volume surge vs baseline
    baseline_1h = volume_24h / 24
    surge_ratio = (volume_1h / baseline_1h) if baseline_1h > 0 else 0
    if surge_ratio >= VOLUME_SURGE_RATIO * 2:
        score += 25
    elif surge_ratio >= VOLUME_SURGE_RATIO:
        score += 15
    elif surge_ratio >= 1.5:
        score += 8

    # 2. 1h price momentum (positive, not already parabolic)
    if PRICE_CHANGE_1H_MIN <= change_1h <= 30:
        score += 25
    elif 30 < change_1h <= 60:
        score += 15
    elif change_1h > 60:
        score += 5   # late; risky

    # 3. 6h trend confirmation
    if change_6h > 0:
        score += min(25, int(change_6h / 2))

    # 4. Liquidity depth (more liquidity = lower rug risk)
    if liquidity >= 500_000:
        score += 25
    elif liquidity >= 200_000:
        score += 18
    elif liquidity >= 100_000:
        score += 10
    else:
        score += 5

    score = min(score, 100)

    if score >= CONFIDENCE_THRESHOLD and change_1h >= PRICE_CHANGE_1H_MIN and change_6h <= PRICE_CHANGE_6H_MAX:
        signal = "buy now"
    elif change_24h < -20 or change_1h < -10:
        signal = "sell"
    else:
        signal = "hold"

    return {
        "signal": signal,
        "coin": coin,
        "name": name,
        "price_usd": price_usd,
        "confidence": score,
        "change_1h": change_1h,
        "change_6h": change_6h,
        "change_24h": change_24h,
        "volume_24h": volume_24h,
        "volume_1h": volume_1h,
        "liquidity_usd": liquidity,
        "pair_url": pair_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def fetch_top_pairs(limit: int = 20) -> list[dict]:
    """Fetch top boosted tokens from DexScreener then hydrate with pair data."""
    try:
        resp = requests.get(DEXSCREENER_TRENDING, timeout=10)
        resp.raise_for_status()
        boosts = resp.json()
    except requests.exceptions.ConnectionError as exc:
        print(f"[signals] Network unreachable: {exc}", file=__import__("sys").stderr)
        return []
    except requests.exceptions.HTTPError as exc:
        print(f"[signals] DexScreener API error {exc.response.status_code}: {exc}", file=__import__("sys").stderr)
        return []
    except Exception as exc:
        print(f"[signals] Unexpected error fetching boosts: {exc}", file=__import__("sys").stderr)
        return []

    results = []
    seen = set()

    for item in boosts[:limit]:
        if item.get("chainId") != CHAIN:
            continue
        address = item.get("tokenAddress", "")
        if not address or address in seen:
            continue
        seen.add(address)

        try:
            time.sleep(0.2)  # be polite to the free API
            r = requests.get(DEXSCREENER_PAIRS.format(address=address), timeout=10)
            r.raise_for_status()
            pairs = r.json().get("pairs") or []
        except Exception:
            continue

        # Pick the highest-liquidity Solana pair
        sol_pairs = [p for p in pairs if p.get("chainId") == CHAIN]
        if not sol_pairs:
            continue
        best = max(sol_pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0))

        scored = _score_pair(best)
        if scored:
            results.append(scored)

    # Sort: buy now first, then by confidence desc
    results.sort(key=lambda x: (x["signal"] != "buy now", -x["confidence"]))
    return results


def run() -> list[dict]:
    signals = fetch_top_pairs()
    return signals


if __name__ == "__main__":
    output = run()
    print(json.dumps(output, indent=2))
