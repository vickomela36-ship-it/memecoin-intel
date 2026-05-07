import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"

# Signal thresholds
_STRONG = {"price_change_24h": 100, "volume_24h": 500_000, "liquidity": 50_000, "price_change_1h": 5}
_MODERATE = {"price_change_24h": 30, "volume_24h": 100_000, "liquidity": 20_000, "price_change_1h": 2}
_WEAK = {"price_change_24h": 10, "volume_24h": 30_000, "liquidity": 10_000, "price_change_1h": 0}


def _fetch_solana_token_addresses():
    resp = requests.get(_PROFILES_URL, timeout=15)
    resp.raise_for_status()
    profiles = resp.json()
    return [p["tokenAddress"] for p in profiles if p.get("chainId") == "solana" and p.get("tokenAddress")]


def _fetch_pairs(addresses):
    pairs = []
    for i in range(0, len(addresses), 30):
        batch = addresses[i : i + 30]
        try:
            resp = requests.get(_TOKENS_URL.format(",".join(batch)), timeout=15)
            if resp.status_code == 200:
                pairs.extend(resp.json().get("pairs") or [])
        except Exception as exc:
            logger.warning("Pair fetch error for batch %d: %s", i, exc)
    return pairs


def _classify(pair):
    if pair.get("chainId") != "solana":
        return None

    liq = (pair.get("liquidity") or {}).get("usd") or 0
    vol = (pair.get("volume") or {}).get("h24") or 0
    ch1h = (pair.get("priceChange") or {}).get("h1") or 0
    ch24h = (pair.get("priceChange") or {}).get("h24") or 0
    price = float(pair.get("priceUsd") or 0)

    base = pair.get("baseToken") or {}
    coin = base.get("symbol", "UNKNOWN")
    address = base.get("address", "")

    if ch24h >= _STRONG["price_change_24h"] and vol >= _STRONG["volume_24h"] and liq >= _STRONG["liquidity"] and ch1h >= _STRONG["price_change_1h"]:
        strength = "Strong"
    elif ch24h >= _MODERATE["price_change_24h"] and vol >= _MODERATE["volume_24h"] and liq >= _MODERATE["liquidity"] and ch1h >= _MODERATE["price_change_1h"]:
        strength = "Moderate"
    elif ch24h >= _WEAK["price_change_24h"] and vol >= _WEAK["volume_24h"] and liq >= _WEAK["liquidity"] and ch1h >= _WEAK["price_change_1h"]:
        strength = "Weak"
    else:
        return None

    return {
        "action": "buy now",
        "signal_name": f"BUY NOW: {coin}",
        "coin": coin,
        "coin_address": address,
        "price_usd": price,
        "price_change_24h": ch24h,
        "price_change_1h": ch1h,
        "volume_24h": vol,
        "liquidity_usd": liq,
        "signal_strength": strength,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pair_url": pair.get("url", ""),
    }


def get_buy_signals():
    """Fetch trending Solana tokens via DexScreener and return all buy-now signals."""
    addresses = _fetch_solana_token_addresses()
    if not addresses:
        logger.warning("No Solana token profiles returned from DexScreener.")
        return []

    pairs = _fetch_pairs(addresses)
    signals = []
    seen = set()

    for pair in pairs:
        result = _classify(pair)
        if result and result["coin_address"] not in seen:
            seen.add(result["coin_address"])
            signals.append(result)

    _order = {"Strong": 0, "Moderate": 1, "Weak": 2}
    signals.sort(key=lambda s: (_order.get(s["signal_strength"], 3), -s["price_change_24h"]))

    logger.info("Signal scan complete — %d buy signal(s) found.", len(signals))
    return signals
