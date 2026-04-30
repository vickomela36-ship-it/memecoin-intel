"""Buy/sell signal logic powered by DexScreener (no API key required)."""
import requests
from config import (
    WATCHED_PAIRS,
    BUY_NOW_MIN_PRICE_CHANGE_5M,
    BUY_NOW_MIN_VOLUME_5M_USD,
    BUY_NOW_MIN_LIQUIDITY_USD,
    BUY_NOW_MAX_PRICE_CHANGE_1H,
    SELL_TRIGGER_5M_DROP,
    SELL_TRIGGER_1H_DROP,
)

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/pairs/solana"


def _fetch_pair(pair_address: str) -> dict | None:
    resp = requests.get(f"{DEXSCREENER_API}/{pair_address}", timeout=10)
    resp.raise_for_status()
    pairs = resp.json().get("pairs")
    return pairs[0] if pairs else None


def _classify(pair: dict) -> str:
    pc5m  = float(pair.get("priceChange", {}).get("m5",  0) or 0)
    pc1h  = float(pair.get("priceChange", {}).get("h1",  0) or 0)
    vol5m = float(pair.get("volume",      {}).get("m5",  0) or 0)
    liq   = float(pair.get("liquidity",   {}).get("usd", 0) or 0)

    if (
        pc5m  >= BUY_NOW_MIN_PRICE_CHANGE_5M
        and vol5m >= BUY_NOW_MIN_VOLUME_5M_USD
        and liq   >= BUY_NOW_MIN_LIQUIDITY_USD
        and pc1h  <= BUY_NOW_MAX_PRICE_CHANGE_1H
    ):
        return "buy now"
    if pc5m <= SELL_TRIGGER_5M_DROP or pc1h <= SELL_TRIGGER_1H_DROP:
        return "sell"
    return "hold"


def get_signals() -> list[dict]:
    results = []
    for addr in WATCHED_PAIRS:
        try:
            pair = _fetch_pair(addr)
            if not pair:
                continue
            results.append({
                "pair_address":    addr,
                "symbol":          pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
                "signal":          _classify(pair),
                "price_usd":       float(pair.get("priceUsd", 0) or 0),
                "price_change_5m": float(pair.get("priceChange", {}).get("m5", 0) or 0),
                "price_change_1h": float(pair.get("priceChange", {}).get("h1", 0) or 0),
                "volume_5m_usd":   float(pair.get("volume",    {}).get("m5",  0) or 0),
                "liquidity_usd":   float(pair.get("liquidity", {}).get("usd", 0) or 0),
            })
        except Exception as exc:
            print(f"[signals] error fetching {addr}: {exc}")
    return results
