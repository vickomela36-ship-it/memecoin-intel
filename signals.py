import requests
import json
from datetime import datetime, timezone
from typing import Optional

DEXSCREENER_BASE = "https://api.dexscreener.com"

# Signal thresholds
BUY_NOW_5M_CHANGE = 10.0    # >10% price gain in 5m
BUY_NOW_1H_CHANGE = 5.0     # >5% price gain in 1h
BUY_NOW_VOLUME_5M = 10_000  # >$10k volume in 5m
BUY_NOW_LIQUIDITY = 50_000  # >$50k liquidity
SELL_5M_CHANGE = -10.0      # <-10% in 5m
SELL_1H_CHANGE = -20.0      # <-20% in 1h


def _get(url: str) -> Optional[dict]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[signals] HTTP error {url}: {e}")
        return None


def get_boosted_tokens(chain: str = "solana") -> list[dict]:
    data = _get(f"{DEXSCREENER_BASE}/token-boosts/latest/v1")
    if not data:
        return []
    return [t for t in data if isinstance(t, dict) and t.get("chainId", "").lower() == chain.lower()][:20]


def get_token_pairs(token_address: str) -> list[dict]:
    data = _get(f"{DEXSCREENER_BASE}/latest/dex/tokens/{token_address}")
    if not data:
        return []
    return data.get("pairs") or []


def evaluate_signal(pair: dict) -> str:
    pc = pair.get("priceChange") or {}
    vol = pair.get("volume") or {}
    liq = pair.get("liquidity") or {}

    change_5m = float(pc.get("m5") or 0)
    change_1h = float(pc.get("h1") or 0)
    volume_5m = float(vol.get("m5") or 0)
    liquidity = float(liq.get("usd") or 0)

    if (
        change_5m >= BUY_NOW_5M_CHANGE
        and change_1h >= BUY_NOW_1H_CHANGE
        and volume_5m >= BUY_NOW_VOLUME_5M
        and liquidity >= BUY_NOW_LIQUIDITY
    ):
        return "buy now"

    if change_5m <= SELL_5M_CHANGE or change_1h <= SELL_1H_CHANGE:
        return "sell"

    return "hold"


def scan_signals(chain: str = "solana") -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    results = []

    for token in get_boosted_tokens(chain):
        address = token.get("tokenAddress", "")
        if not address:
            continue

        pairs = get_token_pairs(address)
        if not pairs:
            continue

        # Pick highest-liquidity pair
        pair = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
        pc = pair.get("priceChange") or {}
        vol = pair.get("volume") or {}
        liq = pair.get("liquidity") or {}
        base = pair.get("baseToken") or {}

        results.append({
            "signal": evaluate_signal(pair),
            "symbol": base.get("symbol", "UNKNOWN"),
            "pair_address": pair.get("pairAddress", ""),
            "price_usd": float(pair.get("priceUsd") or 0),
            "price_change_5m": float(pc.get("m5") or 0),
            "price_change_1h": float(pc.get("h1") or 0),
            "volume_5m_usd": float(vol.get("m5") or 0),
            "liquidity_usd": float(liq.get("usd") or 0),
            "timestamp": now,
        })

    return results


if __name__ == "__main__":
    signals = scan_signals()
    print(json.dumps(signals, indent=2))
    buy = [s for s in signals if s["signal"] == "buy now"]
    print(f"\n{len(buy)} BUY NOW signal(s) from {len(signals)} tokens scanned.")
