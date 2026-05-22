"""Buy/sell signal logic — queries CoinGecko trending coins and scores them."""

import requests
from datetime import datetime, timezone

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
_HEADERS = {"Accept": "application/json"}


def _fetch_trending_ids(limit: int = 15) -> list[str]:
    resp = requests.get(
        f"{COINGECKO_BASE}/search/trending",
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    coins = resp.json().get("coins", [])
    return [c["item"]["id"] for c in coins[:limit]]


def _fetch_market_data(coin_ids: list[str]) -> list[dict]:
    resp = requests.get(
        f"{COINGECKO_BASE}/coins/markets",
        headers=_HEADERS,
        params={
            "vs_currency": "usd",
            "ids": ",".join(coin_ids),
            "order": "market_cap_desc",
            "per_page": 50,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _score(coin: dict, min_change: float, min_vol_ratio: float, min_mcap: float) -> str:
    change   = coin.get("price_change_percentage_24h") or 0.0
    volume   = coin.get("total_volume") or 0.0
    mcap     = coin.get("market_cap") or 0.0

    if mcap < min_mcap:
        return "hold"
    vol_ratio = volume / mcap if mcap else 0.0

    if change >= min_change and vol_ratio >= min_vol_ratio:
        return "buy now"
    if change <= -10:
        return "sell"
    return "hold"


def get_signals(
    min_price_change: float = 15.0,
    min_vol_to_mcap: float  = 0.10,
    min_market_cap: float   = 1_000_000.0,
) -> list[dict]:
    """Return all detected signals for today's trending coins."""
    coin_ids = _fetch_trending_ids()
    if not coin_ids:
        return []

    market_data = _fetch_market_data(coin_ids)
    now = datetime.now(timezone.utc).isoformat()

    results = []
    for coin in market_data:
        signal = _score(coin, min_price_change, min_vol_to_mcap, min_market_cap)
        results.append({
            "coin":             coin.get("name", ""),
            "symbol":           (coin.get("symbol") or "").upper(),
            "signal":           signal,
            "price_usd":        coin.get("current_price") or 0.0,
            "price_change_24h": coin.get("price_change_percentage_24h") or 0.0,
            "market_cap_usd":   coin.get("market_cap") or 0.0,
            "volume_24h_usd":   coin.get("total_volume") or 0.0,
            "detected_at":      now,
            "source":           "CoinGecko Trending",
            "coingecko_id":     coin.get("id", ""),
        })

    return results


def get_buy_now_signals(**kwargs) -> list[dict]:
    return [s for s in get_signals(**kwargs) if s["signal"] == "buy now"]
