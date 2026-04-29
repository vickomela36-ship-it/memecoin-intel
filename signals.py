import logging
import requests
from config import (
    DEXSCREENER_CHAIN,
    BUY_SIGNAL_MIN_PRICE_CHANGE_5M,
    BUY_SIGNAL_MIN_PRICE_CHANGE_1H,
    BUY_SIGNAL_MIN_VOLUME_5M,
    BUY_SIGNAL_MIN_LIQUIDITY,
)

logger = logging.getLogger(__name__)

_BOOSTED_URL = "https://api.dexscreener.com/token-boosts/top/v1"
_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"


def _fetch_boosted_addresses(chain: str) -> list[str]:
    try:
        resp = requests.get(_BOOSTED_URL, timeout=10)
        resp.raise_for_status()
        boosts = resp.json()
    except Exception as e:
        logger.error("Failed to fetch boosted tokens: %s", e)
        return []

    return [
        t["tokenAddress"]
        for t in boosts[:30]
        if t.get("chainId") == chain and t.get("tokenAddress")
    ]


def _fetch_best_pair(address: str) -> dict | None:
    try:
        resp = requests.get(_TOKENS_URL.format(address=address), timeout=10)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        if not pairs:
            return None
        # most liquid pair for this token
        return max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0))
    except Exception as e:
        logger.warning("Failed to fetch pair for %s: %s", address, e)
        return None


def _classify(pair: dict) -> str:
    pc = pair.get("priceChange") or {}
    vol = pair.get("volume") or {}
    liq = pair.get("liquidity") or {}

    change_5m = float(pc.get("m5") or 0)
    change_1h = float(pc.get("h1") or 0)
    volume_5m = float(vol.get("m5") or 0)
    liquidity = float(liq.get("usd") or 0)

    if (
        change_5m >= BUY_SIGNAL_MIN_PRICE_CHANGE_5M
        and change_1h >= BUY_SIGNAL_MIN_PRICE_CHANGE_1H
        and volume_5m >= BUY_SIGNAL_MIN_VOLUME_5M
        and liquidity >= BUY_SIGNAL_MIN_LIQUIDITY
    ):
        return "buy now"
    if change_5m <= -5.0:
        return "sell"
    return "hold"


def run_signals(chain: str | None = None) -> list[dict]:
    """Scan top boosted tokens and return signal results for each."""
    chain = chain or DEXSCREENER_CHAIN
    addresses = _fetch_boosted_addresses(chain)
    results = []

    for address in addresses:
        pair = _fetch_best_pair(address)
        if not pair:
            continue

        pc = pair.get("priceChange") or {}
        vol = pair.get("volume") or {}
        liq = pair.get("liquidity") or {}

        results.append({
            "symbol": (pair.get("baseToken") or {}).get("symbol", "UNKNOWN"),
            "pair_address": pair.get("pairAddress", ""),
            "signal": _classify(pair),
            "price_usd": float(pair.get("priceUsd") or 0),
            "price_change_5m": float(pc.get("m5") or 0),
            "price_change_1h": float(pc.get("h1") or 0),
            "volume_5m_usd": float(vol.get("m5") or 0),
            "liquidity_usd": float(liq.get("usd") or 0),
        })

    buy_count = sum(1 for r in results if r["signal"] == "buy now")
    logger.info("Scanned %d pairs — %d buy signal(s)", len(results), buy_count)
    return results
