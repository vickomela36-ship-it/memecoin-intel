"""
Buy/sell signal logic using DexScreener public API.
Returns a list of SignalResult dicts, one per token pair evaluated.
"""

import json
import urllib.request
from datetime import datetime, timezone
from typing import Any

from config import (
    WATCHED_TOKENS,
    BUY_MIN_1H_CHANGE_PCT,
    BUY_MIN_VOLUME_24H_USD,
    BUY_MIN_LIQUIDITY_USD,
    BUY_MIN_BUY_PRESSURE,
    SELL_MAX_1H_CHANGE_PCT,
)

DEXSCREENER_TOKENS_V1 = "https://api.dexscreener.com/tokens/v1/{chain}/{address}"
DEXSCREENER_SEARCH    = "https://api.dexscreener.com/latest/dex/search?q={}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _fetch_pairs(token_address: str, chain: str = "solana") -> list[dict]:
    for url in [
        DEXSCREENER_TOKENS_V1.format(chain=chain, address=token_address),
        DEXSCREENER_SEARCH.format(token_address),
    ]:
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            pairs = data if isinstance(data, list) else data.get("pairs") or []
            if pairs:
                return pairs
        except Exception:
            continue
    return []


def _best_pair(pairs: list[dict]) -> dict | None:
    """Pick the pair with the highest 24h volume."""
    if not pairs:
        return None
    return max(pairs, key=lambda p: float(p.get("volume", {}).get("h24") or 0))


def _buy_pressure(pair: dict) -> float:
    """Fraction of buy transactions over the last 1h, as a percentage."""
    txns = pair.get("txns", {}).get("h1", {})
    buys = int(txns.get("buys") or 0)
    sells = int(txns.get("sells") or 0)
    total = buys + sells
    return round(buys / total * 100, 1) if total else 0.0


def _signal(pair: dict) -> str:
    price_change_1h = float(pair.get("priceChange", {}).get("h1") or 0)
    volume_24h = float(pair.get("volume", {}).get("h24") or 0)
    liquidity = float(pair.get("liquidity", {}).get("usd") or 0)
    bp = _buy_pressure(pair)

    if (
        price_change_1h >= BUY_MIN_1H_CHANGE_PCT
        and volume_24h >= BUY_MIN_VOLUME_24H_USD
        and liquidity >= BUY_MIN_LIQUIDITY_USD
        and bp >= BUY_MIN_BUY_PRESSURE
    ):
        return "buy now"

    if price_change_1h <= SELL_MAX_1H_CHANGE_PCT:
        return "sell"

    return "hold"


def _fmt(value: Any, prefix: str = "", suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{prefix}{value}{suffix}"


def get_signals() -> list[dict]:
    """
    Returns a list of dicts, one per token address, shaped to match the
    Notion 'Memecoin Buy Signals' schema.
    """
    results = []
    now = datetime.now(timezone.utc).isoformat()

    for address in WATCHED_TOKENS:
        try:
            pairs = _fetch_pairs(address)
            pair = _best_pair(pairs)
            if not pair:
                continue

            sig = _signal(pair)
            pc = pair.get("priceChange", {})
            vol = pair.get("volume", {})
            liq = pair.get("liquidity", {})

            results.append({
                "Token":          pair.get("baseToken", {}).get("name", address),
                "Symbol":         pair.get("baseToken", {}).get("symbol", ""),
                "Signal":         sig,
                "Price USD":      _fmt(pair.get("priceUsd")),
                "1h Change %":    _fmt(pc.get("h1"), suffix="%"),
                "6h Change %":    _fmt(pc.get("h6"), suffix="%"),
                "24h Change %":   _fmt(pc.get("h24"), suffix="%"),
                "Volume 24h USD": _fmt(vol.get("h24"), prefix="$"),
                "Liquidity USD":  _fmt(liq.get("usd"), prefix="$"),
                "Buy Pressure":   _fmt(_buy_pressure(pair), suffix="%"),
                "DexScreener URL": pair.get("url", ""),
                "Checked At":     now,
                "_address":       address,
            })
        except Exception as exc:
            print(f"[signals] error fetching {address}: {exc}")

    return results


if __name__ == "__main__":
    for r in get_signals():
        print(json.dumps(r, indent=2))
