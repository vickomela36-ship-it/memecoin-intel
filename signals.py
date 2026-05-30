import requests
import logging
from dataclasses import dataclass, field
from typing import Optional
from config import (
    TARGET_CHAIN, MAX_TOKENS_TO_SCAN,
    MIN_PRICE_CHANGE_24H, MIN_PRICE_CHANGE_6H,
    MIN_VOLUME_24H, MIN_MARKET_CAP, MAX_MARKET_CAP,
    MIN_VOLUME_TO_MCAP, MIN_LIQUIDITY,
)

logger = logging.getLogger(__name__)

DEXSCREENER_BASE = "https://api.dexscreener.com"

SIGNAL_BUY_NOW = "buy now"
SIGNAL_WATCH = "watch"
SIGNAL_AVOID = "avoid"


@dataclass
class TokenSignal:
    token_name: str
    ticker: str
    signal: str
    price_usd: float
    price_change_24h: float
    volume_24h: float
    market_cap: float
    contract_address: str
    chain: str
    pair_url: str
    notes: str = ""
    liquidity: float = 0.0
    price_change_6h: float = 0.0
    score: float = 0.0


_SEARCH_QUERIES = [
    "solana meme",
    "solana dog",
    "solana pepe",
    "solana cat",
    "solana moon",
]


def _fetch_trending_pairs(chain: str) -> list[dict]:
    """Fetch trending pairs from DexScreener using the free search endpoint."""
    pairs: list[dict] = []
    seen: set[str] = set()
    queries = _SEARCH_QUERIES if chain.lower() == "solana" else [chain]

    for query in queries:
        try:
            resp = requests.get(
                f"{DEXSCREENER_BASE}/latest/dex/search",
                params={"q": query},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for p in data.get("pairs") or []:
                if p.get("chainId", "").lower() != chain.lower():
                    continue
                addr = p.get("baseToken", {}).get("address", "")
                if addr and addr not in seen:
                    seen.add(addr)
                    pairs.append(p)
                    if len(pairs) >= MAX_TOKENS_TO_SCAN:
                        return pairs
        except Exception as e:
            logger.warning(f"Search query '{query}' failed: {e}")

    return pairs


def _fetch_pairs_by_addresses(chain: str, addresses: list[str]) -> list[dict]:
    """Fetch pair data for a list of token addresses."""
    pairs = []
    batch_size = 30
    for i in range(0, len(addresses), batch_size):
        batch = addresses[i:i + batch_size]
        try:
            resp = requests.get(
                f"{DEXSCREENER_BASE}/latest/dex/tokens/{','.join(batch)}",
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            pairs.extend(data.get("pairs") or [])
        except Exception as e:
            logger.warning(f"Batch fetch failed: {e}")
    return pairs


def _best_pair(pairs: list[dict], token_address: str) -> Optional[dict]:
    """Return the highest-liquidity pair for a token address."""
    candidates = [
        p for p in pairs
        if p.get("baseToken", {}).get("address", "").lower() == token_address.lower()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))


def _score_pair(pair: dict) -> float:
    """Return a composite score (higher = better opportunity)."""
    try:
        price_changes = pair.get("priceChange", {})
        h24 = float(price_changes.get("h24") or 0)
        h6 = float(price_changes.get("h6") or 0)
        h1 = float(price_changes.get("h1") or 0)
        volume = float((pair.get("volume") or {}).get("h24") or 0)
        mcap = float(pair.get("marketCap") or 0)
        liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)
        vol_to_mcap = (volume / mcap) if mcap > 0 else 0

        score = (
            (h24 * 0.35)
            + (h6 * 0.25)
            + (h1 * 0.10)
            + (vol_to_mcap * 100 * 0.20)
            + (min(liquidity / 100_000, 5) * 0.10)
        )
        return round(score, 2)
    except Exception:
        return 0.0


