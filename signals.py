#!/usr/bin/env python3
"""Memecoin signal generator using DexScreener public API."""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_PAIRS_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"

MIN_LIQUIDITY_USD = 50_000
MIN_VOLUME_24H = 100_000
MIN_PRICE_CHANGE_1H = 5.0
BUY_NOW_SCORE_THRESHOLD = 60


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "memecoin-intel/1.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read())


def score_pair(pair: dict) -> tuple[int, str]:
    """Return (score 0-100, reason string) for a DexScreener pair."""
    score = 0
    reasons = []

    price_h1 = pair.get("priceChange", {}).get("h1", 0) or 0
    price_h24 = pair.get("priceChange", {}).get("h24", 0) or 0
    volume_h24 = pair.get("volume", {}).get("h24", 0) or 0
    buys_h1 = pair.get("txns", {}).get("h1", {}).get("buys", 0) or 0
    sells_h1 = pair.get("txns", {}).get("h1", {}).get("sells", 0) or 0

    # 1h price momentum (0-35 pts)
    if price_h1 >= 20:
        score += 35
        reasons.append(f"+{price_h1:.1f}% in 1h")
    elif price_h1 >= 10:
        score += 25
        reasons.append(f"+{price_h1:.1f}% in 1h")
    elif price_h1 >= 5:
        score += 15
        reasons.append(f"+{price_h1:.1f}% in 1h")

    # 24h trend (0-20 pts)
    if price_h24 >= 50:
        score += 20
        reasons.append(f"+{price_h24:.1f}% in 24h")
    elif price_h24 >= 20:
        score += 12
        reasons.append(f"+{price_h24:.1f}% in 24h")
    elif price_h24 >= 10:
        score += 6
        reasons.append(f"+{price_h24:.1f}% in 24h")

    # Volume (0-25 pts)
    if volume_h24 >= 1_000_000:
        score += 25
        reasons.append(f"Vol ${volume_h24/1e6:.1f}M")
    elif volume_h24 >= 500_000:
        score += 18
        reasons.append(f"Vol ${volume_h24/1000:.0f}K")
    elif volume_h24 >= 100_000:
        score += 10
        reasons.append(f"Vol ${volume_h24/1000:.0f}K")

    # Buy pressure (0-20 pts)
    total_txns = buys_h1 + sells_h1
    if total_txns > 0:
        buy_ratio = buys_h1 / total_txns
        if buy_ratio >= 0.70:
            score += 20
            reasons.append(f"Buy pressure {buy_ratio*100:.0f}%")
        elif buy_ratio >= 0.60:
            score += 12
            reasons.append(f"Buy ratio {buy_ratio*100:.0f}%")
        elif buy_ratio >= 0.50:
            score += 6

    return min(score, 100), "; ".join(reasons) if reasons else "Trending token"


def get_signals() -> list[dict]:
    try:
        boosts = fetch_json(DEXSCREENER_BOOSTS_URL)
    except urllib.error.URLError as e:
        return [{"error": f"Network error fetching boosts: {e}"}]
    except Exception as e:
        return [{"error": str(e)}]

    signals = []
    seen_addresses = set()

    for item in boosts[:25]:
        token_address = item.get("tokenAddress", "")
        chain_id = item.get("chainId", "")
        if not token_address or token_address in seen_addresses:
            continue
        seen_addresses.add(token_address)

        try:
            pairs_data = fetch_json(DEXSCREENER_PAIRS_URL.format(token_address))
            pairs = pairs_data.get("pairs") or []
        except Exception:
            continue

        if not pairs:
            continue

        # Pick highest-liquidity pair
        pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0)
        liquidity = pair.get("liquidity", {}).get("usd", 0) or 0
        volume_h24 = pair.get("volume", {}).get("h24", 0) or 0
        price_h1 = pair.get("priceChange", {}).get("h1", 0) or 0

        if liquidity < MIN_LIQUIDITY_USD:
            continue
        if volume_h24 < MIN_VOLUME_24H:
            continue
        if price_h1 < MIN_PRICE_CHANGE_1H:
            continue

        score, reason = score_pair(pair)
        signal_type = "buy now" if score >= BUY_NOW_SCORE_THRESHOLD else "watch"

        symbol = pair.get("baseToken", {}).get("symbol", token_address[:8])
        price_usd = float(pair.get("priceUsd", 0) or 0)
        price_h24 = pair.get("priceChange", {}).get("h24", 0) or 0

        signals.append({
            "token": symbol,
            "token_address": token_address,
            "chain": chain_id,
            "signal": signal_type,
            "score": score,
            "price_usd": price_usd,
            "price_change_1h": price_h1,
            "price_change_24h": price_h24,
            "volume_24h_usd": volume_h24,
            "liquidity_usd": liquidity,
            "reason": reason,
            "pair_url": pair.get("url", ""),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    return sorted(signals, key=lambda s: s["score"], reverse=True)


def get_simulated_signals() -> list[dict]:
    """Return deterministic fake signals for pipeline testing (no internet needed)."""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        {
            "token": "TESTMEME", "token_address": "0xTEST", "chain": "solana",
            "signal": "buy now", "score": 82,
            "price_usd": 0.00004269, "price_change_1h": 18.5, "price_change_24h": 47.2,
            "volume_24h_usd": 1_250_000, "liquidity_usd": 320_000,
            "reason": "+18.5% in 1h; Vol $1.3M; Buy pressure 73%",
            "pair_url": "https://dexscreener.com/solana/testmeme",
            "timestamp": now,
        },
        {
            "token": "WATCHCOIN", "token_address": "0xWATCH", "chain": "ethereum",
            "signal": "watch", "score": 45,
            "price_usd": 0.0123, "price_change_1h": 6.1, "price_change_24h": 12.4,
            "volume_24h_usd": 180_000, "liquidity_usd": 75_000,
            "reason": "+6.1% in 1h; Vol $180K",
            "pair_url": "https://dexscreener.com/ethereum/watchcoin",
            "timestamp": now,
        },
    ]


if __name__ == "__main__":
    simulate = "--simulate" in sys.argv
    results = get_simulated_signals() if simulate else get_signals()
    print(json.dumps(results, indent=2))
    buy_now = [s for s in results if s.get("signal") == "buy now"]
    print(f"\n--- {len(buy_now)} BUY NOW signal(s) out of {len(results)} candidates ---",
          file=sys.stderr)
