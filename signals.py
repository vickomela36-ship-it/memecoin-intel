"""Buy/sell signal detection using DexScreener market data."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


@dataclass
class TokenSignal:
    symbol: str
    address: str
    chain: str
    signal: str                   # 'buy now' | 'sell' | 'hold'
    price_usd: float
    price_change_1h: float
    price_change_6h: float
    price_change_24h: float
    volume_24h_usd: float
    market_cap_usd: float
    liquidity_usd: float
    score: int
    reasons: list[str] = field(default_factory=list)
    pair_url: str = ""

    def summary(self) -> str:
        return (
            f"[{self.signal.upper()}] {self.symbol} ({self.chain})\n"
            f"  Price     : ${self.price_usd:.8f}\n"
            f"  1h / 6h / 24h: {self.price_change_1h:+.1f}% / "
            f"{self.price_change_6h:+.1f}% / {self.price_change_24h:+.1f}%\n"
            f"  Volume 24h: ${self.volume_24h_usd:,.0f}\n"
            f"  Market Cap: ${self.market_cap_usd:,.0f}\n"
            f"  Liquidity : ${self.liquidity_usd:,.0f}\n"
            f"  Score     : {self.score} / 6\n"
            f"  Reasons   : {'; '.join(self.reasons)}"
        )


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _fetch_pairs(address: str) -> list[dict]:
    """Return DexScreener pair objects for a token address."""
    url = config.DEXSCREENER_TOKEN_URL.format(address)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("pairs") or []
    except Exception as exc:
        logger.warning("DexScreener fetch failed for %s: %s", address, exc)
        return []


def _fetch_trending() -> list[dict]:
    """Return a list of {address, chain} dicts from DexScreener trending."""
    try:
        resp = requests.get(config.DEXSCREENER_TRENDING_URL, timeout=10)
        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list):
            items = items.get("data", [])
        seen: set[str] = set()
        results = []
        for item in items:
            chain = (item.get("chainId") or "").lower()
            address = item.get("tokenAddress") or ""
            if chain in config.TRENDING_CHAINS and address and address not in seen:
                seen.add(address)
                results.append({"address": address, "chain": chain, "symbol": item.get("description", address[:8])})
                if len(results) >= config.TRENDING_SCAN_LIMIT:
                    break
        return results
    except Exception as exc:
        logger.warning("DexScreener trending fetch failed: %s", exc)
        return []


def _best_pair(pairs: list[dict], chain: Optional[str] = None) -> Optional[dict]:
    """Pick the pair with the highest liquidity on the desired chain."""
    candidates = pairs
    if chain:
        candidates = [p for p in pairs if (p.get("chainId") or "").lower() == chain.lower()] or pairs
    if not candidates:
        return None
    return max(candidates, key=lambda p: _safe_float((p.get("liquidity") or {}).get("usd")))


def _score_pair(pair: dict) -> tuple[int, list[str]]:
    """Score a DexScreener pair object and return (score, reasons)."""
    changes = pair.get("priceChange") or {}
    h1 = _safe_float(changes.get("h1"))
    h6 = _safe_float(changes.get("h6"))
    h24 = _safe_float(changes.get("h24"))
    volume = _safe_float((pair.get("volume") or {}).get("h24"))
    liquidity = _safe_float((pair.get("liquidity") or {}).get("usd"))
    mcap = _safe_float(pair.get("marketCap") or pair.get("fdv"))

    score = 0
    reasons: list[str] = []

    if h1 >= config.MIN_PRICE_CHANGE_1H:
        score += 1
        reasons.append(f"1h +{h1:.1f}%")
    if h6 >= config.MIN_PRICE_CHANGE_6H:
        score += 1
        reasons.append(f"6h +{h6:.1f}%")
    if h24 >= config.MIN_PRICE_CHANGE_24H:
        score += 1
        reasons.append(f"24h +{h24:.1f}%")
    if volume >= config.MIN_VOLUME_24H_USD:
        score += 1
        reasons.append(f"vol ${volume:,.0f}")
    if liquidity >= config.MIN_LIQUIDITY_USD:
        score += 1
        reasons.append(f"liq ${liquidity:,.0f}")
    if mcap > 0 and mcap <= config.MAX_MARKET_CAP_USD:
        score += 1
        reasons.append(f"mcap ${mcap:,.0f}")

    return score, reasons


def _signal_from_score(score: int) -> str:
    if score >= config.BUY_SIGNAL_MIN_SCORE:
        return "buy now"
    if score <= 1:
        return "sell"
    return "hold"


def evaluate_token(symbol: str, address: str, chain: str) -> Optional[TokenSignal]:
    """Evaluate a single token and return its signal."""
    pairs = _fetch_pairs(address)
    pair = _best_pair(pairs, chain)
    if not pair:
        logger.info("No pairs found for %s (%s)", symbol, address)
        return None

    liquidity = _safe_float((pair.get("liquidity") or {}).get("usd"))
    if liquidity < config.MIN_LIQUIDITY_USD:
        logger.info("Skipping %s — liquidity too low ($%s)", symbol, liquidity)
        return None

    changes = pair.get("priceChange") or {}
    score, reasons = _score_pair(pair)
    base_token = pair.get("baseToken") or {}

    return TokenSignal(
        symbol=base_token.get("symbol") or symbol,
        address=base_token.get("address") or address,
        chain=(pair.get("chainId") or chain).lower(),
        signal=_signal_from_score(score),
        price_usd=_safe_float(pair.get("priceUsd")),
        price_change_1h=_safe_float((changes).get("h1")),
        price_change_6h=_safe_float((changes).get("h6")),
        price_change_24h=_safe_float((changes).get("h24")),
        volume_24h_usd=_safe_float((pair.get("volume") or {}).get("h24")),
        market_cap_usd=_safe_float(pair.get("marketCap") or pair.get("fdv")),
        liquidity_usd=liquidity,
        score=score,
        reasons=reasons,
        pair_url=pair.get("url") or "",
    )


def run_scan() -> list[TokenSignal]:
    """
    Scan watchlist (or trending tokens if watchlist is empty).
    Returns all signals regardless of type.
    """
    targets = config.WATCHLIST
    if not targets:
        logger.info("Watchlist empty — scanning trending tokens instead")
        targets = _fetch_trending()

    results: list[TokenSignal] = []
    for token in targets:
        symbol = token.get("symbol", "UNKNOWN")
        address = token.get("address", "")
        chain = token.get("chain", "solana")
        logger.info("Evaluating %s (%s)", symbol, address)
        sig = evaluate_token(symbol, address, chain)
        if sig:
            results.append(sig)
            logger.info(sig.summary())

    buy_signals = [s for s in results if s.signal == "buy now"]
    logger.info(
        "Scan complete — %d tokens evaluated, %d buy signals",
        len(results),
        len(buy_signals),
    )
    return results