def _classify(pair: dict) -> tuple[str, str]:
    """Return (signal, notes) for a pair based on configured thresholds."""
    try:
        price_changes = pair.get("priceChange", {})
        h24 = float(price_changes.get("h24") or 0)
        h6 = float(price_changes.get("h6") or 0)
        volume = float((pair.get("volume") or {}).get("h24") or 0)
        mcap = float(pair.get("marketCap") or 0)
        liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)
        vol_to_mcap = (volume / mcap) if mcap > 0 else 0

        reasons = []
        fails = []

        if h24 >= MIN_PRICE_CHANGE_24H:
            reasons.append(f"+{h24:.1f}% 24h")
        else:
            fails.append(f"24h change {h24:.1f}% < {MIN_PRICE_CHANGE_24H}%")

        if h6 >= MIN_PRICE_CHANGE_6H:
            reasons.append(f"+{h6:.1f}% 6h")
        else:
            fails.append(f"6h change {h6:.1f}% < {MIN_PRICE_CHANGE_6H}%")

        if volume >= MIN_VOLUME_24H:
            reasons.append(f"vol ${volume:,.0f}")
        else:
            fails.append(f"vol ${volume:,.0f} < ${MIN_VOLUME_24H:,.0f}")

        if MIN_MARKET_CAP <= mcap <= MAX_MARKET_CAP:
            reasons.append(f"mcap ${mcap:,.0f}")
        else:
            fails.append(f"mcap ${mcap:,.0f} out of range")

        if vol_to_mcap >= MIN_VOLUME_TO_MCAP:
            reasons.append(f"vol/mcap {vol_to_mcap:.2f}")
        else:
            fails.append(f"vol/mcap {vol_to_mcap:.2f} < {MIN_VOLUME_TO_MCAP}")

        if liquidity >= MIN_LIQUIDITY:
            reasons.append(f"liq ${liquidity:,.0f}")
        else:
            fails.append(f"liq ${liquidity:,.0f} < ${MIN_LIQUIDITY:,.0f}")

        if not fails:
            return SIGNAL_BUY_NOW, "; ".join(reasons)

        if h24 >= MIN_PRICE_CHANGE_24H * 0.5 and volume >= MIN_VOLUME_24H * 0.5:
            return SIGNAL_WATCH, "; ".join(fails[:2])

        return SIGNAL_AVOID, fails[0] if fails else "below thresholds"
    except Exception as e:
        return SIGNAL_AVOID, f"error: {e}"


def run_scan() -> list[TokenSignal]:
    """Run the full daily scan and return a list of TokenSignal objects."""
    logger.info(f"Starting scan for chain: {TARGET_CHAIN}")
    pairs = _fetch_trending_pairs(TARGET_CHAIN)
    logger.info(f"Fetched {len(pairs)} pairs to evaluate")

    seen_addresses = set()
    results: list[TokenSignal] = []

    for pair in pairs:
        base = pair.get("baseToken", {})
        address = base.get("address", "")
        if not address or address in seen_addresses:
            continue
        seen_addresses.add(address)

        signal, notes = _classify(pair)
        score = _score_pair(pair)
        price_changes = pair.get("priceChange", {})

        results.append(TokenSignal(
            token_name=base.get("name", "Unknown"),
            ticker=base.get("symbol", "???"),
            signal=signal,
            price_usd=float(pair.get("priceUsd") or 0),
            price_change_24h=float(price_changes.get("h24") or 0),
            price_change_6h=float(price_changes.get("h6") or 0),
            volume_24h=float((pair.get("volume") or {}).get("h24") or 0),
            market_cap=float(pair.get("marketCap") or 0),
            liquidity=float((pair.get("liquidity") or {}).get("usd") or 0),
            contract_address=address,
            chain=pair.get("chainId", TARGET_CHAIN),
            pair_url=pair.get("url", ""),
            notes=notes,
            score=score,
        ))

    results.sort(key=lambda t: t.score, reverse=True)
    buy_now = [t for t in results if t.signal == SIGNAL_BUY_NOW]
    logger.info(f"Scan complete: {len(buy_now)} buy now, {len(results) - len(buy_now)} other signals")
    return results
