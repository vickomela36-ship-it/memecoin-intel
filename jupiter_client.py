"""
Jupiter / Birdeye API client — price feeds, OHLCV candles, and volume data.
Jupiter Price API v2 for real-time prices.
Birdeye for OHLCV history and volume breakdowns (buy/sell).
"""

import time
import requests
from config import (
    JUPITER_API_KEY,
    JUPITER_PRICE_API,
    JUPITER_TOKEN_API,
    JUPITER_TOKEN_LIST_API,
    BIRDEYE_API_KEY,
    BIRDEYE_API_BASE,
)


def _jup_headers() -> dict:
    return {"Authorization": f"Bearer {JUPITER_API_KEY}"}


# ── Jupiter Price API ────────────────────────────────────────────────────────

def get_prices(mint_addresses: list[str]) -> dict[str, float]:
    """
    Batch-fetch USD prices from Jupiter Price API v2.
    Returns {mint_address: price_usd}.
    """
    if not mint_addresses:
        return {}

    # Jupiter supports up to 100 mints per call
    prices = {}
    for i in range(0, len(mint_addresses), 100):
        batch = mint_addresses[i : i + 100]
        params = {"ids": ",".join(batch)}
        try:
            resp = requests.get(JUPITER_PRICE_API, params=params, headers=_jup_headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            for mint, info in data.items():
                if info and info.get("price"):
                    prices[mint] = float(info["price"])
        except requests.RequestException as e:
            print(f"[Jupiter] Price fetch error: {e}")
    return prices


def get_price(mint_address: str) -> float | None:
    """Get a single token's USD price."""
    result = get_prices([mint_address])
    return result.get(mint_address)


def get_verified_token_list() -> list[dict]:
    """Fetch Jupiter's verified token list (useful for finding active tokens)."""
    try:
        resp = requests.get(JUPITER_TOKEN_LIST_API, headers=_jup_headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[Jupiter] Token list error: {e}")
        return []


def get_token_info(mint_address: str) -> dict | None:
    """
    Fetch token metadata from Jupiter Token API v1.
    Returns name, symbol, decimals, daily volume, and tags.
    """
    url = f"{JUPITER_TOKEN_API}/token/{mint_address}"
    try:
        resp = requests.get(url, headers=_jup_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[Jupiter] Token info error for {mint_address}: {e}")
        return None


def get_token_daily_volume(mint_address: str) -> float | None:
    """Get 24h USD volume for a token directly from Jupiter."""
    url = f"{JUPITER_TOKEN_API}/token/{mint_address}/volume"
    try:
        resp = requests.get(url, headers=_jup_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("volume24h") or data.get("volume") or 0) or None
    except requests.RequestException as e:
        print(f"[Jupiter] Volume error for {mint_address}: {e}")
        return None


# ── Birdeye API (OHLCV + Volume) ────────────────────────────────────────────

def _birdeye_headers() -> dict:
    return {
        "X-API-KEY": BIRDEYE_API_KEY,
        "x-chain": "solana",
    }


def get_ohlcv(mint_address: str, interval: str = "1H", limit: int = 24) -> list[dict]:
    """
    Fetch OHLCV candles from Birdeye.
    interval: "1m", "5m", "15m", "30m", "1H", "4H", "1D"
    Returns list of candles sorted oldest → newest:
        [{unixTime, open, high, low, close, volume}, ...]
    """
    interval_map = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1H": "1H", "4H": "4H", "1D": "1D",
    }
    birdeye_interval = interval_map.get(interval, "1H")

    now = int(time.time())
    # Rough seconds per interval
    secs = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
            "1H": 3600, "4H": 14400, "1D": 86400}
    time_from = now - secs.get(interval, 3600) * limit

    url = f"{BIRDEYE_API_BASE}/defi/ohlcv"
    params = {
        "address": mint_address,
        "type": birdeye_interval,
        "time_from": time_from,
        "time_to": now,
    }
    try:
        resp = requests.get(url, headers=_birdeye_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        items = data.get("items", [])
        return sorted(items, key=lambda c: c.get("unixTime", 0))
    except requests.RequestException as e:
        print(f"[Birdeye] OHLCV error for {mint_address}: {e}")
        return []


def get_token_overview(mint_address: str) -> dict | None:
    """
    Birdeye token overview — includes 24h volume, price change,
    liquidity, holder count, etc.
    """
    url = f"{BIRDEYE_API_BASE}/defi/token_overview"
    params = {"address": mint_address}
    try:
        resp = requests.get(url, headers=_birdeye_headers(), params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data")
    except requests.RequestException as e:
        print(f"[Birdeye] Overview error for {mint_address}: {e}")
        return None


def get_trade_volume_breakdown(mint_address: str) -> dict | None:
    """
    Get buy vs sell volume breakdown from Birdeye.
    Returns {buy_volume, sell_volume, total_volume, buy_ratio}.
    """
    overview = get_token_overview(mint_address)
    if not overview:
        return None

    buy_vol = overview.get("buy24h", 0) or 0
    sell_vol = overview.get("sell24h", 0) or 0
    total = buy_vol + sell_vol

    return {
        "buy_volume": buy_vol,
        "sell_volume": sell_vol,
        "total_volume": total,
        "buy_ratio": buy_vol / total if total > 0 else 0.5,
    }


def get_trending_tokens(sort_by: str = "volume24hUSD", limit: int = 50) -> list[dict]:
    """
    Fetch trending tokens from Birdeye sorted by volume.
    Useful for finding high-volume tokens to scan.
    """
    url = f"{BIRDEYE_API_BASE}/defi/token_trending"
    params = {"sort_by": sort_by, "sort_type": "desc", "offset": 0, "limit": limit}
    try:
        resp = requests.get(url, headers=_birdeye_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data.get("tokens", [])
    except requests.RequestException as e:
        print(f"[Birdeye] Trending error: {e}")
        return []
