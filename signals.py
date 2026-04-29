"""
Buy/sell signal logic using DexScreener API.
Checks on-chain memecoin pair data and classifies signals as:
  'buy now' — strong momentum + high buy pressure
  'sell'    — downtrend or weak buy side
  'hold'    — insufficient data or neutral conditions
"""

import requests
from dataclasses import dataclass
from typing import Optional

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"


@dataclass
class SignalResult:
    token: str
    symbol: str
    signal: str          # 'buy now' | 'hold' | 'sell'
    price_usd: float
    volume_24h: float
    liquidity_usd: float
    change_1h: float
    change_6h: float
    change_24h: float
    buy_pressure: float  # 0.0 – 1.0
    dexscreener_url: str
    reason: str


def _get_pair(pair_address: str, chain: str = "solana") -> Optional[dict]:
    url = f"{DEXSCREENER_API}/pairs/{chain}/{pair_address}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    pairs = resp.json().get("pairs") or []
    return pairs[0] if pairs else None


def _classify(pair: dict) -> SignalResult:
    base = pair.get("baseToken", {})
    token_name = base.get("name", "Unknown")
    symbol = base.get("symbol", "???")

    price_usd = float(pair.get("priceUsd") or 0)
    vol = pair.get("volume") or {}
    liq = pair.get("liquidity") or {}
    chg = pair.get("priceChange") or {}
    txns_24h = (pair.get("txns") or {}).get("h24") or {}

    volume_24h = float(vol.get("h24") or 0)
    liquidity_usd = float(liq.get("usd") or 0)
    change_1h = float(chg.get("h1") or 0)
    change_6h = float(chg.get("h6") or 0)
    change_24h = float(chg.get("h24") or 0)

    buys = int(txns_24h.get("buys") or 0)
    sells = int(txns_24h.get("sells") or 0)
    total = buys + sells
    buy_pressure = buys / total if total > 0 else 0.5

    dex_url = pair.get("url", "")

    # import thresholds lazily to avoid circular deps
    from config import (
        MIN_LIQUIDITY_USD,
        MIN_VOLUME_24H_USD,
        BUY_PRESSURE_THRESHOLD,
        PRICE_CHANGE_1H_THRESHOLD,
    )

    if liquidity_usd < MIN_LIQUIDITY_USD:
        signal = "hold"
        reason = f"Low liquidity (${liquidity_usd:,.0f} < ${MIN_LIQUIDITY_USD:,.0f})"
    elif change_24h < -20:
        signal = "sell"
        reason = f"Strong downtrend: {change_24h:.1f}% over 24 h"
    elif change_24h < -5 and buy_pressure < 0.40:
        signal = "sell"
        reason = f"Weak: {change_24h:.1f}% 24 h, only {buy_pressure*100:.0f}% buys"
    elif (
        change_1h >= PRICE_CHANGE_1H_THRESHOLD
        and buy_pressure >= BUY_PRESSURE_THRESHOLD
        and volume_24h >= MIN_VOLUME_24H_USD
        and change_6h > 0
    ):
        signal = "buy now"
        reason = (
            f"Momentum: +{change_1h:.1f}% 1h | {buy_pressure*100:.0f}% buys | "
            f"vol ${volume_24h:,.0f}"
        )
    else:
        signal = "hold"
        reason = (
            f"Neutral: {change_1h:+.1f}% 1h, {buy_pressure*100:.0f}% buys, "
            f"vol ${volume_24h:,.0f}"
        )

    return SignalResult(
        token=token_name,
        symbol=symbol,
        signal=signal,
        price_usd=price_usd,
        volume_24h=volume_24h,
        liquidity_usd=liquidity_usd,
        change_1h=change_1h,
        change_6h=change_6h,
        change_24h=change_24h,
        buy_pressure=buy_pressure,
        dexscreener_url=dex_url,
        reason=reason,
    )


def check_all_tokens() -> list[SignalResult]:
    """Fetch + classify every token in config.TRACKED_TOKENS."""
    from config import TRACKED_TOKENS, CHAIN

    results: list[SignalResult] = []
    for addr in TRACKED_TOKENS:
        try:
            pair = _get_pair(addr, chain=CHAIN)
            if pair:
                results.append(_classify(pair))
            else:
                print(f"[signals] No pair data for {addr}")
        except Exception as exc:
            print(f"[signals] Error fetching {addr}: {exc}")
    return results
