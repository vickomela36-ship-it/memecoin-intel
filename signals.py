"""Buy/sell signal logic based on RSI, volume spikes, and price momentum."""

import time
import requests
import numpy as np
from typing import Optional
from config import (
    TRACKED_COINS, RSI_BUY_THRESHOLD, RSI_SELL_THRESHOLD,
    VOLUME_SPIKE_MULTIPLIER, PRICE_DIP_THRESHOLD,
    COINGECKO_API_KEY, COINGECKO_BASE,
)

HEADERS = {"x-cg-demo-api-key": COINGECKO_API_KEY} if COINGECKO_API_KEY else {}


def _get(path: str, params: dict = None) -> dict:
    url = f"{COINGECKO_BASE}{path}"
    for attempt in range(3):
        resp = requests.get(url, params=params or {}, headers=HEADERS, timeout=15)
        if resp.status_code == 429:
            time.sleep(60)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"CoinGecko request failed after retries: {path}")


def _rsi(prices: list[float], period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def fetch_coin_data(coin_id: str) -> dict:
    data = _get(f"/coins/{coin_id}", params={
        "localization": "false",
        "tickers": "false",
        "community_data": "false",
        "developer_data": "false",
    })
    market = data.get("market_data", {})
    return {
        "id": coin_id,
        "name": data.get("name", coin_id),
        "symbol": data.get("symbol", "").upper(),
        "price": market.get("current_price", {}).get("usd", 0),
        "change_24h": market.get("price_change_percentage_24h", 0) or 0,
        "volume_24h": market.get("total_volume", {}).get("usd", 0),
        "market_cap": market.get("market_cap", {}).get("usd", 0),
    }


def fetch_price_history(coin_id: str, days: int = 30) -> list[float]:
    data = _get(f"/coins/{coin_id}/market_chart", params={
        "vs_currency": "usd",
        "days": days,
        "interval": "daily",
    })
    return [p[1] for p in data.get("prices", [])]


def fetch_volume_history(coin_id: str, days: int = 8) -> list[float]:
    data = _get(f"/coins/{coin_id}/market_chart", params={
        "vs_currency": "usd",
        "days": days,
        "interval": "daily",
    })
    return [v[1] for v in data.get("total_volumes", [])]


def classify_signal(rsi: Optional[float], change_24h: float, volume_spike: float) -> tuple[str, str]:
    """Returns (signal, confidence)."""
    buy_points = 0
    if rsi is not None and rsi < RSI_BUY_THRESHOLD:
        buy_points += 2
    if change_24h <= PRICE_DIP_THRESHOLD:
        buy_points += 1
    if volume_spike >= VOLUME_SPIKE_MULTIPLIER:
        buy_points += 1

    sell_points = 0
    if rsi is not None and rsi > RSI_SELL_THRESHOLD:
        sell_points += 2
    if change_24h >= 20:
        sell_points += 1

    if buy_points >= 3:
        confidence = "high" if buy_points >= 4 else "medium"
        return "buy now", confidence
    if sell_points >= 2:
        return "sell", "medium"
    return "hold", "low"


def analyze_coin(coin_id: str) -> dict:
    coin = fetch_coin_data(coin_id)
    time.sleep(1.2)  # stay under free-tier rate limit

    prices = fetch_price_history(coin_id, days=30)
    time.sleep(1.2)

    volumes = fetch_volume_history(coin_id, days=8)
    time.sleep(1.2)

    rsi = _rsi(prices)

    avg_volume_7d = np.mean(volumes[:-1]) if len(volumes) > 1 else 0
    volume_spike = (coin["volume_24h"] / avg_volume_7d) if avg_volume_7d > 0 else 0

    signal, confidence = classify_signal(rsi, coin["change_24h"], volume_spike)

    return {
        **coin,
        "rsi": rsi,
        "volume_spike": round(volume_spike, 2),
        "signal": signal,
        "confidence": confidence,
    }


def run_all() -> list[dict]:
    results = []
    for coin_id in TRACKED_COINS:
        coin_id = coin_id.strip()
        if not coin_id:
            continue
        try:
            result = analyze_coin(coin_id)
            results.append(result)
            print(f"  {result['name']:20s}  RSI={result['rsi']}  signal={result['signal']:8s}  conf={result['confidence']}")
        except Exception as exc:
            print(f"  [ERROR] {coin_id}: {exc}")
    return results
