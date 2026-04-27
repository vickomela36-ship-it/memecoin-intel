"""
Buy/sell signal logic.

Data source: DexScreener public API (no key required).
Strategy   : Trending Solana pairs that pass liquidity, volume, and
             1-hour momentum thresholds are marked "buy now".
"""

import logging
import requests

from config import (
    DEXSCREENER_BASE,
    TARGET_CHAINS,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_24H_USD,
    MIN_PRICE_CHANGE_1H,
    MAX_TOKENS_PER_RUN,
)

log = logging.getLogger(__name__)

# DexScreener endpoints (all public, no API key required)
_BOOSTED_URL  = f"{DEXSCREENER_BASE}/token-boosts/top/v1"      # top boosted tokens
_SEARCH_URL   = f"{DEXSCREENER_BASE}/latest/dex/search"         # fallback: search by query
_PAIRS_URL    = f"{DEXSCREENER_BASE}/latest/dex/tokens/{{addresses}}"

# Broad search terms used as fallback when the boosted endpoint is unavailable
_FALLBACK_QUERIES = ["SOL", "BONK", "WIF", "POPCAT"]


def _fetch_trending_addresses() -> list[str]:
    """Return token addresses for the top boosted tokens on target chains.

    Falls back to DexScreener search results when the boosted endpoint is blocked.
    """
    # Primary: boosted tokens (best signal for trending memecoins)
    try:
        resp = requests.get(_BOOSTED_URL, timeout=15)
        if resp.ok:
            boosted = resp.json()
            addresses = [
                p["tokenAddress"]
                for p in boosted
                if p.get("chainId") in TARGET_CHAINS and p.get("tokenAddress")
            ]
            if addresses:
                log.info("Fetched %d boosted token address(es)", len(addresses))
                return addresses[:MAX_TOKENS_PER_RUN]
    except Exception as exc:
        log.warning("Boosted endpoint unavailable (%s) — falling back to search", exc)

    # Fallback: search-based discovery
    addresses: list[str] = []
    seen: set[str] = set()
    for query in _FALLBACK_QUERIES:
        if len(addresses) >= MAX_TOKENS_PER_RUN:
            break
        try:
            resp = requests.get(_SEARCH_URL, params={"q": query}, timeout=15)
            if not resp.ok:
                continue
            for pair in resp.json().get("pairs") or []:
                if pair.get("chainId") not in TARGET_CHAINS:
                    continue
                addr = (pair.get("baseToken") or {}).get("address", "")
                if addr and addr not in seen:
                    seen.add(addr)
                    addresses.append(addr)
        except Exception as exc:
            log.warning("Search fallback failed for %r: %s", query, exc)

    log.info("Fetched %d address(es) via search fallback", len(addresses))
    return addresses[:MAX_TOKENS_PER_RUN]


def _fetch_pairs(addresses: list[str]) -> list[dict]:
    """Batch-fetch pair data for a list of token addresses."""
    if not addresses:
        return []
    # DexScreener accepts up to 30 comma-separated addresses per request
    pairs: list[dict] = []
    chunk_size = 30
    for i in range(0, len(addresses), chunk_size):
        chunk = ",".join(addresses[i : i + chunk_size])
        try:
            resp = requests.get(_PAIRS_URL.format(addresses=chunk), timeout=15)
            resp.raise_for_status()
            pairs.extend(resp.json().get("pairs") or [])
        except Exception as exc:
            log.warning("Failed to fetch pairs for chunk: %s", exc)
    return pairs


def _best_pair(pairs: list[dict], address: str) -> dict | None:
    """Return the highest-liquidity pair for a given token address."""
    candidates = [
        p for p in pairs
        if p.get("baseToken", {}).get("address", "").lower() == address.lower()
        and p.get("chainId") in TARGET_CHAINS
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)


def _evaluate(pair: dict) -> str:
    """Return 'buy now' | 'hold' based on the configured thresholds."""
    try:
        liq    = float((pair.get("liquidity") or {}).get("usd") or 0)
        vol24  = float((pair.get("volume") or {}).get("h24") or 0)
        chg1h  = float((pair.get("priceChange") or {}).get("h1") or 0)
    except (TypeError, ValueError):
        return "hold"

    if liq >= MIN_LIQUIDITY_USD and vol24 >= MIN_VOLUME_24H_USD and chg1h >= MIN_PRICE_CHANGE_1H:
        return "buy now"
    return "hold"


def _build_signal_record(pair: dict) -> dict:
    base    = pair.get("baseToken") or {}
    vol     = pair.get("volume") or {}
    liq     = pair.get("liquidity") or {}
    chg     = pair.get("priceChange") or {}
    liq_usd = liq.get("usd") or 0
    vol_24h = vol.get("h24") or 0
    chg_1h  = chg.get("h1") or 0

    return {
        "token":         base.get("symbol", "UNKNOWN"),
        "token_address": base.get("address", ""),
        "chain":         pair.get("chainId", ""),
        "dex":           pair.get("dexId", ""),
        "dex_url":       pair.get("url", ""),
        "price_usd":     str(pair.get("priceUsd") or ""),
        "volume_24h":    str(vol_24h),
        "liquidity":     str(liq_usd),
        "change_1h":     str(chg_1h),
        "change_6h":     str(chg.get("h6") or ""),
        "change_24h":    str(chg.get("h24") or ""),
        "signal":        "buy now",
        "reason": (
            f"Vol ${float(vol_24h):,.0f} | "
            f"Liq ${float(liq_usd):,.0f} | "
            f"+{chg_1h}% (1h)"
        ),
    }


def get_buy_signals() -> list[dict]:
    """
    Main entry point.  Returns a list of signal records (dicts) for every
    token that currently meets the 'buy now' criteria.
    """
    addresses = _fetch_trending_addresses()
    if not addresses:
        log.info("No trending addresses found.")
        return []

    pairs = _fetch_pairs(addresses)
    log.info("Evaluating %d token(s) across %d pair(s)", len(addresses), len(pairs))

    results = []
    seen = set()
    for addr in addresses:
        pair = _best_pair(pairs, addr)
        if not pair:
            continue
        if addr in seen:
            continue
        seen.add(addr)

        signal = _evaluate(pair)
        if signal == "buy now":
            rec = _build_signal_record(pair)
            log.info("BUY NOW ▶ %s @ $%s (+%s%% 1h)", rec["token"], rec["price_usd"], rec["change_1h"])
            results.append(rec)

    return results
