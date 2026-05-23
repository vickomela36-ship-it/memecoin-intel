"""
Buy/sell signal logic.
Uses DexScreener API (free, no auth) to fetch live pair data and score each token.
"""

import requests
from dataclasses import dataclass, field
from typing import Literal

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search?q={}"
DEXSCREENER_PAIRS  = "https://api.dexscreener.com/latest/dex/tokens/{}"

Signal = Literal["buy now", "hold", "sell"]


@dataclass
class TokenSignal:
    token: str
    signal: Signal
    price: float
    score: float
    reason: str
    raw: dict = field(default_factory=dict)


def _score_pair(pair: dict) -> tuple[float, str]:
    """
    Score a DEX pair 0-100:
      - 24h price change  (up to 40 pts)
      - 1h  price change  (up to 20 pts)
      - Volume/liquidity  (up to 20 pts)
      - Liquidity depth   (up to 20 pts)
    Returns (score, reason_string).
    """
    score = 0.0
    reasons: list[str] = []

    price_change = pair.get("priceChange", {})
    h24 = float(price_change.get("h24") or 0)
    h1  = float(price_change.get("h1")  or 0)

    if h24 >= 50:
        score += 40; reasons.append(f"+{h24:.1f}% 24h")
    elif h24 >= 20:
        score += 25; reasons.append(f"+{h24:.1f}% 24h")
    elif h24 >= 5:
        score += 10; reasons.append(f"+{h24:.1f}% 24h")
    elif h24 <= -20:
        score -= 20; reasons.append(f"{h24:.1f}% 24h")

    if h1 >= 10:
        score += 20; reasons.append(f"+{h1:.1f}% 1h")
    elif h1 >= 3:
        score += 10; reasons.append(f"+{h1:.1f}% 1h")
    elif h1 <= -5:
        score -= 10; reasons.append(f"{h1:.1f}% 1h")

    volume_h24 = float((pair.get("volume") or {}).get("h24") or 0)
    liquidity  = float((pair.get("liquidity") or {}).get("usd") or 1)
    vol_liq = volume_h24 / liquidity if liquidity else 0
    if vol_liq >= 3:
        score += 20; reasons.append(f"vol/liq={vol_liq:.1f}x")
    elif vol_liq >= 1:
        score += 10; reasons.append(f"vol/liq={vol_liq:.1f}x")

    if liquidity >= 500_000:
        score += 20; reasons.append(f"liq=${liquidity/1e6:.2f}M")
    elif liquidity >= 100_000:
        score += 10; reasons.append(f"liq=${liquidity/1e3:.0f}K")

    return max(0.0, min(100.0, score)), " | ".join(reasons) if reasons else "no strong signals"


def _pair_to_signal(pair: dict, threshold: float) -> TokenSignal:
    base   = pair.get("baseToken", {})
    symbol = base.get("symbol", "UNKNOWN")
    price  = float(pair.get("priceUsd") or 0)
    score, reason = _score_pair(pair)

    if score >= threshold:
        sig: Signal = "buy now"
    elif score <= 30:
        sig = "sell"
    else:
        sig = "hold"

    return TokenSignal(token=symbol, signal=sig, price=price, score=score, reason=reason, raw=pair)


def get_signals_for_tokens(addresses: list[str], threshold: float = 70.0) -> list[TokenSignal]:
    """Fetch signals for specific token contract addresses."""
    results = []
    for addr in addresses:
        try:
            resp = requests.get(DEXSCREENER_PAIRS.format(addr), timeout=10)
            resp.raise_for_status()
            pairs = resp.json().get("pairs") or []
            if not pairs:
                continue
            best = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
            results.append(_pair_to_signal(best, threshold))
        except Exception as exc:
            results.append(TokenSignal(token=addr[:8], signal="hold", price=0, score=0,
                                       reason=f"fetch error: {exc}"))
    return results


def get_trending_signals(threshold: float = 70.0, limit: int = 20) -> list[TokenSignal]:
    """Scan top trending Solana/ETH/Base memecoin pairs on DexScreener."""
    queries = ["solana memecoin", "ethereum memecoin", "base memecoin"]
    seen: set[str] = set()
    results: list[TokenSignal] = []

    for q in queries:
        try:
            resp = requests.get(DEXSCREENER_SEARCH.format(requests.utils.quote(q)), timeout=10)
            resp.raise_for_status()
            pairs = resp.json().get("pairs") or []
            for pair in pairs[:limit]:
                addr = (pair.get("baseToken") or {}).get("address", "")
                if addr in seen:
                    continue
                seen.add(addr)
                results.append(_pair_to_signal(pair, threshold))
        except Exception:
            continue

    return results


def run(watch_tokens: list[str] | None = None, threshold: float = 70.0) -> list[TokenSignal]:
    """Main entry point — returns all signals."""
    if watch_tokens:
        return get_signals_for_tokens(watch_tokens, threshold)
    return get_trending_signals(threshold)
