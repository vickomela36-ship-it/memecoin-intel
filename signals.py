"""
Memecoin buy/sell signal engine.
Fetches trending tokens from DexScreener, scores them, and emits signals as JSON.

Exit codes: 0 = success, 1 = fetch error
Output: JSON array of signal objects to stdout
"""

import json
import sys
import time
from datetime import datetime, timezone

import requests

DEXSCREENER_URL = "https://api.dexscreener.com/token-boosts/top/v1"
TRENDING_URL = "https://api.dexscreener.com/latest/dex/search?q=trending"

# Chains we care about
TARGET_CHAINS = {"solana", "ethereum", "base", "bsc"}

# Scoring thresholds
BUY_NOW_MIN_SCORE = 72
SCORE_WEIGHTS = {
    "volume_24h": 0.30,
    "price_change_24h": 0.25,
    "liquidity": 0.20,
    "buysell_ratio": 0.15,
    "price_change_1h": 0.10,
}


def fetch_trending_pairs() -> list[dict]:
    """Fetch top boosted / trending pairs from DexScreener."""
    pairs = []
    headers = {"User-Agent": "memecoin-intel/1.0"}

    for url in [DEXSCREENER_URL, TRENDING_URL]:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # /token-boosts returns a list of {tokenAddress, chainId, ...}
            if isinstance(data, list):
                addresses = [
                    d["tokenAddress"]
                    for d in data
                    if d.get("chainId", "").lower() in TARGET_CHAINS
                ][:20]
                if addresses:
                    addr_str = ",".join(addresses[:10])
                    p_resp = requests.get(
                        f"https://api.dexscreener.com/latest/dex/tokens/{addr_str}",
                        headers=headers,
                        timeout=15,
                    )
                    p_resp.raise_for_status()
                    p_data = p_resp.json()
                    pairs.extend(p_data.get("pairs", []))
            elif isinstance(data, dict):
                pairs.extend(data.get("pairs", []))
        except requests.RequestException:
            continue
        time.sleep(0.3)

    seen = set()
    unique = []
    for p in pairs:
        key = (p.get("chainId", ""), p.get("pairAddress", ""))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def score_pair(pair: dict) -> tuple[float, str]:
    """Return (0-100 score, human-readable reason) for a pair."""
    info = pair.get("priceChange", {})
    volume = pair.get("volume", {})
    liquidity = pair.get("liquidity", {})
    txns = pair.get("txns", {}).get("h24", {})

    price_change_1h = float(info.get("h1", 0) or 0)
    price_change_24h = float(info.get("h24", 0) or 0)
    volume_24h = float(volume.get("h24", 0) or 0)
    liq_usd = float(liquidity.get("usd", 0) or 0)
    buys = int(txns.get("buys", 0) or 0)
    sells = int(txns.get("sells", 0) or 0)
    total_txns = buys + sells

    # Normalise each component to 0-100
    vol_score = min(100, (volume_24h / 500_000) * 100)
    liq_score = min(100, (liq_usd / 100_000) * 100)

    price24_score = 0.0
    if price_change_24h > 0:
        price24_score = min(100, price_change_24h * 2)

    price1h_score = 0.0
    if price_change_1h > 0:
        price1h_score = min(100, price_change_1h * 5)

    bs_score = 50.0
    if total_txns > 0:
        buy_pct = buys / total_txns
        bs_score = buy_pct * 100

    score = (
        SCORE_WEIGHTS["volume_24h"] * vol_score
        + SCORE_WEIGHTS["price_change_24h"] * price24_score
        + SCORE_WEIGHTS["liquidity"] * liq_score
        + SCORE_WEIGHTS["buysell_ratio"] * bs_score
        + SCORE_WEIGHTS["price_change_1h"] * price1h_score
    )

    parts = []
    if price_change_24h > 0:
        parts.append(f"+{price_change_24h:.1f}% 24h")
    if price_change_1h > 0:
        parts.append(f"+{price_change_1h:.1f}% 1h")
    if volume_24h > 0:
        parts.append(f"${volume_24h:,.0f} vol/24h")
    if total_txns > 0:
        parts.append(f"{buy_pct * 100:.0f}% buys")
    reason = ", ".join(parts) if parts else "no strong indicators"

    return round(score, 1), reason


def build_signals(pairs: list[dict]) -> list[dict]:
    """Score all pairs and return only the ones worth acting on."""
    signals = []
    now = datetime.now(timezone.utc).isoformat()

    for pair in pairs:
        chain = pair.get("chainId", "unknown")
        if chain.lower() not in TARGET_CHAINS:
            continue

        base = pair.get("baseToken", {})
        token_name = base.get("name", "Unknown")
        token_symbol = base.get("symbol", "?")
        price_usd = float(pair.get("priceUsd", 0) or 0)

        score, reason = score_pair(pair)

        if score >= BUY_NOW_MIN_SCORE:
            signal_text = "buy now"
        elif score >= 50:
            signal_text = "watch"
        else:
            signal_text = "hold"

        signals.append(
            {
                "signal": signal_text,
                "token": f"{token_name} ({token_symbol})",
                "chain": chain,
                "price_usd": price_usd,
                "score": score,
                "reason": reason,
                "timestamp": now,
            }
        )

    signals.sort(key=lambda s: s["score"], reverse=True)
    return signals


def main() -> int:
    pairs = fetch_trending_pairs()
    if not pairs:
        print(json.dumps({"error": "no pairs fetched", "signals": []}))
        return 1

    signals = build_signals(pairs)
    print(json.dumps(signals, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
