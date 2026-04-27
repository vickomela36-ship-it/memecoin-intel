"""Buy/sell signal logic based on CoinGecko market data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import requests

import config

log = logging.getLogger(__name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"


@dataclass
class Signal:
    coin: str
    signal: str          # "buy now" | "hold" | "sell"
    confidence: str      # "high" | "medium" | "low"
    price_usd: float
    price_change_1h: float
    volume_24h: float
    notes: str


def _fetch_market_data(token_ids: List[str]) -> List[dict]:
    params = {
        "vs_currency": "usd",
        "ids": ",".join(token_ids),
        "price_change_percentage": "1h",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
    }
    resp = requests.get(COINGECKO_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _classify(price_change_1h: float, volume_24h: float) -> tuple[str, str, str]:
    """Return (signal, confidence, notes)."""
    if volume_24h < config.MIN_VOLUME_USD:
        return "hold", "low", f"Volume too low (${volume_24h:,.0f})"

    if price_change_1h >= config.BUY_NOW_HIGH_THRESHOLD:
        return (
            "buy now",
            "high",
            f"+{price_change_1h:.2f}% in 1 h — strong upward momentum",
        )
    if price_change_1h >= config.BUY_NOW_MED_THRESHOLD:
        return (
            "buy now",
            "medium",
            f"+{price_change_1h:.2f}% in 1 h — moderate upward momentum",
        )
    if price_change_1h <= config.SELL_THRESHOLD:
        return (
            "sell",
            "high",
            f"{price_change_1h:.2f}% in 1 h — sharp decline",
        )

    return "hold", "low", f"{price_change_1h:.2f}% in 1 h — no clear edge"


def get_signals() -> List[Signal]:
    """Fetch market data and return a Signal for every configured token."""
    try:
        data = _fetch_market_data(config.TOKENS)
    except Exception as exc:
        log.error("CoinGecko fetch failed: %s", exc)
        return []

    results: List[Signal] = []
    for row in data:
        coin = row.get("id", "unknown")
        price_usd = row.get("current_price") or 0.0
        price_change_1h = row.get("price_change_percentage_1h_in_currency") or 0.0
        volume_24h = row.get("total_volume") or 0.0

        signal, confidence, notes = _classify(price_change_1h, volume_24h)
        results.append(
            Signal(
                coin=row.get("name", coin),
                signal=signal,
                confidence=confidence,
                price_usd=price_usd,
                price_change_1h=price_change_1h,
                volume_24h=volume_24h,
                notes=notes,
            )
        )
        log.info("[%s] %s (%s) — $%.6f, 1h: %+.2f%%", signal.upper(), coin, confidence, price_usd, price_change_1h)

    return results
