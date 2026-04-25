"""
Signal engine — fetches live token data from DexScreener and scores each token.
Score 0–10; score >= BUY_THRESHOLD → signal = "buy now".

Scoring breakdown (10 pts total):
  3 pts  1h price change  (≥5% → 3, ≥2% → 2, ≥0% → 1, negative → 0)
  2 pts  Volume/liquidity ratio   (h1 volume ÷ liquidity ≥ 0.3 → 2, ≥ 0.1 → 1)
  2 pts  Recent momentum vs 24h  (h6 change ≥ 60% of h24 change → 2, ≥ 30% → 1)
  2 pts  24h price change  (≥20% → 2, ≥8% → 1)
  1 pt   Adequate liquidity  (≥ $50k USD)
"""

from __future__ import annotations
import logging
import requests
from config import TOKENS, BUY_THRESHOLD

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search?q={symbol}"
REQUEST_TIMEOUT = 10

logger = logging.getLogger(__name__)


def _best_pair(pairs: list[dict]) -> dict | None:
    """Return the highest-liquidity pair from DexScreener results."""
    valid = [p for p in pairs if p.get("liquidity", {}).get("usd", 0) > 0]
    if not valid:
        return None
    return max(valid, key=lambda p: p["liquidity"]["usd"])


def fetch_token_data(symbol: str) -> dict | None:
    """Return the best DexScreener pair dict for *symbol*, or None on failure."""
    try:
        resp = requests.get(
            DEXSCREENER_SEARCH.format(symbol=symbol),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        return _best_pair(pairs)
    except Exception as exc:
        logger.warning("DexScreener fetch failed for %s: %s", symbol, exc)
        return None


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_score(pair: dict) -> tuple[float, str]:
    """Return (score 0–10, human-readable reason string)."""
    price_change = pair.get("priceChange", {})
    h1  = _safe_float(price_change.get("h1"))
    h6  = _safe_float(price_change.get("h6"))
    h24 = _safe_float(price_change.get("h24"))
    vol_h1    = _safe_float(pair.get("volume", {}).get("h1"))
    liquidity = _safe_float(pair.get("liquidity", {}).get("usd"))

    score = 0.0
    reasons: list[str] = []

    # 1h momentum (3 pts)
    if h1 >= 5:
        score += 3; reasons.append(f"1h +{h1:.1f}%")
    elif h1 >= 2:
        score += 2; reasons.append(f"1h +{h1:.1f}%")
    elif h1 >= 0:
        score += 1; reasons.append(f"1h +{h1:.1f}%")

    # Volume/liquidity pressure (2 pts)
    if liquidity > 0:
        ratio = vol_h1 / liquidity
        if ratio >= 0.3:
            score += 2; reasons.append(f"vol/liq {ratio:.2f}")
        elif ratio >= 0.1:
            score += 1; reasons.append(f"vol/liq {ratio:.2f}")

    # Recent acceleration vs 24h (2 pts)
    if h24 > 0:
        if h6 >= h24 * 0.6:
            score += 2; reasons.append("accelerating h6")
        elif h6 >= h24 * 0.3:
            score += 1; reasons.append("gaining h6")

    # 24h trend (2 pts)
    if h24 >= 20:
        score += 2; reasons.append(f"24h +{h24:.1f}%")
    elif h24 >= 8:
        score += 1; reasons.append(f"24h +{h24:.1f}%")

    # Liquidity floor (1 pt)
    if liquidity >= 50_000:
        score += 1; reasons.append(f"liq ${liquidity:,.0f}")

    reason = " | ".join(reasons) if reasons else "no positive signals"
    return round(score, 2), reason


def run_signal_check() -> list[dict]:
    """
    Check all configured tokens. Returns a list of dicts for every token
    whose score meets BUY_THRESHOLD:
        {token, price, score, reason, signal}
    """
    results = []
    for symbol in TOKENS:
        symbol = symbol.strip().upper()
        pair = fetch_token_data(symbol)
        if pair is None:
            logger.info("No data for %s — skipping", symbol)
            continue

        score, reason = compute_score(pair)
        price = _safe_float(pair.get("priceUsd"))
        signal = "buy now" if score >= BUY_THRESHOLD else "hold"

        logger.info("%s  score=%.1f  signal=%s  price=$%s", symbol, score, signal, price)

        if signal == "buy now":
            results.append({
                "token": symbol,
                "price": price,
                "score": score,
                "reason": reason,
                "signal": signal,
            })

    return results
