"""Buy/sell signal logic using DexScreener trending data."""
import json
from datetime import datetime, timezone

import requests

DEXSCREENER_BASE = "https://api.dexscreener.com"
TARGET_CHAIN = "solana"
MIN_VOLUME_USD = 50_000
MIN_LIQUIDITY_USD = 10_000


def _fetch_top_boosted_addresses():
    resp = requests.get(f"{DEXSCREENER_BASE}/token-boosts/top/v1", timeout=15)
    resp.raise_for_status()
    items = resp.json()
    return [
        item["tokenAddress"]
        for item in items
        if item.get("chainId") == TARGET_CHAIN and item.get("tokenAddress")
    ]


def _fetch_pairs_for_token(address):
    resp = requests.get(
        f"{DEXSCREENER_BASE}/latest/dex/tokens/{address}", timeout=10
    )
    resp.raise_for_status()
    pairs = resp.json().get("pairs") or []
    pairs.sort(
        key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0),
        reverse=True,
    )
    return pairs[0] if pairs else None


def _compute_signal(pair):
    """
    BUY NOW: strong cross-timeframe momentum + high volume/liquidity ratio.
    SELL:    sharp multi-hour decline.
    HOLD:    everything else.
    """
    pc = pair.get("priceChange") or {}
    vol = pair.get("volume") or {}
    liq = pair.get("liquidity") or {}

    change_1h = float(pc.get("h1", 0) or 0)
    change_6h = float(pc.get("h6", 0) or 0)
    change_24h = float(pc.get("h24", 0) or 0)
    volume_24h = float(vol.get("h24", 0) or 0)
    liquidity = float(liq.get("usd", 0) or 0)
    market_cap = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)

    vol_liq_ratio = volume_24h / liquidity if liquidity > 0 else 0

    score = 0
    if change_1h > 5:
        score += 2
    if change_6h > 10:
        score += 2
    if change_24h > 20:
        score += 3
    if vol_liq_ratio > 2:
        score += 2
    if 0 < market_cap < 50_000_000:
        score += 1

    if score >= 6:
        return "buy now"
    if change_24h < -20 or change_6h < -15:
        return "sell"
    return "hold"


def get_signals():
    """Return a list of signal dicts for trending Solana memecoins."""
    addresses = _fetch_top_boosted_addresses()
    now = datetime.now(timezone.utc).isoformat()
    results = []
    seen = set()

    for addr in addresses:
        if addr in seen:
            continue
        seen.add(addr)
        try:
            pair = _fetch_pairs_for_token(addr)
            if not pair:
                continue

            vol_24h = float((pair.get("volume") or {}).get("h24", 0) or 0)
            liq_usd = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
            if vol_24h < MIN_VOLUME_USD or liq_usd < MIN_LIQUIDITY_USD:
                continue

            base = pair.get("baseToken") or {}
            pc = pair.get("priceChange") or {}

            results.append({
                "coin": base.get("symbol", "UNKNOWN"),
                "name": base.get("name", ""),
                "signal": _compute_signal(pair),
                "price_usd": float(pair.get("priceUsd", 0) or 0),
                "price_change_24h": float(pc.get("h24", 0) or 0),
                "volume_24h_usd": vol_24h,
                "market_cap_usd": float(
                    pair.get("marketCap", 0) or pair.get("fdv", 0) or 0
                ),
                "liquidity_usd": liq_usd,
                "source": "DexScreener",
                "pair_url": pair.get("url", ""),
                "detected_at": now,
            })
        except Exception:
            continue

    return results


if __name__ == "__main__":
    signals = get_signals()
    buy_now = [s for s in signals if s["signal"] == "buy now"]
    print(json.dumps({"total_checked": len(signals), "buy_now": buy_now}, indent=2))
