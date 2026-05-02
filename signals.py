import requests
from dataclasses import dataclass
from typing import Optional

DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
PREFERRED_CHAINS = {"solana", "ethereum", "base"}
TRACKED_TOKENS = [
    "PEPE", "DOGE", "SHIB", "BONK", "WIF", "FLOKI",
    "BRETT", "POPCAT", "MEW", "TURBO", "MOODENG", "GOAT",
]

# Thresholds for a 'buy now' signal
BUY_NOW_MIN_24H_CHANGE = 5.0    # percent
BUY_NOW_MIN_1H_CHANGE = 1.0     # percent
BUY_NOW_MIN_VOLUME_24H = 100_000  # USD
BUY_NOW_MIN_LIQUIDITY = 50_000    # USD
SELL_MAX_24H_CHANGE = -10.0       # percent


@dataclass
class SignalResult:
    token: str
    signal: str          # 'buy now' | 'hold' | 'sell'
    price_usd: float
    market_cap: Optional[float]
    volume_24h: float
    change_24h: float
    change_1h: float
    liquidity: float
    chain: str
    pair_address: str
    notes: str = ""


def _fetch_pairs(symbol: str) -> list[dict]:
    try:
        resp = requests.get(
            DEXSCREENER_SEARCH_URL,
            params={"q": symbol},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("pairs") or []
    except Exception:
        return []


def _best_pair(pairs: list[dict], symbol: str) -> Optional[dict]:
    """Highest-volume pair for symbol on preferred chains."""
    candidates = [
        p for p in pairs
        if p.get("baseToken", {}).get("symbol", "").upper() == symbol.upper()
        and p.get("chainId") in PREFERRED_CHAINS
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: float(p.get("volume", {}).get("h24") or 0))


def _evaluate(pair: dict) -> str:
    change_24h = float(pair.get("priceChange", {}).get("h24") or 0)
    change_1h = float(pair.get("priceChange", {}).get("h1") or 0)
    volume_24h = float(pair.get("volume", {}).get("h24") or 0)
    liquidity = float(pair.get("liquidity", {}).get("usd") or 0)

    if (
        change_24h >= BUY_NOW_MIN_24H_CHANGE
        and change_1h >= BUY_NOW_MIN_1H_CHANGE
        and volume_24h >= BUY_NOW_MIN_VOLUME_24H
        and liquidity >= BUY_NOW_MIN_LIQUIDITY
    ):
        return "buy now"
    if change_24h <= SELL_MAX_24H_CHANGE:
        return "sell"
    return "hold"


def get_signals() -> list[SignalResult]:
    results = []
    for symbol in TRACKED_TOKENS:
        pairs = _fetch_pairs(symbol)
        pair = _best_pair(pairs, symbol)
        if pair is None:
            continue

        change_24h = float(pair.get("priceChange", {}).get("h24") or 0)
        change_1h = float(pair.get("priceChange", {}).get("h1") or 0)
        volume_24h = float(pair.get("volume", {}).get("h24") or 0)
        liquidity = float(pair.get("liquidity", {}).get("usd") or 0)
        price_usd = float(pair.get("priceUsd") or 0)
        raw_mc = pair.get("marketCap")
        market_cap = float(raw_mc) if raw_mc else None

        notes = (
            f"1h: {change_1h:+.2f}% | "
            f"Liq: ${liquidity:,.0f} | "
            f"Chain: {pair.get('chainId', '').upper()}"
        )

        results.append(SignalResult(
            token=symbol,
            signal=_evaluate(pair),
            price_usd=price_usd,
            market_cap=market_cap,
            volume_24h=volume_24h,
            change_24h=change_24h,
            change_1h=change_1h,
            liquidity=liquidity,
            chain=pair.get("chainId", ""),
            pair_address=pair.get("pairAddress", ""),
            notes=notes,
        ))
    return results


if __name__ == "__main__":
    for r in get_signals():
        print(f"{r.token:10s} {r.signal:8s}  ${r.price_usd:.8g}  24h: {r.change_24h:+.1f}%  vol: ${r.volume_24h:,.0f}")
