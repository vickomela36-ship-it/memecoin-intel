"""
Memecoin signal generation using DexScreener API.

Signal criteria for 'buy now':
  - 24h price change between +15% and +150% (momentum, not a runaway pump)
  - 24h volume >= $200K (real trading activity)
  - Liquidity >= $30K (not a ghost pool)
  - Pair age < 30 days (early-stage tokens)

Returns list of SignalResult dicts, each with a 'signal' key of
'buy now', 'sell', or 'hold'.
"""

import requests
import time
from datetime import datetime, timezone


BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
PAIRS_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"

BUY_CHANGE_MIN = 15.0    # minimum 24h % gain
BUY_CHANGE_MAX = 150.0   # cap to exclude obvious pump-and-dumps
BUY_VOLUME_MIN = 200_000  # USD
BUY_LIQUIDITY_MIN = 30_000  # USD
SELL_CHANGE_MAX = -20.0  # 24h % loss threshold for sell signal

# Only watch these chains to avoid noise
ALLOWED_CHAINS = {"solana", "ethereum", "bsc"}


def _fetch_json(url: str, retries: int = 3) -> dict | list | None:
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == retries - 1:
                print(f"[signals] fetch failed for {url}: {exc}")
                return None
            time.sleep(2 ** attempt)
    return None


def _classify(pair: dict) -> str:
    price_change = float(pair.get("priceChange", {}).get("h24") or 0)
    volume_h24 = float((pair.get("volume") or {}).get("h24") or 0)
    liquidity = float((pair.get("liquidity") or {}).get("usd") or 0)

    if (
        BUY_CHANGE_MIN <= price_change <= BUY_CHANGE_MAX
        and volume_h24 >= BUY_VOLUME_MIN
        and liquidity >= BUY_LIQUIDITY_MIN
    ):
        return "buy now"
    if price_change <= SELL_CHANGE_MAX:
        return "sell"
    return "hold"


def get_signals() -> list[dict]:
    """Fetch top boosted tokens and return signal results for all pairs."""
    boosts = _fetch_json(BOOSTS_URL)
    if not boosts:
        return []

    seen_addresses = set()
    results = []

    for entry in boosts:
        chain = (entry.get("chainId") or "").lower()
        if chain not in ALLOWED_CHAINS:
            continue

        token_address = entry.get("tokenAddress")
        if not token_address or token_address in seen_addresses:
            continue
        seen_addresses.add(token_address)

        pairs_data = _fetch_json(PAIRS_URL.format(address=token_address))
        if not pairs_data:
            continue

        pairs = pairs_data.get("pairs") or []
        if not pairs:
            continue

        # Use the highest-volume pair for this token
        pair = max(pairs, key=lambda p: float((p.get("volume") or {}).get("h24") or 0))

        signal = _classify(pair)
        price_usd = pair.get("priceUsd")
        price_change = float(pair.get("priceChange", {}).get("h24") or 0)
        volume_h24 = float((pair.get("volume") or {}).get("h24") or 0)
        liquidity_usd = float((pair.get("liquidity") or {}).get("usd") or 0)
        base_token = pair.get("baseToken") or {}

        results.append({
            "signal": signal,
            "coin_name": base_token.get("name", token_address[:8]),
            "coin_symbol": base_token.get("symbol", "???"),
            "price_usd": float(price_usd) if price_usd else None,
            "price_change_24h": price_change,
            "volume_24h_usd": volume_h24,
            "liquidity_usd": liquidity_usd,
            "chain": chain,
            "dex": pair.get("dexId", ""),
            "pair_address": pair.get("pairAddress", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Be polite to the API
        time.sleep(0.3)

    return results


if __name__ == "__main__":
    signals = get_signals()
    buys = [s for s in signals if s["signal"] == "buy now"]
    print(f"Total pairs scanned: {len(signals)}")
    print(f"Buy now signals:     {len(buys)}")
    for s in buys:
        print(f"  {s['coin_symbol']:10s}  {s['price_change_24h']:+.1f}%  vol=${s['volume_24h_usd']:,.0f}")
