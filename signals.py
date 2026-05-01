import requests
import json
from datetime import datetime, timezone

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"

# Minimum thresholds for a "buy now" signal
THRESHOLDS = {
    "price_change_24h_min": 20.0,   # must be up 20%+ in 24h
    "price_change_6h_min": 5.0,     # must be up 5%+ in 6h (momentum continuing)
    "price_change_1h_min": 0.0,     # must be positive in last hour
    "volume_24h_min": 200_000,      # min $200k 24h volume
    "liquidity_min": 100_000,       # min $100k liquidity (rug protection)
    "confidence_min": 0.55,         # min composite confidence score
}


def _safe_float(val, default=0.0):
    try:
        return float(val or default)
    except (TypeError, ValueError):
        return default


def score_pair(pair: dict) -> dict | None:
    """Return a buy-signal dict if the pair passes all thresholds, else None."""
    base = pair.get("baseToken", {})
    price_changes = pair.get("priceChange", {})
    volume = pair.get("volume", {})
    liquidity = pair.get("liquidity", {})

    ch24 = _safe_float(price_changes.get("h24"))
    ch6  = _safe_float(price_changes.get("h6"))
    ch1  = _safe_float(price_changes.get("h1"))
    vol24 = _safe_float(volume.get("h24"))
    liq   = _safe_float(liquidity.get("usd"))
    price = _safe_float(pair.get("priceUsd"))

    # Hard filters — must all pass
    if ch24 < THRESHOLDS["price_change_24h_min"]:
        return None
    if ch6 < THRESHOLDS["price_change_6h_min"]:
        return None
    if ch1 < THRESHOLDS["price_change_1h_min"]:
        return None
    if vol24 < THRESHOLDS["volume_24h_min"]:
        return None
    if liq < THRESHOLDS["liquidity_min"]:
        return None

    # Composite confidence: each component capped at 1.0
    score_24h  = min(ch24 / 60.0, 1.0)   # full score at 60% 24h gain
    score_6h   = min(ch6  / 20.0, 1.0)   # full score at 20% 6h gain
    score_1h   = min(ch1  / 10.0, 1.0)   # full score at 10% 1h gain
    score_vol  = min(vol24 / 1_000_000, 1.0)  # full score at $1M volume
    score_liq  = min(liq   / 500_000,   1.0)  # full score at $500k liquidity

    confidence = (score_24h * 0.30 + score_6h * 0.25 + score_1h * 0.20
                  + score_vol * 0.15 + score_liq * 0.10)

    if confidence < THRESHOLDS["confidence_min"]:
        return None

    return {
        "signal": "buy now",
        "confidence": round(confidence, 3),
        "token_name": base.get("name", "Unknown"),
        "token_symbol": base.get("symbol", "???"),
        "token_address": base.get("address", ""),
        "chain": pair.get("chainId", ""),
        "price_usd": price,
        "price_change_24h": ch24,
        "price_change_6h": ch6,
        "price_change_1h": ch1,
        "volume_24h": vol24,
        "liquidity_usd": liq,
        "dex": pair.get("dexId", ""),
        "pair_url": pair.get("url", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_signals() -> dict:
    now = datetime.now(timezone.utc).isoformat()

    # 1. Fetch top boosted tokens (active social momentum)
    try:
        resp = requests.get(DEXSCREENER_BOOSTS_URL, timeout=15)
        resp.raise_for_status()
        boosts = resp.json()
    except Exception as exc:
        return {"checked_at": now, "error": str(exc), "buy_signals": []}

    buy_signals: list[dict] = []
    seen: set[str] = set()
    checked = 0

    for boost in boosts[:30]:  # examine top 30 boosted tokens
        addr = boost.get("tokenAddress", "")
        chain = boost.get("chainId", "")
        key = f"{chain}:{addr}"
        if not addr or key in seen:
            continue
        seen.add(key)

        try:
            r = requests.get(DEXSCREENER_TOKENS_URL.format(addr), timeout=10)
            r.raise_for_status()
            pairs = r.json().get("pairs") or []
        except Exception:
            continue

        checked += 1
        if not pairs:
            continue

        # Use the most liquid pair for the token
        best = max(pairs, key=lambda p: _safe_float(
            (p.get("liquidity") or {}).get("usd")))

        result = score_pair(best)
        if result:
            buy_signals.append(result)

    buy_signals.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "checked_at": now,
        "tokens_checked": checked,
        "buy_signals": buy_signals[:5],  # cap at top 5
    }


if __name__ == "__main__":
    print(json.dumps(run_signals(), indent=2))
