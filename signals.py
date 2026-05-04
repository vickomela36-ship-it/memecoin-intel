"""Buy/sell signal logic powered by the DexScreener public API."""

from __future__ import annotations

import logging

import requests

from config import SIGNAL_CONFIG

log = logging.getLogger(__name__)

_BASE = "https://api.dexscreener.com"


def _fetch_pairs_for_addresses(addresses: list[str]) -> list[dict]:
    """Return DexScreener pair objects for up to 30 token addresses."""
    url = f"{_BASE}/latest/dex/tokens/{','.join(addresses[:30])}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json().get("pairs") or []


def _fetch_trending_pairs() -> list[dict]:
    """Pull the current DexScreener boosted/trending tokens, then fetch their pairs."""
    resp = requests.get(f"{_BASE}/token-boosts/latest/v1", timeout=15)
    resp.raise_for_status()
    boosts = resp.json() or []
    addresses = [
        b["tokenAddress"]
        for b in boosts[:30]
        if b.get("tokenAddress")
    ]
    if not addresses:
        return []
    return _fetch_pairs_for_addresses(addresses)


def _evaluate(pair: dict) -> str | None:
    """Return 'buy now' when all criteria pass, else None."""
    cfg = SIGNAL_CONFIG
    try:
        change_1h = float((pair.get("priceChange") or {}).get("h1") or 0)
        vol_24h = float((pair.get("volume") or {}).get("h24") or 0)
        liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)
    except (TypeError, ValueError):
        return None

    if (
        change_1h >= cfg["min_price_change_1h_pct"]
        and vol_24h >= cfg["min_volume_24h_usd"]
        and liquidity >= cfg["min_liquidity_usd"]
        and liquidity > 0
        and (vol_24h / liquidity) >= cfg["min_vol_liq_ratio"]
    ):
        return "buy now"
    return None


def get_signals(token_addresses: list[str] | None = None) -> list[dict]:
    """
    Evaluate all tracked tokens and return a list of signal dicts for every
    token whose signal is 'buy now'.

    Each dict contains:
        token, chain, token_address, price_usd, price_change_1h,
        volume_24h, liquidity_usd, dexscreener_url, signal
    """
    pairs = (
        _fetch_pairs_for_addresses(token_addresses)
        if token_addresses
        else _fetch_trending_pairs()
    )

    results: list[dict] = []
    seen: set[str] = set()

    for pair in pairs:
        signal = _evaluate(pair)
        if signal != "buy now":
            continue

        address = (pair.get("baseToken") or {}).get("address", "")
        if address in seen:
            continue
        seen.add(address)

        results.append(
            {
                "token": (pair.get("baseToken") or {}).get("symbol", "UNKNOWN"),
                "chain": pair.get("chainId", ""),
                "token_address": address,
                "price_usd": float(pair.get("priceUsd") or 0),
                "price_change_1h": float(
                    (pair.get("priceChange") or {}).get("h1") or 0
                ),
                "volume_24h": float(
                    (pair.get("volume") or {}).get("h24") or 0
                ),
                "liquidity_usd": float(
                    (pair.get("liquidity") or {}).get("usd") or 0
                ),
                "dexscreener_url": pair.get("url", ""),
                "signal": signal,
            }
        )
        log.info("BUY NOW: %s (%s)", results[-1]["token"], results[-1]["chain"])

    return results
