"""
Buy/sell signal logic based on CoinGecko market data.

Signal criteria for 'buy now':
  - 24h price change >= BUY_PRICE_CHANGE_MIN_PCT
  - 24h volume >= BUY_VOLUME_SPIKE_MULTIPLIER * 7-day average volume
  - Market cap <= BUY_MARKET_CAP_MAX_USD
"""

import time
import requests
from config import (
    TRACKED_TOKENS,
    BUY_VOLUME_SPIKE_MULTIPLIER,
    BUY_PRICE_CHANGE_MIN_PCT,
    BUY_MARKET_CAP_MAX_USD,
    COINGECKO_API_KEY,
)


COINGECKO_BASE = "https://api.coingecko.com/api/v3"
HEADERS = {"x-cg-demo-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}


def _fetch_market_data(token_ids: list[str]) -> list[dict]:
    """Fetch current market data for a batch of tokens."""
    ids = ",".join(token_ids)
    resp = requests.get(
        f"{COINGECKO_BASE}/coins/markets",
        params={
            "vs_currency": "usd",
            "ids": ids,
            "order": "market_cap_desc",
            "sparkline": "false",
            "price_change_percentage": "24h",
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_7d_avg_volume(token_id: str) -> float:
    """Return the average 24h volume over the past 7 days."""
    resp = requests.get(
        f"{COINGECKO_BASE}/coins/{token_id}/market_chart",
        params={"vs_currency": "usd", "days": 7, "interval": "daily"},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    volumes = [v[1] for v in data.get("total_volumes", [])]
    return sum(volumes) / len(volumes) if volumes else 0.0


def evaluate(token: dict, avg_volume_7d: float) -> str:
    """Return 'buy now', 'hold', or 'sell' for a single token."""
    price_change = token.get("price_change_percentage_24h") or 0.0
    volume_24h = token.get("total_volume") or 0.0
    market_cap = token.get("market_cap") or float("inf")

    volume_spike = (volume_24h >= BUY_VOLUME_SPIKE_MULTIPLIER * avg_volume_7d) if avg_volume_7d else False
    strong_momentum = price_change >= BUY_PRICE_CHANGE_MIN_PCT
    small_cap = market_cap <= BUY_MARKET_CAP_MAX_USD

    if strong_momentum and volume_spike and small_cap:
        return "buy now"
    if price_change <= -10.0:
        return "sell"
    return "hold"


def get_signals() -> list[dict]:
    """
    Return a list of signal dicts for all tracked tokens.

    Each dict contains:
      token, signal, price, market_cap, volume_24h, price_change_24h
    """
    results = []

    market_data = _fetch_market_data(TRACKED_TOKENS)

    for token in market_data:
        token_id = token["id"]
        time.sleep(1.2)  # respect free-tier rate limit (50 req/min)
        avg_vol = _fetch_7d_avg_volume(token_id)

        signal = evaluate(token, avg_vol)
        results.append({
            "token": token.get("symbol", token_id).upper(),
            "token_id": token_id,
            "signal": signal,
            "price": token.get("current_price") or 0.0,
            "market_cap": token.get("market_cap") or 0.0,
            "volume_24h": token.get("total_volume") or 0.0,
            "price_change_24h": token.get("price_change_percentage_24h") or 0.0,
        })

    return results
