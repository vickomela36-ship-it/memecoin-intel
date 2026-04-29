"""
Buy/sell signal logic using DexScreener's free public API.

Signal thresholds (tunable via env vars):
  buy now  → 1h ≥ +3%, 24h vol ≥ $50k, liquidity ≥ $10k, buy pressure ≥ 55%
  sell     → 1h ≤ -8%  OR  buy pressure ≤ 30%
  hold     → everything else
"""
import os
import requests
from datetime import datetime, timezone

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens"

# Thresholds — override via env vars if needed
BUY_MIN_1H_CHANGE     = float(os.getenv("BUY_MIN_1H_CHANGE",     "3.0"))
BUY_MIN_VOLUME_24H    = float(os.getenv("BUY_MIN_VOLUME_24H",    "50000"))
BUY_MIN_LIQUIDITY     = float(os.getenv("BUY_MIN_LIQUIDITY",     "10000"))
BUY_MIN_BUY_PRESSURE  = float(os.getenv("BUY_MIN_BUY_PRESSURE",  "0.55"))
SELL_MAX_1H_CHANGE    = float(os.getenv("SELL_MAX_1H_CHANGE",    "-8.0"))
SELL_MAX_BUY_PRESSURE = float(os.getenv("SELL_MAX_BUY_PRESSURE", "0.30"))


def _best_pair_per_token(pairs: list[dict]) -> list[dict]:
    """Keep the highest-liquidity trading pair for each base token address."""
    best: dict[str, dict] = {}
    for pair in pairs:
        addr = pair["baseToken"]["address"]
        liq = (pair.get("liquidity") or {}).get("usd") or 0
        if addr not in best or liq > ((best[addr].get("liquidity") or {}).get("usd") or 0):
            best[addr] = pair
    return list(best.values())


def fetch_pairs(addresses: list[str]) -> list[dict]:
    """Fetch DexScreener pair data for up to 30 token addresses at once."""
    if not addresses:
        return []
    joined = ",".join(addresses[:30])
    resp = requests.get(f"{DEXSCREENER_API}/{joined}", timeout=15)
    resp.raise_for_status()
    return _best_pair_per_token(resp.json().get("pairs") or [])


def compute_signal(pair: dict) -> dict:
    price_change = pair.get("priceChange") or {}
    h1  = float(price_change.get("h1")  or 0)
    h6  = float(price_change.get("h6")  or 0)
    h24 = float(price_change.get("h24") or 0)

    volume_24h = float((pair.get("volume") or {}).get("h24") or 0)
    liquidity  = float((pair.get("liquidity") or {}).get("usd") or 0)
    price_usd  = pair.get("priceUsd") or "0"

    h1_txns    = (pair.get("txns") or {}).get("h1") or {}
    buys       = int(h1_txns.get("buys")  or 0)
    sells      = int(h1_txns.get("sells") or 0)
    total      = buys + sells
    buy_pressure = buys / total if total > 0 else 0.5

    token = pair["baseToken"]

    if (
        h1 >= BUY_MIN_1H_CHANGE
        and volume_24h >= BUY_MIN_VOLUME_24H
        and liquidity  >= BUY_MIN_LIQUIDITY
        and buy_pressure >= BUY_MIN_BUY_PRESSURE
    ):
        signal = "buy now"
    elif h1 <= SELL_MAX_1H_CHANGE or buy_pressure <= SELL_MAX_BUY_PRESSURE:
        signal = "sell"
    else:
        signal = "hold"

    return {
        "token_name":      token.get("name", "Unknown"),
        "symbol":          token.get("symbol", "?"),
        "address":         token.get("address", ""),
        "signal":          signal,
        "price_usd":       price_usd,
        "volume_24h":      volume_24h,
        "liquidity":       liquidity,
        "h1_change":       h1,
        "h6_change":       h6,
        "h24_change":      h24,
        "buy_pressure":    round(buy_pressure * 100, 1),
        "dexscreener_url": pair.get("url") or "",
        "checked_at":      datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }


def get_signals(addresses: list[str]) -> list[dict]:
    """Return a signal dict for each watched token address."""
    pairs = fetch_pairs(addresses)
    return [compute_signal(p) for p in pairs]
