import requests
import json
from datetime import datetime, timezone

# Tokens to watch — add/remove contract addresses here
WATCHLIST = [
    {"symbol": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
    {"symbol": "WIF",  "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
    {"symbol": "POPCAT", "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"},
    {"symbol": "MEW",  "address": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5"},
    {"symbol": "PEPE", "address": "0x6982508145454Ce325dDbE47a25d4ec3d2311933"},
]

DEXSCREENER_BASE = "https://api.dexscreener.com/latest/dex/tokens"


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def fetch_pair(address: str) -> dict | None:
    """Return the highest-liquidity pair for a token address, or None."""
    try:
        resp = requests.get(f"{DEXSCREENER_BASE}/{address}", timeout=12)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        if not pairs:
            return None
        return max(pairs, key=lambda p: _safe_float(p.get("liquidity", {}).get("usd")))
    except Exception as exc:
        print(f"[warn] fetch_pair({address}): {exc}")
        return None


def compute_signal(pair: dict) -> str:
    """
    Buy signal requires:
      - liquidity >= $50k (enough to enter/exit)
      - 1h price change > +5%
      - 6h price change > 0% (trend confirmation)
      - 24h volume > $100k (active market)
      - buy pressure (buys / total txns last 1h) > 60%

    Sell signal when:
      - 1h drop > -10%, OR
      - 6h drop > -15% while 1h is also negative, OR
      - buy pressure < 35%

    Everything else → hold.
    """
    pc = pair.get("priceChange", {})
    ch1h  = _safe_float(pc.get("h1"))
    ch6h  = _safe_float(pc.get("h6"))
    vol24 = _safe_float(pair.get("volume", {}).get("h24"))
    liq   = _safe_float(pair.get("liquidity", {}).get("usd"))

    txns_1h = pair.get("txns", {}).get("h1", {})
    buys  = _safe_float(txns_1h.get("buys"))
    sells = _safe_float(txns_1h.get("sells"))
    total = buys + sells
    buy_pressure = (buys / total * 100) if total > 0 else 50.0

    if (liq >= 50_000 and ch1h > 5 and ch6h > 0
            and vol24 > 100_000 and buy_pressure > 60):
        return "buy now"

    if ch1h < -10 or (ch6h < -15 and ch1h < 0) or buy_pressure < 35:
        return "sell"

    return "hold"


def run_signals() -> list[dict]:
    """Fetch data and compute signal for every token in WATCHLIST."""
    results = []
    now = datetime.now(timezone.utc).isoformat()

    for token in WATCHLIST:
        pair = fetch_pair(token["address"])
        if pair is None:
            continue

        pc     = pair.get("priceChange", {})
        vol    = pair.get("volume", {})
        liq    = pair.get("liquidity", {})
        txns   = pair.get("txns", {}).get("h1", {})
        buys   = _safe_float(txns.get("buys"))
        sells  = _safe_float(txns.get("sells"))
        total  = buys + sells

        results.append({
            "token":           pair.get("baseToken", {}).get("name", token["symbol"]),
            "symbol":          pair.get("baseToken", {}).get("symbol", token["symbol"]),
            "signal":          compute_signal(pair),
            "price_usd":       pair.get("priceUsd", "N/A"),
            "price_change_1h": pc.get("h1", "N/A"),
            "price_change_6h": pc.get("h6", "N/A"),
            "price_change_24h":pc.get("h24", "N/A"),
            "volume_24h_usd":  vol.get("h24", "N/A"),
            "liquidity_usd":   liq.get("usd", "N/A"),
            "buy_pressure":    round(buys / total * 100, 1) if total > 0 else 50.0,
            "dexscreener_url": pair.get("url", ""),
            "checked_at":      now,
        })

    return results


if __name__ == "__main__":
    signals = run_signals()
    print(json.dumps(signals, indent=2))
