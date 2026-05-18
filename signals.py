"""Buy/sell signal logic — fetches Solana memecoin pairs from DexScreener."""

import requests
from dataclasses import dataclass

DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"

# Thresholds for a 'buy now' signal
BUY_MIN_VOLUME_24H = 100_000      # $100k volume in last 24h
BUY_MIN_PRICE_CHANGE_24H = 15.0   # at least +15% price move in 24h
BUY_MIN_LIQUIDITY = 50_000        # $50k liquidity floor
BUY_MAX_MARKET_CAP = 50_000_000   # cap at $50M (early-stage gems)

SELL_PRICE_CHANGE_THRESHOLD = -20.0  # -20% triggers sell


@dataclass
class TokenSignal:
    name: str
    symbol: str
    price_usd: float
    volume_24h: float
    market_cap: float
    price_change_24h: float
    liquidity: float
    signal: str  # 'buy now' | 'hold' | 'sell'
    source: str
    notes: str = ""


def _evaluate_signal(pair: dict) -> str:
    try:
        volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        price_change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
        liquidity = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
        market_cap = float(pair.get("marketCap", 0) or 0)
    except (ValueError, TypeError):
        return "hold"

    if (
        volume_24h >= BUY_MIN_VOLUME_24H
        and price_change_24h >= BUY_MIN_PRICE_CHANGE_24H
        and liquidity >= BUY_MIN_LIQUIDITY
        and (market_cap == 0 or market_cap <= BUY_MAX_MARKET_CAP)
    ):
        return "buy now"

    if price_change_24h <= SELL_PRICE_CHANGE_THRESHOLD:
        return "sell"

    return "hold"


def get_signals(query: str = "solana memecoin") -> list[TokenSignal]:
    """Return a list of TokenSignal objects for active Solana pairs."""
    try:
        resp = requests.get(
            DEXSCREENER_SEARCH_URL,
            params={"q": query},
            timeout=20,
        )
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
    except Exception as e:
        print(f"[signals] DexScreener fetch failed: {e}")
        return []

    results: list[TokenSignal] = []

    for pair in pairs:
        if pair.get("chainId") != "solana":
            continue

        base = pair.get("baseToken", {})
        name = base.get("name", "Unknown")
        symbol = base.get("symbol", "?")

        try:
            price_usd = float(pair.get("priceUsd", 0) or 0)
            volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
            market_cap = float(pair.get("marketCap", 0) or 0)
            price_change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
            liquidity = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
        except (ValueError, TypeError):
            continue

        results.append(
            TokenSignal(
                name=name,
                symbol=symbol,
                price_usd=price_usd,
                volume_24h=volume_24h,
                market_cap=market_cap,
                price_change_24h=price_change_24h,
                liquidity=liquidity,
                signal=_evaluate_signal(pair),
                source=pair.get("url", ""),
            )
        )

    return results


if __name__ == "__main__":
    sigs = get_signals()
    buy = [s for s in sigs if s.signal == "buy now"]
    print(f"Scanned {len(sigs)} Solana pairs → {len(buy)} buy now signal(s)")
    for s in buy:
        print(f"  {s.symbol}: ${s.price_usd} | vol ${s.volume_24h:,.0f} | +{s.price_change_24h:.1f}%")
