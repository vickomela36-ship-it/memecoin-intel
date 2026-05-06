"""
Memecoin buy/sell signal generator using the DexScreener public API.
Run directly to print a JSON result:  python3 signals.py
"""
import json
import sys
import requests
from datetime import datetime, timezone

from config import (
    CHAIN,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_24H_USD,
    BUY_NOW_SCORE_THRESHOLD,
)

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"
DEXSCREENER_BOOSTS = "https://api.dexscreener.com/token-boosts/top/v1"

_HEADERS = {
    "User-Agent": "memecoin-intel/1.0 (signal tracker)",
    "Accept": "application/json",
}


def _fetch_pairs(query: str) -> list[dict]:
    try:
        r = requests.get(DEXSCREENER_SEARCH, params={"q": query}, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return r.json().get("pairs", [])
    except Exception as exc:
        print(f"[signals] search error: {exc}", file=sys.stderr)

    # Fallback: fetch boosted tokens and resolve their pairs
    try:
        r = requests.get(DEXSCREENER_BOOSTS, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        boosts = r.json() if isinstance(r.json(), list) else []
        addresses = [b["tokenAddress"] for b in boosts[:20] if b.get("chainId") == CHAIN and b.get("tokenAddress")]
        if not addresses:
            return []
        addr_str = ",".join(addresses)
        r2 = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{addr_str}",
            headers=_HEADERS,
            timeout=15,
        )
        r2.raise_for_status()
        return r2.json().get("pairs", [])
    except Exception as exc:
        print(f"[signals] boosts fallback error: {exc}", file=sys.stderr)
        return []


def _score(pair: dict) -> tuple[float, str]:
    """Score a pair 0–10 and return (score, human-readable reason)."""
    score = 0.0
    reasons: list[str] = []

    liq = (pair.get("liquidity") or {}).get("usd") or 0
    vol24 = (pair.get("volume") or {}).get("h24") or 0
    pc = pair.get("priceChange") or {}
    pc5m  = pc.get("m5") or 0
    pc1h  = pc.get("h1") or 0
    pc6h  = pc.get("h6") or 0
    pc24h = pc.get("h24") or 0
    txns1h = (pair.get("txns") or {}).get("h1") or {}
    buys   = txns1h.get("buys") or 0
    sells  = txns1h.get("sells") or 0

    # Liquidity (0–2 pts)
    if liq >= 500_000:
        score += 2.0; reasons.append("high liquidity")
    elif liq >= 100_000:
        score += 1.5; reasons.append("solid liquidity")
    elif liq >= 50_000:
        score += 1.0

    # Volume/liquidity ratio (0–2 pts)
    vlr = vol24 / liq if liq else 0
    if vlr >= 3:
        score += 2.0; reasons.append(f"vol/liq ratio {vlr:.1f}x")
    elif vlr >= 1:
        score += 1.5; reasons.append("strong volume")
    elif vlr >= 0.5:
        score += 1.0

    # Price momentum (0–3 pts)
    if pc5m > 5:
        score += 1.0; reasons.append(f"+{pc5m:.1f}% 5m")
    if pc1h > 10:
        score += 1.5; reasons.append(f"+{pc1h:.1f}% 1h")
    elif pc1h > 5:
        score += 1.0; reasons.append(f"+{pc1h:.1f}% 1h")
    if pc6h > 20:
        score += 0.5; reasons.append(f"+{pc6h:.1f}% 6h")

    # Buy pressure (0–2 pts)
    total = buys + sells
    if total > 0:
        buy_ratio = buys / total
        if buy_ratio >= 0.65:
            score += 2.0; reasons.append(f"{buy_ratio*100:.0f}% buys")
        elif buy_ratio >= 0.55:
            score += 1.0; reasons.append(f"{buy_ratio*100:.0f}% buys")

    # 24h positive drift (0–1 pt)
    if pc24h > 50:
        score += 1.0; reasons.append(f"+{pc24h:.0f}% 24h")
    elif pc24h > 20:
        score += 0.5

    reason = ", ".join(reasons) if reasons else "no strong indicators"
    return min(score, 10.0), reason


def get_signal() -> dict:
    """
    Scan trending Solana memecoins and return the strongest signal.

    Returns a dict with keys:
        signal    – "buy now" | "hold" | "no data"
        token     – token name/symbol
        price     – USD price (float or None)
        score     – float 0–10
        reason    – human-readable signal drivers
        timestamp – ISO-8601 UTC
        pair_url  – DexScreener pair link
    """
    pairs = _fetch_pairs(f"pump {CHAIN}")

    qualifying = [
        p for p in pairs
        if p.get("chainId") == CHAIN
        and ((p.get("liquidity") or {}).get("usd") or 0) >= MIN_LIQUIDITY_USD
        and ((p.get("volume") or {}).get("h24") or 0) >= MIN_VOLUME_24H_USD
    ]

    if not qualifying:
        return {
            "signal": "no data",
            "token": None,
            "price": None,
            "score": 0.0,
            "reason": "No qualifying pairs found",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pair_url": "",
        }

    scored = sorted(
        [(_score(p), p) for p in qualifying],
        key=lambda x: x[0][0],
        reverse=True,
    )
    (best_score, best_reason), best_pair = scored[0]

    base = best_pair.get("baseToken") or {}
    token_name = base.get("name") or base.get("symbol") or "Unknown"

    try:
        price = float(best_pair.get("priceUsd") or 0) or None
    except (TypeError, ValueError):
        price = None

    return {
        "signal": "buy now" if best_score >= BUY_NOW_SCORE_THRESHOLD else "hold",
        "token": token_name,
        "price": price,
        "score": round(best_score, 2),
        "reason": best_reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pair_url": best_pair.get("url", ""),
    }


if __name__ == "__main__":
    print(json.dumps(get_signal(), indent=2))
