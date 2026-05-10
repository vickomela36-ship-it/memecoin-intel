"""
Memecoin buy/sell signal logic using DexScreener API.
Signals are based on volume/liquidity ratio, 24h price change, and minimum liquidity thresholds.
"""
import json
import requests
from datetime import datetime, timezone

DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
DEXSCREENER_BOOSTED_URL = "https://api.dexscreener.com/token-boosts/top/v1"

SUPPORTED_CHAINS = {"solana", "ethereum", "bsc", "base"}

MIN_LIQUIDITY_USD = 10_000
MIN_VOLUME_24H_USD = 50_000
MIN_VOL_LIQ_RATIO = 2.0
MIN_PRICE_CHANGE_24H_PCT = 10.0

SEARCH_TERMS = ["meme", "pepe", "doge", "shib", "moon", "inu", "baby", "bonk"]


def _fetch_pairs_by_term(term: str) -> list[dict]:
    try:
        resp = requests.get(
            DEXSCREENER_SEARCH_URL,
            params={"q": term},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("pairs", [])
    except Exception:
        return []


def fetch_candidate_pairs() -> list[dict]:
    """Collect candidate pairs from DexScreener across multiple search terms."""
    seen_addresses = set()
    pairs = []
    for term in SEARCH_TERMS:
        for pair in _fetch_pairs_by_term(term):
            addr = pair.get("pairAddress", "")
            if addr and addr not in seen_addresses:
                seen_addresses.add(addr)
                pairs.append(pair)
    return pairs


def _evaluate_pair(pair: dict) -> dict | None:
    """Return a signal dict if the pair meets buy criteria, else None."""
    try:
        chain = pair.get("chainId", "")
        if chain not in SUPPORTED_CHAINS:
            return None

        liquidity = (pair.get("liquidity") or {}).get("usd") or 0
        volume_24h = (pair.get("volume") or {}).get("h24") or 0
        price_change_24h = (pair.get("priceChange") or {}).get("h24") or 0
        price_usd = pair.get("priceUsd") or "0"

        if liquidity < MIN_LIQUIDITY_USD:
            return None
        if volume_24h < MIN_VOLUME_24H_USD:
            return None

        vol_liq_ratio = volume_24h / liquidity if liquidity > 0 else 0
        if vol_liq_ratio < MIN_VOL_LIQ_RATIO:
            return None
        if price_change_24h < MIN_PRICE_CHANGE_24H_PCT:
            return None

        base = pair.get("baseToken") or {}
        return {
            "signal": "buy now",
            "token_name": base.get("name") or "Unknown",
            "symbol": base.get("symbol") or "",
            "chain": chain,
            "pair_address": pair.get("pairAddress") or "",
            "price_usd": str(price_usd),
            "price_change_24h_pct": round(float(price_change_24h), 2),
            "volume_24h_usd": round(float(volume_24h), 2),
            "liquidity_usd": round(float(liquidity), 2),
            "vol_liq_ratio": round(vol_liq_ratio, 2),
            "dexscreener_url": pair.get("url") or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        return None


def get_buy_signals() -> list[dict]:
    """Return all pairs currently meeting 'buy now' criteria."""
    pairs = fetch_candidate_pairs()
    signals = []
    seen = set()
    for pair in pairs:
        result = _evaluate_pair(pair)
        if result and result["pair_address"] not in seen:
            seen.add(result["pair_address"])
            signals.append(result)
    return signals


if __name__ == "__main__":
    results = get_buy_signals()
    print(json.dumps(results, indent=2))
    print(f"\n{len(results)} buy now signal(s) found")
