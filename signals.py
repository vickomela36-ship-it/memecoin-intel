"""Buy/sell signal logic using DexScreener API."""

import logging
import requests
import config

_DEXSCREENER = "https://api.dexscreener.com/latest/dex/pairs/solana/{}"


def _fetch_pair(pair_address: str) -> dict:
    url = _DEXSCREENER.format(pair_address)
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    pairs = resp.json().get("pairs") or []
    return pairs[0] if pairs else {}


def _classify(pair: dict) -> str:
    price_change = float((pair.get("priceChange") or {}).get("h24") or 0)
    volume_24h = float((pair.get("volume") or {}).get("h24") or 0)
    liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)

    if (
        price_change >= config.BUY_MIN_PRICE_CHANGE_24H
        and volume_24h >= config.BUY_MIN_VOLUME_24H
        and liquidity >= config.BUY_MIN_LIQUIDITY
    ):
        return "buy now"
    if price_change <= -10:
        return "sell"
    return "hold"


def get_signals() -> list[dict]:
    """Return a list of signal dicts for every pair in the watchlist."""
    results = []
    for addr in config.WATCHLIST:
        try:
            pair = _fetch_pair(addr)
            if not pair:
                logging.warning("No data for pair %s", addr)
                continue
            results.append(
                {
                    "signal": _classify(pair),
                    "pair_address": addr,
                    "coin_symbol": (pair.get("baseToken") or {}).get("symbol", ""),
                    "chain": pair.get("chainId", "solana"),
                    "dex": pair.get("dexId", ""),
                    "price_usd": float(pair.get("priceUsd") or 0),
                    "price_change_24h": float((pair.get("priceChange") or {}).get("h24") or 0),
                    "liquidity_usd": float((pair.get("liquidity") or {}).get("usd") or 0),
                    "volume_24h_usd": float((pair.get("volume") or {}).get("h24") or 0),
                }
            )
        except Exception:
            logging.exception("Failed to evaluate pair %s", addr)
    return results
