import requests
from config import (
    CHAINS,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_24H_USD,
    MIN_VOL_LIQ_RATIO,
    MIN_PRICE_CHANGE_24H,
)

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"


def _fetch_pairs(chain: str) -> list[dict]:
    try:
        resp = requests.get(DEXSCREENER_SEARCH, params={"q": chain}, timeout=15)
        resp.raise_for_status()
        return resp.json().get("pairs") or []
    except Exception as exc:
        print(f"[signals] fetch error for {chain}: {exc}")
        return []


def _is_buy_now(pair: dict) -> bool:
    liquidity = (pair.get("liquidity") or {}).get("usd") or 0
    volume_24h = (pair.get("volume") or {}).get("h24") or 0
    change_24h = (pair.get("priceChange") or {}).get("h24") or 0

    if liquidity < MIN_LIQUIDITY_USD:
        return False
    if volume_24h < MIN_VOLUME_24H_USD:
        return False
    if liquidity and (volume_24h / liquidity) < MIN_VOL_LIQ_RATIO:
        return False
    if change_24h < MIN_PRICE_CHANGE_24H:
        return False
    return True


def get_buy_signals() -> list[dict]:
    """Return all pairs across configured chains that meet buy-now criteria."""
    results = []
    seen: set[str] = set()

    for chain in CHAINS:
        for pair in _fetch_pairs(chain):
            addr = pair.get("pairAddress", "")
            if not addr or addr in seen:
                continue
            seen.add(addr)

            if not _is_buy_now(pair):
                continue

            liquidity = (pair.get("liquidity") or {}).get("usd") or 0
            volume_24h = (pair.get("volume") or {}).get("h24") or 0

            results.append({
                "token_name": (pair.get("baseToken") or {}).get("name", "Unknown"),
                "symbol": (pair.get("baseToken") or {}).get("symbol", ""),
                "price_usd": pair.get("priceUsd", ""),
                "price_change_24h": (pair.get("priceChange") or {}).get("h24", 0),
                "volume_24h_usd": volume_24h,
                "liquidity_usd": liquidity,
                "vol_liq_ratio": round(volume_24h / liquidity, 2) if liquidity else 0,
                "pair_address": addr,
                "dexscreener_url": pair.get("url", ""),
                "chain": pair.get("chainId", chain),
            })

    return results
