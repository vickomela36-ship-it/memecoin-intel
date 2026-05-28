"""
Buy/sell signal logic for tracked memecoins.

Score (0-100):
  - Price vs 24h change      (30 pts)
  - Volume surge             (25 pts)
  - RSI-like momentum        (25 pts)
  - Market cap rank trend    (20 pts)

Signal:
  >= 60  → buy now
  <= 35  → sell
  else   → hold
"""

import time
import requests
from dataclasses import dataclass, field
from typing import List

from config import (
    COINGECKO_API_KEY,
    TRACKED_COINS,
    BUY_SCORE_THRESHOLD,
    SELL_SCORE_THRESHOLD,
)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


@dataclass
class CoinSignal:
    coin_id: str
    name: str
    symbol: str
    price_usd: float
    price_change_24h: float     # percent
    volume_change_24h: float    # percent vs prev day avg estimate
    score: int
    signal: str                 # "buy now" | "hold" | "sell"
    notes: List[str] = field(default_factory=list)


def _headers() -> dict:
    h = {"accept": "application/json"}
    if COINGECKO_API_KEY:
        h["x-cg-pro-api-key"] = COINGECKO_API_KEY
    return h


def _fetch_market_data(coin_ids: List[str]) -> List[dict]:
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "order": "market_cap_desc",
        "per_page": len(coin_ids),
        "page": 1,
        "price_change_percentage": "1h,24h,7d",
        "sparkline": False,
    }
    resp = requests.get(url, params=params, headers=_headers(), timeout=20)
    resp.raise_for_status()
    return resp.json()


def _score_coin(data: dict) -> CoinSignal:
    notes = []
    score = 50  # neutral baseline

    price_change_24h = data.get("price_change_percentage_24h") or 0.0
    price_change_1h  = data.get("price_change_percentage_1h_in_currency") or 0.0
    price_change_7d  = data.get("price_change_percentage_7d_in_currency") or 0.0
    volume_24h       = data.get("total_volume") or 0.0
    market_cap       = data.get("market_cap") or 1.0
    volume_to_mcap   = (volume_24h / market_cap) * 100 if market_cap else 0

    # --- 24h price momentum (up to ±20 pts) ---
    if price_change_24h >= 20:
        score += 20; notes.append(f"+{price_change_24h:.1f}% 24h (strong)")
    elif price_change_24h >= 10:
        score += 12; notes.append(f"+{price_change_24h:.1f}% 24h")
    elif price_change_24h >= 5:
        score += 6;  notes.append(f"+{price_change_24h:.1f}% 24h")
    elif price_change_24h <= -20:
        score -= 20; notes.append(f"{price_change_24h:.1f}% 24h (crash)")
    elif price_change_24h <= -10:
        score -= 12; notes.append(f"{price_change_24h:.1f}% 24h")
    elif price_change_24h <= -5:
        score -= 6;  notes.append(f"{price_change_24h:.1f}% 24h")

    # --- 1h acceleration (up to ±15 pts) ---
    if price_change_1h >= 5:
        score += 15; notes.append(f"+{price_change_1h:.1f}% 1h surge")
    elif price_change_1h >= 2:
        score += 8;  notes.append(f"+{price_change_1h:.1f}% 1h up")
    elif price_change_1h <= -5:
        score -= 15; notes.append(f"{price_change_1h:.1f}% 1h dump")
    elif price_change_1h <= -2:
        score -= 8;  notes.append(f"{price_change_1h:.1f}% 1h down")

    # --- Volume/market-cap ratio (up to +15 pts) ---
    if volume_to_mcap >= 50:
        score += 15; notes.append(f"V/MC {volume_to_mcap:.0f}% (huge)")
    elif volume_to_mcap >= 25:
        score += 10; notes.append(f"V/MC {volume_to_mcap:.0f}% (high)")
    elif volume_to_mcap >= 10:
        score += 5;  notes.append(f"V/MC {volume_to_mcap:.0f}%")
    elif volume_to_mcap < 2:
        score -= 5;  notes.append("Low volume")

    # --- 7d trend context (up to ±10 pts) ---
    if price_change_7d >= 30:
        score += 10; notes.append("Strong 7d uptrend")
    elif price_change_7d >= 10:
        score += 5
    elif price_change_7d <= -30:
        score -= 10; notes.append("Severe 7d downtrend")
    elif price_change_7d <= -10:
        score -= 5

    score = max(0, min(100, score))

    if score >= BUY_SCORE_THRESHOLD:
        signal = "buy now"
    elif score <= SELL_SCORE_THRESHOLD:
        signal = "sell"
    else:
        signal = "hold"

    return CoinSignal(
        coin_id=data["id"],
        name=data["name"],
        symbol=data["symbol"].upper(),
        price_usd=data.get("current_price") or 0.0,
        price_change_24h=price_change_24h,
        volume_change_24h=volume_to_mcap,
        score=score,
        signal=signal,
        notes=notes,
    )


def run_signals(coin_ids: List[str] | None = None) -> List[CoinSignal]:
    """Fetch market data and return a signal for each tracked coin."""
    ids = coin_ids or TRACKED_COINS
    market_data = _fetch_market_data(ids)
    results = []
    for item in market_data:
        results.append(_score_coin(item))
        time.sleep(0.1)
    return results
