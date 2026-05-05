"""
Buy / hold / sell signal generation for tracked memecoins.

Data source: CoinGecko public API (no key required; optional key raises rate limits).
Signal logic is momentum + volume-surge based, tuned for memecoins.
"""

import logging
import time
from dataclasses import dataclass

import requests

import config

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    coin: str         # ticker symbol, e.g. "DOGE"
    action: str       # "buy now" | "hold" | "sell"
    price: float
    confidence: float # 0.0 – 1.0
    notes: str


# ── CoinGecko helpers ─────────────────────────────────────────────────────────

def _headers() -> dict:
    h = {"accept": "application/json"}
    if config.COINGECKO_API_KEY:
        h["x-cg-demo-api-key"] = config.COINGECKO_API_KEY
    return h


def fetch_market_data(coin_ids: list[str]) -> list[dict]:
    """Return CoinGecko /coins/markets payload for the given IDs."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "order": "market_cap_desc",
        "per_page": len(coin_ids),
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d",
    }
    resp = requests.get(url, params=params, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Signal computation ────────────────────────────────────────────────────────

def compute_signal(data: dict) -> Signal:
    """Derive a Signal from a single CoinGecko market-data record."""
    symbol = (data.get("symbol") or "?").upper()
    price = float(data.get("current_price") or 0)
    change_1h = float(data.get("price_change_percentage_1h_in_currency") or 0)
    change_24h = float(data.get("price_change_percentage_24h_in_currency") or 0)
    change_7d = float(data.get("price_change_percentage_7d_in_currency") or 0)
    volume_24h = float(data.get("total_volume") or 0)
    market_cap = float(data.get("market_cap") or 1) or 1

    vol_to_mcap = volume_24h / market_cap

    action = "hold"
    confidence = 0.0
    reasons: list[str] = []

    if change_24h >= config.SELL_CHANGE_24H:
        # Overextended – take profit
        action = "sell"
        confidence = 0.75
        reasons.append(f"overextended +{change_24h:.1f}% 24h")

    elif (
        config.BUY_MIN_CHANGE_24H <= change_24h <= config.BUY_MAX_CHANGE_24H
        and vol_to_mcap >= config.BUY_MIN_VOL_TO_MCAP
        and change_1h > 0
    ):
        # Momentum buy: moderate 24h gain + high volume + still rising on 1h
        action = "buy now"
        confidence = min(0.95, 0.45 + vol_to_mcap * 0.6 + change_24h * 0.005)
        reasons.append(
            f"+{change_24h:.1f}% 24h, vol/mcap={vol_to_mcap:.2f}, +{change_1h:.2f}% 1h"
        )

    elif vol_to_mcap >= 0.30 and change_1h >= 2.0:
        # Volume-surge buy even without a big 24h move (early breakout)
        action = "buy now"
        confidence = min(0.80, 0.40 + vol_to_mcap * 0.5)
        reasons.append(
            f"volume surge vol/mcap={vol_to_mcap:.2f}, +{change_1h:.2f}% 1h"
        )

    reasons.append(f"7d: {change_7d:+.1f}%")

    return Signal(
        coin=symbol,
        action=action,
        price=price,
        confidence=round(confidence, 2),
        notes="; ".join(reasons),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def get_signals() -> list[Signal]:
    """Fetch market data and return a Signal for every tracked coin."""
    raw = fetch_market_data(config.TRACKED_COINS)
    signals: list[Signal] = []
    for item in raw:
        try:
            signals.append(compute_signal(item))
        except Exception as exc:
            logger.warning("Failed to compute signal for %s: %s", item.get("id"), exc)
        time.sleep(0.05)  # stay well within rate limits
    return signals
