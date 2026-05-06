from __future__ import annotations
import requests
from dataclasses import dataclass
from typing import Literal

Signal = Literal["buy now", "hold", "sell"]

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"


@dataclass
class TokenSignal:
    token: str
    chain: str
    signal: Signal
    price: float
    score: float
    price_change_24h: float
    volume_24h: float
    liquidity: float
    reason: str


def _score_pair(pair: dict) -> float:
    score = 0.0
    pc24 = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    pc1  = float(pair.get("priceChange", {}).get("h1",  0) or 0)
    vol  = float(pair.get("volume", {}).get("h24", 0) or 0)
    liq  = float((pair.get("liquidity") or {}).get("usd", 0) or 0)

    # 24h price change (up to 40 pts)
    if   pc24 >= 50:  score += 40
    elif pc24 >= 20:  score += 25
    elif pc24 >= 5:   score += 10
    elif pc24 <= -20: score -= 20

    # 1h price change (up to 20 pts)
    if   pc1 >= 10:  score += 20
    elif pc1 >= 3:   score += 10
    elif pc1 <= -5:  score -= 10

    # Volume / liquidity ratio (up to 20 pts)
    if liq > 0:
        ratio = vol / liq
        if   ratio >= 3: score += 20
        elif ratio >= 1: score += 10

    # Liquidity depth (up to 20 pts)
    if   liq >= 500_000: score += 20
    elif liq >= 100_000: score += 10

    return max(0.0, min(100.0, score))


def _pair_to_signal(pair: dict, threshold: float) -> TokenSignal:
    symbol = (pair.get("baseToken") or {}).get("symbol", "???")
    chain  = pair.get("chainId", "")
    price  = float(pair.get("priceUsd") or 0)
    pc24   = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    vol    = float(pair.get("volume", {}).get("h24", 0) or 0)
    liq    = float((pair.get("liquidity") or {}).get("usd", 0) or 0)

    score = _score_pair(pair)

    if   score >= threshold: sig: Signal = "buy now"
    elif score <= 30:        sig = "sell"
    else:                    sig = "hold"

    vol_liq = f"{vol/liq:.1f}x" if liq > 0 else "n/a"
    reason  = f"+{pc24:.1f}% 24h | vol/liq={vol_liq} | liq=${liq:,.0f}"

    return TokenSignal(
        token=symbol, chain=chain, signal=sig,
        price=price, score=score,
        price_change_24h=pc24, volume_24h=vol,
        liquidity=liq, reason=reason,
    )


def _search(query: str) -> list[dict]:
    try:
        r = requests.get(DEXSCREENER_SEARCH, params={"q": query}, timeout=15)
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception:
        return []


def _best_pair_per_token(pairs: list[dict]) -> list[dict]:
    """Keep only the highest-liquidity pair per base token symbol."""
    seen: dict[str, dict] = {}
    for p in pairs:
        sym = (p.get("baseToken") or {}).get("symbol", "")
        liq = float((p.get("liquidity") or {}).get("usd", 0) or 0)
        if sym not in seen or liq > float((seen[sym].get("liquidity") or {}).get("usd", 0) or 0):
            seen[sym] = p
    return list(seen.values())


def get_trending_signals(threshold: float) -> list[TokenSignal]:
    pairs: list[dict] = []
    for q in ("solana memecoin", "ethereum memecoin", "base memecoin"):
        pairs.extend(_search(q))
    pairs = _best_pair_per_token(pairs)
    pairs = [p for p in pairs if float((p.get("liquidity") or {}).get("usd", 0) or 0) >= 50_000]
    return [_pair_to_signal(p, threshold) for p in pairs]


def get_signals_for_tokens(tokens: list[str], threshold: float) -> list[TokenSignal]:
    pairs: list[dict] = []
    for t in tokens:
        pairs.extend(_search(t))
    pairs = _best_pair_per_token(pairs)
    return [_pair_to_signal(p, threshold) for p in pairs]


def fetch_signals(watch_tokens: list[str], threshold: float) -> list[TokenSignal]:
    if watch_tokens:
        return get_signals_for_tokens(watch_tokens, threshold)
    return get_trending_signals(threshold)
