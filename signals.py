import logging
import requests
from dataclasses import dataclass
from typing import Optional

from config import BUY_SIGNAL_PRICE_CHANGE_1H, BUY_SIGNAL_VOLUME_MIN

logger = logging.getLogger(__name__)

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"
SOLANA_CHAIN = "solana"


@dataclass
class Signal:
    signal_type: str   # always 'buy now' for qualifying signals
    strength: str      # 'Strong', 'Moderate', or 'Weak'
    coin: str
    token_address: str
    price_usd: float
    price_change_1h: float
    price_change_24h: float
    volume_24h: float
    pair_url: str
    notes: str


def _score_pair(pair: dict) -> Optional[Signal]:
    """Return a Signal if the pair meets buy-now criteria, else None."""
    try:
        if pair.get("chainId") != SOLANA_CHAIN:
            return None

        base = pair.get("baseToken") or {}
        symbol = base.get("symbol", "UNKNOWN")
        address = base.get("address", "")

        price_usd = float(pair.get("priceUsd") or 0)
        volume = pair.get("volume") or {}
        volume_24h = float(volume.get("h24") or 0)
        price_change = pair.get("priceChange") or {}
        change_1h = float(price_change.get("h1") or 0)
        change_24h = float(price_change.get("h24") or 0)

        txns = pair.get("txns") or {}
        txns_1h = txns.get("h1") or {}
        buys_1h = int(txns_1h.get("buys") or 0)
        sells_1h = int(txns_1h.get("sells") or 0)
        buy_sell_ratio = (buys_1h / sells_1h) if sells_1h > 0 else float(buys_1h)

        pair_url = pair.get("url", "")

        if volume_24h < BUY_SIGNAL_VOLUME_MIN or change_1h <= 0:
            return None

        notes_parts = []

        strong_change = BUY_SIGNAL_PRICE_CHANGE_1H * 2
        if change_1h >= strong_change and volume_24h >= 500_000 and buy_sell_ratio >= 1.5:
            strength = "Strong"
            notes_parts.append(f"Strong momentum: +{change_1h:.1f}% in 1h")
        elif change_1h >= BUY_SIGNAL_PRICE_CHANGE_1H and volume_24h >= BUY_SIGNAL_VOLUME_MIN:
            strength = "Moderate"
            notes_parts.append(f"Moderate momentum: +{change_1h:.1f}% in 1h")
        elif change_1h >= BUY_SIGNAL_PRICE_CHANGE_1H / 2:
            strength = "Weak"
            notes_parts.append(f"Weak momentum: +{change_1h:.1f}% in 1h")
        else:
            return None

        if buy_sell_ratio >= 1.5:
            notes_parts.append(f"Buy/sell ratio: {buy_sell_ratio:.1f}x")
        if change_24h > 0:
            notes_parts.append(f"24h: +{change_24h:.1f}%")

        return Signal(
            signal_type="buy now",
            strength=strength,
            coin=symbol,
            token_address=address,
            price_usd=price_usd,
            price_change_1h=change_1h,
            price_change_24h=change_24h,
            volume_24h=volume_24h,
            pair_url=pair_url,
            notes=", ".join(notes_parts),
        )
    except Exception as e:
        logger.warning(f"Error scoring pair: {e}")
        return None


def _fetch_pairs_for_addresses(addresses: list[str]) -> list[dict]:
    """Fetch DexScreener pair data for a list of token addresses."""
    pairs: list[dict] = []
    # DexScreener accepts up to 30 comma-separated addresses per request
    for i in range(0, len(addresses), 30):
        chunk = ",".join(addresses[i : i + 30])
        try:
            resp = requests.get(DEXSCREENER_TOKENS_URL.format(chunk), timeout=15)
            resp.raise_for_status()
            pairs.extend(resp.json().get("pairs") or [])
        except requests.RequestException as e:
            logger.warning(f"Failed fetching pairs for chunk: {e}")
    return pairs


def get_buy_signals() -> list[Signal]:
    """
    Fetch top-boosted Solana tokens from DexScreener, score them, and return
    those that qualify as 'buy now' sorted by strength then 1h price change.
    """
    try:
        resp = requests.get(DEXSCREENER_BOOSTS_URL, timeout=15)
        resp.raise_for_status()
        boosted: list[dict] = resp.json()
    except requests.RequestException as e:
        logger.error(f"DexScreener boosts API error: {e}")
        return []

    addresses = [
        t["tokenAddress"]
        for t in boosted[:40]
        if t.get("chainId") == SOLANA_CHAIN and t.get("tokenAddress")
    ]

    if not addresses:
        logger.warning("No boosted Solana tokens found")
        return []

    pairs = _fetch_pairs_for_addresses(addresses)

    seen_addresses: set[str] = set()
    signals: list[Signal] = []

    for pair in pairs:
        addr = (pair.get("baseToken") or {}).get("address", "")
        if addr in seen_addresses:
            continue
        seen_addresses.add(addr)

        sig = _score_pair(pair)
        if sig:
            signals.append(sig)

    strength_rank = {"Strong": 0, "Moderate": 1, "Weak": 2}
    signals.sort(key=lambda s: (strength_rank.get(s.strength, 3), -s.price_change_1h))

    logger.info(f"Signal check complete — {len(signals)} buy signal(s) found")
    return signals
