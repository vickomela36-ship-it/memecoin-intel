import requests
from dataclasses import dataclass
from datetime import datetime, timezone

from config import DEXSCREENER_API, BUY_PRICE_CHANGE_THRESHOLD, BUY_VOLUME_THRESHOLD


@dataclass
class Signal:
    coin: str
    pair_address: str
    signal: str          # "buy now" | "hold" | "sell"
    confidence: float    # 0.0 – 1.0
    price_usd: float
    price_change_24h: float
    volume_24h: float
    reason: str
    timestamp: str


def _fetch_trending_pairs() -> list[dict]:
    pairs: list[dict] = []
    for chain in ("solana",):
        url = f"{DEXSCREENER_API}/tokens/trending/{chain}"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            pairs.extend(resp.json().get("pairs") or [])
        except Exception as exc:
            print(f"DexScreener fetch error ({chain}): {exc}")
    return pairs


def _score(price_change: float, volume_24h: float, liquidity: float) -> float:
    score = 0.0

    if price_change >= 50:
        score += 0.40
    elif price_change >= 30:
        score += 0.30
    elif price_change >= 15:
        score += 0.20

    if volume_24h >= 1_000_000:
        score += 0.35
    elif volume_24h >= 500_000:
        score += 0.25
    elif volume_24h >= 100_000:
        score += 0.15

    if liquidity >= 500_000:
        score += 0.25
    elif liquidity >= 100_000:
        score += 0.15
    elif liquidity >= 50_000:
        score += 0.10

    return min(score, 1.0)


def _analyze(pair: dict) -> Signal | None:
    try:
        coin = (pair.get("baseToken") or {}).get("symbol", "UNKNOWN")
        pair_address = pair.get("pairAddress", "")
        price_usd = float(pair.get("priceUsd") or 0)
        price_change_24h = float((pair.get("priceChange") or {}).get("h24") or 0)
        volume_24h = float((pair.get("volume") or {}).get("h24") or 0)
        liquidity_usd = float((pair.get("liquidity") or {}).get("usd") or 0)

        confidence = round(_score(price_change_24h, volume_24h, liquidity_usd), 2)

        if price_change_24h >= BUY_PRICE_CHANGE_THRESHOLD and volume_24h >= BUY_VOLUME_THRESHOLD:
            signal = "buy now"
            reason = (
                f"24h +{price_change_24h:.1f}%, "
                f"vol ${volume_24h:,.0f}, "
                f"liq ${liquidity_usd:,.0f}"
            )
        elif price_change_24h <= -20:
            signal = "sell"
            reason = f"24h {price_change_24h:.1f}% — bearish"
        else:
            signal = "hold"
            reason = f"24h {price_change_24h:.1f}% — insufficient momentum"

        return Signal(
            coin=coin,
            pair_address=pair_address,
            signal=signal,
            confidence=confidence,
            price_usd=price_usd,
            price_change_24h=price_change_24h,
            volume_24h=volume_24h,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        print(f"Signal analysis error: {exc}")
        return None


def get_signals() -> list[Signal]:
    pairs = _fetch_trending_pairs()
    seen: set[str] = set()
    signals: list[Signal] = []
    for pair in pairs:
        sig = _analyze(pair)
        if sig and sig.coin not in seen:
            seen.add(sig.coin)
            signals.append(sig)
    signals.sort(key=lambda s: s.confidence, reverse=True)
    return signals
