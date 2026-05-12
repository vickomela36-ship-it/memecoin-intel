import time
import requests
from dataclasses import dataclass

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"


@dataclass
class SignalResult:
    coin: str
    signal: str       # 'buy now' | 'hold' | 'sell'
    price_usd: float
    confidence: float # 0–100
    reason: str


def _fetch_pair(address: str) -> dict | None:
    try:
        resp = requests.get(
            DEXSCREENER_URL.format(address=address),
            timeout=10,
            headers={"User-Agent": "memecoin-intel/1.0"},
        )
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        if not pairs:
            return None
        # Prefer the pair with the highest USD liquidity
        return max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
    except Exception as exc:
        print(f"  Warning: could not fetch {address}: {exc}")
        return None


def _score_pair(pair: dict) -> tuple[str, float, str]:
    """Return (signal, confidence_0_100, reason_string)."""
    price_change_h24 = float((pair.get("priceChange") or {}).get("h24") or 0)
    volume_h24       = float((pair.get("volume")      or {}).get("h24") or 0)
    liquidity_usd    = float((pair.get("liquidity")   or {}).get("usd") or 0)
    txns             = (pair.get("txns") or {}).get("h24") or {}
    buys             = int(txns.get("buys")  or 0)
    sells            = int(txns.get("sells") or 1)   # avoid div/0

    buy_sell_ratio = buys / sells
    score = 50  # neutral baseline
    reasons: list[str] = []

    # Price momentum
    if price_change_h24 >= 20:
        score += 20
        reasons.append(f"+{price_change_h24:.0f}% 24h surge")
    elif price_change_h24 >= 10:
        score += 10
        reasons.append(f"+{price_change_h24:.0f}% 24h gain")
    elif price_change_h24 <= -20:
        score -= 30
        reasons.append(f"{price_change_h24:.0f}% 24h drop")
    elif price_change_h24 <= -10:
        score -= 15
        reasons.append(f"{price_change_h24:.0f}% 24h decline")

    # Buy/sell pressure
    if buy_sell_ratio >= 2.0:
        score += 15
        reasons.append(f"strong buy pressure ({buy_sell_ratio:.1f}× buys vs sells)")
    elif buy_sell_ratio >= 1.5:
        score += 8
        reasons.append(f"buy pressure ({buy_sell_ratio:.1f}×)")
    elif buy_sell_ratio <= 0.5:
        score -= 15
        reasons.append(f"sell pressure ({buy_sell_ratio:.1f}×)")

    # Liquidity health
    if liquidity_usd >= 500_000:
        score += 5
        reasons.append("high liquidity")
    elif liquidity_usd < 50_000:
        score -= 10
        reasons.append("low liquidity risk")

    # Volume spike
    if volume_h24 >= 1_000_000:
        score += 10
        reasons.append(f"high volume (${volume_h24 / 1e6:.1f}M)")

    score = max(0.0, min(100.0, score))

    if score >= 75:
        signal = "buy now"
    elif score <= 35:
        signal = "sell"
    else:
        signal = "hold"

    reason = "; ".join(reasons) if reasons else "no significant signal"
    return signal, score, reason


def run_signals(coins: list[dict]) -> list[SignalResult]:
    """
    coins: list of {"name": str, "address": str}
    Returns a SignalResult per coin that has live data.
    """
    results: list[SignalResult] = []
    for coin in coins:
        pair = _fetch_pair(coin["address"])
        if pair is None:
            continue
        price_usd = float(pair.get("priceUsd") or 0)
        signal, confidence, reason = _score_pair(pair)
        results.append(SignalResult(
            coin=coin["name"],
            signal=signal,
            price_usd=price_usd,
            confidence=confidence,
            reason=reason,
        ))
        time.sleep(0.4)  # stay within DexScreener rate limits
    return results
