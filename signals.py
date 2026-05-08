"""
Memecoin buy/sell signal engine.

Usage
-----
Standalone (Claude/loop uses WebFetch internally):
  python signals.py

Pipe mode (loop fetches data with WebFetch, pipes JSON here):
  echo '<coingecko-json>' | python signals.py --coingecko-stdin
  echo '<dexscreener-json>' | python signals.py --dex-stdin
"""
import json
import sys
from datetime import datetime, timezone

import requests

# ── API endpoints (used in standalone mode) ──────────────────────────────────
COINGECKO_TRENDING   = "https://api.coingecko.com/api/v3/search/trending"
COINGECKO_MARKETS    = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&ids={ids}&price_change_percentage=1h,24h"
)
DEXSCREENER_BOOSTED  = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS   = "https://api.dexscreener.com/latest/dex/tokens/{}"

# ── Signal thresholds ────────────────────────────────────────────────────────
MIN_1H_CHANGE  = 5.0    # percent
MIN_24H_VOLUME = 50_000 # USD
MIN_SCORE      = 60     # out of 100 → "buy now"


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_coingecko_coin(coin: dict) -> dict:
    """Score a CoinGecko market-data coin dict."""
    ch1h  = coin.get("price_change_percentage_1h_in_currency")  or 0
    ch24h = coin.get("price_change_percentage_24h")             or 0
    vol   = coin.get("total_volume")                            or 0
    price = coin.get("current_price")                           or 0

    score   = 0
    reasons = []

    if vol < MIN_24H_VOLUME:
        return _make_result(coin, "wait", 0, f"Volume too low (${vol:,.0f})", price)

    if ch1h >= MIN_1H_CHANGE:
        score += 40
        reasons.append(f"+{ch1h:.1f}% in 1h")

    if ch1h >= 15:
        score += 10
        reasons.append("strong 1h surge")

    if ch24h > 0:
        score += min(20, ch24h / 2)
        reasons.append(f"+{ch24h:.1f}% 24h")

    if vol >= 500_000:
        score += 20
        reasons.append(f"vol ${vol:,.0f}")
    elif vol >= MIN_24H_VOLUME:
        score += 10
        reasons.append(f"vol ${vol:,.0f}")

    signal = "buy now" if score >= MIN_SCORE else "wait"
    notes  = "; ".join(reasons) if reasons else "Below thresholds"
    return _make_result(coin, signal, round(min(score, 100), 1), notes, price)


def _make_result(coin: dict, signal: str, confidence: float, notes: str, price: float) -> dict:
    return {
        "signal":     signal,
        "coin":       coin.get("symbol", "?").upper(),
        "name":       coin.get("name", ""),
        "price":      float(price),
        "confidence": confidence,
        "notes":      notes,
        "volume_24h": coin.get("total_volume", 0),
        "change_1h":  coin.get("price_change_percentage_1h_in_currency", 0),
        "change_24h": coin.get("price_change_percentage_24h", 0),
        "url":        f"https://www.coingecko.com/en/coins/{coin.get('id','')}",
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }


# ── Data fetching (standalone mode) ─────────────────────────────────────────

def _get_trending_ids() -> list[str]:
    r = requests.get(COINGECKO_TRENDING, timeout=15)
    r.raise_for_status()
    return [c["item"]["id"] for c in r.json().get("coins", [])]


def _get_market_data(ids: list[str]) -> list[dict]:
    r = requests.get(COINGECKO_MARKETS.format(ids=",".join(ids)), timeout=15)
    r.raise_for_status()
    return r.json()


def get_signals_live() -> list[dict]:
    ids   = _get_trending_ids()
    coins = _get_market_data(ids)
    results = [score_coingecko_coin(c) for c in coins]
    results.sort(key=lambda x: (x["signal"] != "buy now", -x["confidence"]))
    return results


# ── Pipe mode: accept pre-fetched JSON ──────────────────────────────────────

def get_signals_from_coingecko_json(raw: str) -> list[dict]:
    """Accept CoinGecko /coins/markets JSON string."""
    coins   = json.loads(raw)
    results = [score_coingecko_coin(c) for c in coins]
    results.sort(key=lambda x: (x["signal"] != "buy now", -x["confidence"]))
    return results


def get_signals_from_trending_json(raw: str) -> list[dict]:
    """
    Accept CoinGecko /search/trending JSON.
    Returns partial results (no 1h data) scored on available fields.
    """
    data    = json.loads(raw)
    coins   = [c["item"] for c in data.get("coins", [])]
    results = [score_coingecko_coin(c) for c in coins]
    results.sort(key=lambda x: (x["signal"] != "buy now", -x["confidence"]))
    return results


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--live"

    if mode == "--coingecko-stdin":
        signals = get_signals_from_coingecko_json(sys.stdin.read())
    elif mode == "--trending-stdin":
        signals = get_signals_from_trending_json(sys.stdin.read())
    else:  # --live
        try:
            signals = get_signals_live()
        except Exception as e:
            print(json.dumps([{"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}]))
            sys.exit(1)

    print(json.dumps(signals, indent=2))

    buy_now = [s for s in signals if s.get("signal") == "buy now"]
    print(f"\n=== {len(buy_now)} BUY NOW signal(s) ===", file=sys.stderr)
    for s in buy_now:
        print(f"  {s['coin']}: ${s['price']:.6f}  conf={s['confidence']}  {s['notes']}", file=sys.stderr)
