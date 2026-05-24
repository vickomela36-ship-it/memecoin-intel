import requests
from datetime import datetime

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"

MIN_LIQUIDITY_USD = 20_000
MIN_VOLUME_24H = 50_000
BUY_SIGNAL_MIN_SCORE = 4


def fetch_trending_addresses():
    resp = requests.get(DEXSCREENER_BOOSTS_URL, timeout=10)
    resp.raise_for_status()
    boosts = resp.json()
    return [b["tokenAddress"] for b in boosts[:25] if "tokenAddress" in b]


def fetch_best_pair(token_address):
    url = DEXSCREENER_TOKENS_URL.format(token_address)
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    pairs = resp.json().get("pairs") or []
    if not pairs:
        return None
    return max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))


def _f(pair, *keys, default=0.0):
    """Safely navigate nested pair dict and cast to float."""
    obj = pair
    for k in keys:
        obj = (obj or {}).get(k)
    try:
        return float(obj or default)
    except (TypeError, ValueError):
        return float(default)


def score_pair(pair):
    change_5m = _f(pair, "priceChange", "m5")
    change_1h = _f(pair, "priceChange", "h1")
    change_6h = _f(pair, "priceChange", "h6")
    change_24h = _f(pair, "priceChange", "h24")
    volume_24h = _f(pair, "volume", "h24")
    liquidity = _f(pair, "liquidity", "usd")
    fdv = _f(pair, "fdv")
    txns_buys = _f(pair, "txns", "h1", "buys")
    txns_sells = _f(pair, "txns", "h1", "sells")

    # Hard disqualifiers
    if liquidity < MIN_LIQUIDITY_USD:
        return 0, "hold"
    if change_24h < -30:
        return 0, "sell"

    score = 0

    # Price momentum
    if change_1h > 20:
        score += 3
    elif change_1h > 10:
        score += 2
    elif change_1h > 5:
        score += 1

    if change_24h > 50:
        score += 2
    elif change_24h > 20:
        score += 1

    if change_6h > 15:
        score += 1

    if change_5m > 3:
        score += 1

    # Volume strength
    if volume_24h > 1_000_000:
        score += 2
    elif volume_24h > 500_000:
        score += 1
    elif volume_24h < MIN_VOLUME_24H:
        score -= 1

    # Buy pressure (buys > sells in last hour)
    if txns_buys > 0 and txns_sells >= 0:
        buy_ratio = txns_buys / (txns_buys + txns_sells + 1)
        if buy_ratio > 0.65:
            score += 1

    # Volume/FDV ratio (high ratio = real interest)
    if fdv > 0 and (volume_24h / fdv) > 0.15:
        score += 1

    if score >= BUY_SIGNAL_MIN_SCORE:
        signal = "buy now"
    elif score >= 2:
        signal = "hold"
    else:
        signal = "sell"

    return score, signal


def get_signals():
    addresses = fetch_trending_addresses()
    results = []

    for addr in addresses:
        try:
            pair = fetch_best_pair(addr)
        except Exception as e:
            print(f"  Skipping {addr}: {e}")
            continue
        if not pair:
            continue

        score, signal = score_pair(pair)
        base = pair.get("baseToken") or {}

        results.append({
            "name": base.get("name", "Unknown"),
            "symbol": base.get("symbol", "?"),
            "address": base.get("address", addr),
            "chain": pair.get("chainId", "unknown"),
            "price_usd": pair.get("priceUsd", "0"),
            "price_change_1h": _f(pair, "priceChange", "h1"),
            "price_change_24h": _f(pair, "priceChange", "h24"),
            "volume_24h": _f(pair, "volume", "h24"),
            "liquidity_usd": _f(pair, "liquidity", "usd"),
            "fdv": _f(pair, "fdv"),
            "signal": signal,
            "score": score,
            "url": pair.get("url", ""),
            "timestamp": datetime.utcnow().isoformat(),
        })

    return results
