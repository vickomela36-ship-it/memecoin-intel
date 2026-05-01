"""Buy/sell signal logic based on DexScreener price/volume momentum."""

import json
import sys
import requests
from config import (
    DEXSCREENER_API,
    BUY_PRICE_CHANGE_5M, BUY_PRICE_CHANGE_1H,
    BUY_VOLUME_5M_USD, BUY_LIQUIDITY_USD,
    SELL_PRICE_CHANGE_5M, SELL_PRICE_CHANGE_1H,
    TARGET_CHAINS, TOP_PAIRS_LIMIT,
)

MEMECOIN_KEYWORDS = [
    "pepe", "doge", "shib", "floki", "bonk", "wif", "meme",
    "cat", "inu", "moon", "wojak", "popcat", "brett", "book",
    "turbo", "neiro", "mog", "ponke", "snek",
]


def _is_memecoin(pair: dict) -> bool:
    name = (pair.get("baseToken", {}).get("name") or "").lower()
    symbol = (pair.get("baseToken", {}).get("symbol") or "").lower()
    return any(kw in name or kw in symbol for kw in MEMECOIN_KEYWORDS)


def _classify(pair: dict) -> str:
    changes = pair.get("priceChange", {})
    p5m = float(changes.get("m5") or 0)
    p1h = float(changes.get("h1") or 0)
    vol5m = float((pair.get("volume") or {}).get("m5") or 0)
    liq = float((pair.get("liquidity") or {}).get("usd") or 0)

    if (
        p5m >= BUY_PRICE_CHANGE_5M
        and p1h >= BUY_PRICE_CHANGE_1H
        and vol5m >= BUY_VOLUME_5M_USD
        and liq >= BUY_LIQUIDITY_USD
    ):
        return "buy now"
    if p5m <= SELL_PRICE_CHANGE_5M or p1h <= SELL_PRICE_CHANGE_1H:
        return "sell"
    return "hold"


def fetch_trending_pairs() -> list[dict]:
    pairs = []
    for chain in TARGET_CHAINS:
        try:
            resp = requests.get(
                f"{DEXSCREENER_API}/search?q=memecoin&chainId={chain}",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            pairs.extend(data.get("pairs") or [])
        except Exception:
            pass
    # Also pull the overall trending endpoint
    try:
        resp = requests.get(
            "https://api.dexscreener.com/token-boosts/top/v1",
            timeout=10,
        )
        resp.raise_for_status()
        boosted = resp.json()
        if isinstance(boosted, list):
            token_addresses = [t.get("tokenAddress") for t in boosted[:20] if t.get("tokenAddress")]
            if token_addresses:
                addr_str = ",".join(token_addresses)
                r2 = requests.get(f"{DEXSCREENER_API}/tokens/{addr_str}", timeout=10)
                r2.raise_for_status()
                pairs.extend(r2.json().get("pairs") or [])
    except Exception:
        pass
    return pairs


def build_signal_entry(pair: dict, signal: str) -> dict:
    changes = pair.get("priceChange", {})
    base = pair.get("baseToken", {})
    return {
        "symbol": base.get("symbol", ""),
        "pair_address": pair.get("pairAddress", ""),
        "signal": signal,
        "price_usd": float(pair.get("priceUsd") or 0),
        "price_change_5m": float(changes.get("m5") or 0),
        "price_change_1h": float(changes.get("h1") or 0),
        "volume_5m_usd": float((pair.get("volume") or {}).get("m5") or 0),
        "liquidity_usd": float((pair.get("liquidity") or {}).get("usd") or 0),
        "dex_url": pair.get("url", ""),
        "chain": pair.get("chainId", ""),
    }


def get_signals(only_buy: bool = False) -> list[dict]:
    raw_pairs = fetch_trending_pairs()
    seen = set()
    results = []
    for pair in raw_pairs:
        addr = pair.get("pairAddress", "")
        if not addr or addr in seen:
            continue
        if not _is_memecoin(pair):
            continue
        seen.add(addr)
        signal = _classify(pair)
        if only_buy and signal != "buy now":
            continue
        results.append(build_signal_entry(pair, signal))
        if len(results) >= TOP_PAIRS_LIMIT:
            break
    return results


if __name__ == "__main__":
    only_buy = "--buy-only" in sys.argv
    signals = get_signals(only_buy=only_buy)
    print(json.dumps(signals, indent=2))
