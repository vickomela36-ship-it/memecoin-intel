"""
Memecoin buy/sell signal generator.

Fetches live data from CoinGecko public API and classifies each coin.

Signal rules:
  buy now  — 24h price change >= +10 % AND 24h volume >= $500 k
  sell     — 24h price change <= -10 %
  hold     — everything else

Usage:
    python3 signals.py            # prints full JSON report
    python3 signals.py --buy-only # prints only buy-now signals

Requires: requests>=2.28.0
"""

import argparse
import json
import sys
import requests
from datetime import datetime, timezone

COINGECKO_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"

# --- Thresholds (edit here to tune sensitivity) ---
BUY_THRESHOLD_PCT = 10.0    # minimum 24h % gain to trigger "buy now"
SELL_THRESHOLD_PCT = -10.0  # maximum 24h % loss to trigger "sell"
MIN_VOLUME_USD = 500_000    # minimum 24h volume for a "buy now" signal


def fetch_memecoins(per_page: int = 50) -> list[dict]:
    params = {
        "vs_currency": "usd",
        "category": "meme-token",
        "order": "volume_desc",
        "per_page": per_page,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    resp = requests.get(COINGECKO_MARKETS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def classify(coin: dict) -> dict:
    pct = coin.get("price_change_percentage_24h") or 0.0
    vol = coin.get("total_volume") or 0
    price = coin.get("current_price") or 0.0
    name = coin.get("name", "Unknown")
    symbol = (coin.get("symbol") or "???").upper()

    if pct >= BUY_THRESHOLD_PCT and vol >= MIN_VOLUME_USD:
        signal_type = "buy now"
        confidence = round(min(0.5 + (pct - BUY_THRESHOLD_PCT) / 40.0, 1.0), 2)
        reason = f"+{pct:.1f}% in 24h · ${vol:,.0f} volume"
    elif pct <= SELL_THRESHOLD_PCT:
        signal_type = "sell"
        confidence = round(min(0.5 + (abs(pct) - abs(SELL_THRESHOLD_PCT)) / 40.0, 1.0), 2)
        reason = f"{pct:.1f}% in 24h"
    else:
        signal_type = "hold"
        confidence = 0.5
        reason = f"{pct:+.1f}% in 24h"

    return {
        "coin": name,
        "symbol": symbol,
        "signal_type": signal_type,
        "price_usd": price,
        "price_change_24h_pct": round(pct, 2),
        "volume_24h_usd": vol,
        "confidence": confidence,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run(per_page: int = 50) -> dict:
    coins = fetch_memecoins(per_page)
    signals = [classify(c) for c in coins]
    buy_now = [s for s in signals if s["signal_type"] == "buy now"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_analyzed": len(signals),
        "buy_now_count": len(buy_now),
        "buy_now_signals": buy_now,
        "all_signals": signals,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--buy-only", action="store_true", help="Print only buy-now signals")
    args = parser.parse_args()

    result = run()

    if args.buy_only:
        print(json.dumps(result["buy_now_signals"], indent=2))
    else:
        print(json.dumps(result, indent=2))

    if result.get("error"):
        sys.exit(1)
