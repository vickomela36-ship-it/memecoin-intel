"""
Fetches trending Solana tokens from DexScreener and returns 'buy now' signals.
Criteria: >15% 24h gain, >$100k liquidity, >$500k 24h volume, buy txns > sell txns (1h).
"""
import requests
from datetime import datetime, timezone

DEXSCREENER = "https://api.dexscreener.com"


def _get(url, timeout=15):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _safe_float(value, default=0.0):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def get_trending_pairs(chain="solana", limit=30):
    """Pull latest profiled tokens on DexScreener, return their pair data."""
    profiles = _get(f"{DEXSCREENER}/token-profiles/latest/v1")
    if not isinstance(profiles, list):
        return []

    addresses = [
        p["tokenAddress"]
        for p in profiles
        if p.get("chainId", "").lower() == chain and p.get("tokenAddress")
    ][:limit]

    if not addresses:
        return []

    batch = ",".join(addresses)
    data = _get(f"{DEXSCREENER}/latest/dex/tokens/{batch}")
    return data.get("pairs", [])


def _evaluate(pair):
    """Return (is_buy_signal, signal_dict | None)."""
    if pair.get("chainId", "").lower() != "solana":
        return False, None

    price_change_24h = _safe_float(pair.get("priceChange", {}).get("h24"))
    volume_24h = _safe_float(pair.get("volume", {}).get("h24"))
    liquidity = _safe_float((pair.get("liquidity") or {}).get("usd"))
    txns_h1 = pair.get("txns", {}).get("h1", {})
    buys_h1 = int(_safe_float(txns_h1.get("buys")))
    sells_h1 = int(_safe_float(txns_h1.get("sells")))

    if not (
        price_change_24h > 15
        and liquidity > 100_000
        and volume_24h > 500_000
        and buys_h1 > sells_h1
    ):
        return False, None

    base = pair.get("baseToken", {})
    pair_address = pair.get("pairAddress", "")
    vol_liq_ratio = round(volume_24h / max(liquidity, 1), 2)

    return True, {
        "signal": "buy now",
        "token": base.get("name", "Unknown"),
        "symbol": base.get("symbol", "???"),
        "price_usd": pair.get("priceUsd", "N/A"),
        "price_change_24h": price_change_24h,
        "volume_24h_usd": volume_24h,
        "liquidity_usd": liquidity,
        "vol_liq_ratio": vol_liq_ratio,
        "buys_h1": buys_h1,
        "sells_h1": sells_h1,
        "pair_address": pair_address,
        "dexscreener_url": f"https://dexscreener.com/solana/{pair_address}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_buy_signals():
    """Main entry point. Returns list of buy-signal dicts."""
    pairs = get_trending_pairs()
    signals = []
    for pair in pairs:
        is_buy, sig = _evaluate(pair)
        if is_buy:
            signals.append(sig)
    return signals


if __name__ == "__main__":
    import json
    results = get_buy_signals()
    print(json.dumps(results, indent=2))
    print(f"\nTotal buy signals: {len(results)}")
