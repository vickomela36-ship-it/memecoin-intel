"""Buy/sell signal logic using DexScreener API (no API key required)."""
from __future__ import annotations

import requests

from config import MIN_LIQUIDITY_USD, PRICE_CHANGE_MIN_PCT, VOL_LIQ_RATIO_MIN, WATCHED_PAIRS

_BASE = "https://api.dexscreener.com"
_TIMEOUT = 10


def _get_pair(pair_address: str) -> dict | None:
    try:
        r = requests.get(f"{_BASE}/latest/dex/pairs/solana/{pair_address}", timeout=_TIMEOUT)
        r.raise_for_status()
        pairs = r.json().get("pairs") or []
        return pairs[0] if pairs else None
    except Exception as exc:
        print(f"[signals] fetch error for {pair_address}: {exc}")
        return None


def _get_trending_pairs() -> list[dict]:
    """Pull top-boosted Solana tokens from DexScreener and return their best pair."""
    try:
        r = requests.get(f"{_BASE}/token-boosts/top/v1", timeout=_TIMEOUT)
        r.raise_for_status()
        boosted = [t for t in r.json() if t.get("chainId") == "solana"]
    except Exception as exc:
        print(f"[signals] trending fetch error: {exc}")
        return []

    pairs: list[dict] = []
    for token in boosted[:20]:
        addr = token.get("tokenAddress", "")
        if not addr:
            continue
        try:
            r = requests.get(f"{_BASE}/latest/dex/tokens/{addr}", timeout=_TIMEOUT)
            r.raise_for_status()
            token_pairs = r.json().get("pairs") or []
            if token_pairs:
                # Prefer the highest-liquidity pair
                best = max(token_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                pairs.append(best)
        except Exception:
            pass
    return pairs


def _score(pair: dict) -> tuple[str, dict]:
    price_change = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    vol_liq = round(volume_24h / liquidity, 2) if liquidity > 0 else 0.0

    metrics = {
        "token_name": pair.get("baseToken", {}).get("name", "Unknown"),
        "symbol": pair.get("baseToken", {}).get("symbol", "???"),
        "pair_address": pair.get("pairAddress", ""),
        "price_usd": pair.get("priceUsd", "0"),
        "price_change_24h": price_change,
        "volume_24h_usd": volume_24h,
        "liquidity_usd": liquidity,
        "vol_liq_ratio": vol_liq,
        "dexscreener_url": pair.get("url", ""),
    }

    if liquidity < MIN_LIQUIDITY_USD:
        return "hold", metrics
    if price_change >= PRICE_CHANGE_MIN_PCT and vol_liq >= VOL_LIQ_RATIO_MIN:
        return "buy now", metrics
    if price_change <= -15.0:
        return "sell", metrics
    return "hold", metrics


def get_signals() -> list[dict]:
    """Return signal dicts for all watched (or trending) pairs."""
    raw_pairs: list[dict] = []

    if WATCHED_PAIRS:
        for addr in WATCHED_PAIRS:
            p = _get_pair(addr)
            if p:
                raw_pairs.append(p)
    else:
        raw_pairs = _get_trending_pairs()

    results = []
    for pair in raw_pairs:
        signal, metrics = _score(pair)
        results.append({"signal": signal, **metrics})
    return results


if __name__ == "__main__":
    import json
    print(json.dumps(get_signals(), indent=2))
