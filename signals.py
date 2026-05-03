"""
Buy/sell signal logic for trending Solana memecoins.

Data source: DexScreener public API (no auth required).

Scoring:
  +2  volume/marketCap ratio > VOLUME_TO_MCAP_THRESHOLD
  +2  24h price change >= PRICE_CHANGE_THRESHOLD_HIGH
  +1  24h price change >= PRICE_CHANGE_THRESHOLD_LOW
  +1  24h volume >= MIN_VOLUME_USD

  score >= 4  → "buy now"
  score >= 2  → "hold"
  else        → "sell"
"""

import requests
from config import (
    VOLUME_TO_MCAP_THRESHOLD,
    PRICE_CHANGE_THRESHOLD_HIGH,
    PRICE_CHANGE_THRESHOLD_LOW,
    MIN_VOLUME_USD,
)

_BOOSTED_URL = "https://api.dexscreener.com/token-boosts/top/v1"
_TOKEN_URL   = "https://api.dexscreener.com/latest/dex/tokens/{address}"


def _fetch_top_solana_pairs(limit: int) -> list[dict]:
    try:
        resp = requests.get(_BOOSTED_URL, timeout=10)
        resp.raise_for_status()
        tokens = [t for t in resp.json() if t.get("chainId") == "solana"][:limit]
    except Exception as e:
        print(f"[signals] boosted-tokens fetch error: {e}")
        return []

    pairs = []
    for token in tokens:
        addr = token.get("tokenAddress", "")
        if not addr:
            continue
        try:
            r = requests.get(_TOKEN_URL.format(address=addr), timeout=10)
            r.raise_for_status()
            pair_list = r.json().get("pairs") or []
            if pair_list:
                # pick the pair with highest 24h volume
                best = max(pair_list, key=lambda p: float((p.get("volume") or {}).get("h24") or 0))
                pairs.append(best)
        except Exception as e:
            print(f"[signals] pair fetch error for {addr}: {e}")

    return pairs


def _compute_signal(pair: dict) -> dict:
    base       = pair.get("baseToken") or {}
    symbol     = base.get("symbol", "UNKNOWN")
    address    = base.get("address", "")
    price_usd  = float(pair.get("priceUsd") or 0)
    market_cap = float(pair.get("marketCap") or pair.get("fdv") or 0)
    volume_24h = float((pair.get("volume") or {}).get("h24") or 0)
    change_24h = float((pair.get("priceChange") or {}).get("h24") or 0)

    score = 0
    notes: list[str] = []

    if volume_24h < MIN_VOLUME_USD:
        notes.append(f"low vol ${volume_24h:,.0f}")
    else:
        if market_cap > 0:
            ratio = volume_24h / market_cap
            if ratio > VOLUME_TO_MCAP_THRESHOLD:
                score += 2
                notes.append(f"vol/mcap={ratio:.1%}")

        if change_24h >= PRICE_CHANGE_THRESHOLD_HIGH:
            score += 2
            notes.append(f"+{change_24h:.1f}% 24h")
        elif change_24h >= PRICE_CHANGE_THRESHOLD_LOW:
            score += 1
            notes.append(f"+{change_24h:.1f}% 24h")

        score += 1
        notes.append(f"vol=${volume_24h / 1e6:.2f}M")

    if score >= 4:
        signal = "buy now"
    elif score >= 2:
        signal = "hold"
    else:
        signal = "sell"

    return {
        "token":      symbol,
        "address":    address,
        "signal":     signal,
        "price_usd":  price_usd,
        "market_cap": market_cap,
        "volume_24h": volume_24h,
        "change_24h": change_24h,
        "notes":      ", ".join(notes),
        "score":      score,
    }


def get_buy_signals(limit: int = 20) -> list[dict]:
    """Return signal dicts with signal == 'buy now' from top trending Solana pairs."""
    pairs   = _fetch_top_solana_pairs(limit)
    results = [_compute_signal(p) for p in pairs]
    buys    = [r for r in results if r["signal"] == "buy now"]
    return buys
