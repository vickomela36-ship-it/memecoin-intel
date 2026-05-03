"""
Memecoin buy/sell signal generator using DexScreener API.
Outputs JSON with signal data. Run directly to check current signals.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Tokens to track (Solana memecoins by contract address)
TRACKED_TOKENS = [
    {"symbol": "BONK",  "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
    {"symbol": "WIF",   "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
    {"symbol": "POPCAT","address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"},
    {"symbol": "FARTCOIN","address": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"},
    {"symbol": "PEPE",  "address": "CLgBGaFrCpLpMKtJVvFQb9v5i4yWt3pKCKFQgBNwHLhh"},
]

# Signal thresholds
MIN_LIQUIDITY_USD = 50_000
MIN_MARKET_CAP = 500_000
MAX_MARKET_CAP = 500_000_000
VOLUME_SPIKE_THRESHOLD = 2.0   # 1h volume / 6h avg hourly volume
PRICE_CHANGE_1H_BUY = 5.0      # % price increase in 1h
PRICE_CHANGE_1H_STRONG = 15.0  # % for strong buy
MIN_SCORE_BUY = 60


def fetch_token(address: str) -> dict | None:
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "memecoin-intel/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        pairs = data.get("pairs") or []
        # Pick the pair with highest liquidity
        solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
        if not solana_pairs:
            return None
        return max(solana_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        return None


def score_token(pair: dict) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    market_cap = float(pair.get("marketCap", 0) or 0)
    price_usd = float(pair.get("priceUsd", 0) or 0)
    price_change_1h = float((pair.get("priceChange") or {}).get("h1", 0) or 0)
    price_change_6h = float((pair.get("priceChange") or {}).get("h6", 0) or 0)
    price_change_24h = float((pair.get("priceChange") or {}).get("h24", 0) or 0)
    vol_1h = float((pair.get("volume") or {}).get("h1", 0) or 0)
    vol_6h = float((pair.get("volume") or {}).get("h6", 0) or 0)
    txns_1h = (pair.get("txns") or {}).get("h1", {})
    buys_1h = int((txns_1h or {}).get("buys", 0) or 0)
    sells_1h = int((txns_1h or {}).get("sells", 0) or 0)

    # Liquidity check
    if liquidity < MIN_LIQUIDITY_USD:
        return 0, ["Insufficient liquidity"]
    if not (MIN_MARKET_CAP <= market_cap <= MAX_MARKET_CAP):
        return 0, ["Market cap out of range"]

    # Price momentum
    if price_change_1h >= PRICE_CHANGE_1H_STRONG:
        score += 35
        reasons.append(f"Strong 1h pump +{price_change_1h:.1f}%")
    elif price_change_1h >= PRICE_CHANGE_1H_BUY:
        score += 20
        reasons.append(f"1h price up +{price_change_1h:.1f}%")

    if price_change_6h > 10:
        score += 15
        reasons.append(f"6h trend +{price_change_6h:.1f}%")

    if price_change_24h > 20:
        score += 10
        reasons.append(f"24h up +{price_change_24h:.1f}%")

    # Volume spike
    avg_hourly_6h = vol_6h / 6 if vol_6h > 0 else 0
    if avg_hourly_6h > 0:
        vol_ratio = vol_1h / avg_hourly_6h
        if vol_ratio >= VOLUME_SPIKE_THRESHOLD * 2:
            score += 25
            reasons.append(f"Volume spike {vol_ratio:.1f}x vs 6h avg")
        elif vol_ratio >= VOLUME_SPIKE_THRESHOLD:
            score += 15
            reasons.append(f"Volume up {vol_ratio:.1f}x vs 6h avg")

    # Buy/sell pressure
    total_txns = buys_1h + sells_1h
    if total_txns > 0:
        buy_ratio = buys_1h / total_txns
        if buy_ratio >= 0.70:
            score += 15
            reasons.append(f"Buy pressure {buy_ratio*100:.0f}% ({buys_1h} buys / {sells_1h} sells)")
        elif buy_ratio >= 0.55:
            score += 8
            reasons.append(f"Slight buy pressure {buy_ratio*100:.0f}%")

    return score, reasons


def generate_signal(score: int) -> str:
    if score >= MIN_SCORE_BUY:
        return "buy now"
    if score >= 40:
        return "watch"
    return "hold"


def check_signals() -> list[dict]:
    results = []
    for token in TRACKED_TOKENS:
        pair = fetch_token(token["address"])
        if not pair:
            continue
        score, reasons = score_token(pair)
        signal = generate_signal(score)
        price = float(pair.get("priceUsd", 0) or 0)
        results.append({
            "token": token["symbol"],
            "signal": signal,
            "score": score,
            "price": price,
            "reason": "; ".join(reasons) if reasons else "No significant signals",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        time.sleep(0.3)  # rate limit courtesy
    return results


MOCK_SIGNALS = [
    {
        "token": "BONK",
        "signal": "buy now",
        "score": 82,
        "price": 0.00002341,
        "reason": "Strong 1h pump +18.3%; Volume spike 4.2x vs 6h avg; Buy pressure 74% (312 buys / 109 sells)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "token": "WIF",
        "signal": "watch",
        "score": 48,
        "price": 1.234,
        "reason": "1h price up +6.1%; Slight buy pressure 58%",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
]


if __name__ == "__main__":
    if "--mock" in sys.argv:
        signals = MOCK_SIGNALS
    else:
        signals = check_signals()
    print(json.dumps(signals, indent=2))
    buy_signals = [s for s in signals if s["signal"] == "buy now"]
    if buy_signals:
        print(f"\n*** {len(buy_signals)} BUY NOW signal(s) detected! ***", file=sys.stderr)
    sys.exit(0 if buy_signals else 1)
