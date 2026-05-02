#!/usr/bin/env python3
"""Memecoin buy/sell signal engine backed by DexScreener's public API."""
import json
import sys

import requests

from config import (
    MIN_LIQUIDITY,
    MIN_PRICE_CHANGE_1H,
    MIN_VOLUME_24H,
    WATCH_TOKENS,
)

_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search?q={}"
_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"

# Free-tier search terms to surface trending memecoins across all chains
_SEARCH_TERMS = ["pepe", "doge", "shib", "meme", "cat", "bonk", "wojak", "moon"]

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})


def _evaluate_pair(pair: dict) -> dict | None:
    """Return a signal dict if the pair meets buy criteria, else None."""
    try:
        price_change_1h = float(pair.get("priceChange", {}).get("h1") or 0)
        volume_24h = float(pair.get("volume", {}).get("h24") or 0)
        liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)
        price_usd = float(pair.get("priceUsd") or 0)

        if (
            price_change_1h >= MIN_PRICE_CHANGE_1H
            and volume_24h >= MIN_VOLUME_24H
            and liquidity >= MIN_LIQUIDITY
        ):
            base = pair.get("baseToken") or {}
            return {
                "signal": "buy now",
                "token": base.get("symbol", "UNKNOWN"),
                "token_name": base.get("name", ""),
                "token_address": base.get("address", ""),
                "chain": pair.get("chainId", ""),
                "price_usd": price_usd,
                "price_change_1h": price_change_1h,
                "volume_24h": volume_24h,
                "liquidity_usd": liquidity,
                "dexscreener_url": pair.get("url", ""),
            }
    except (TypeError, ValueError, KeyError):
        pass
    return None


def _pairs_for_address(address: str) -> list[dict]:
    resp = _SESSION.get(_TOKEN_URL.format(address), timeout=10)
    resp.raise_for_status()
    return resp.json().get("pairs") or []


def get_signals() -> list[dict]:
    """Return all 'buy now' signals for the current check cycle."""
    signals: list[dict] = []
    seen: set[str] = set()

    if WATCH_TOKENS:
        for addr in WATCH_TOKENS:
            for pair in _pairs_for_address(addr)[:5]:
                key = pair.get("pairAddress", "")
                if key in seen:
                    continue
                seen.add(key)
                sig = _evaluate_pair(pair)
                if sig:
                    signals.append(sig)
    else:
        # Search free-tier DexScreener endpoints for trending memecoins
        for term in _SEARCH_TERMS:
            try:
                resp = _SESSION.get(_SEARCH_URL.format(term), timeout=10)
                resp.raise_for_status()
                pairs = resp.json().get("pairs") or []
                # Only look at the top 5 pairs per search term by volume
                pairs_sorted = sorted(
                    pairs,
                    key=lambda p: float((p.get("volume") or {}).get("h24") or 0),
                    reverse=True,
                )
                for pair in pairs_sorted[:5]:
                    key = pair.get("pairAddress", "")
                    if key in seen:
                        continue
                    seen.add(key)
                    sig = _evaluate_pair(pair)
                    if sig:
                        signals.append(sig)
            except requests.RequestException:
                continue

    return signals


if __name__ == "__main__":
    try:
        result = get_signals()
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
