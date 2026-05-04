#!/usr/bin/env python3
"""
Memecoin buy signal scanner using DexScreener API.
Outputs a JSON array of buy signals to stdout.
"""
import json
import sys
import requests

SIGNAL_CRITERIA = {
    "min_liquidity_usd": 10_000,
    "min_volume_24h": 50_000,
    "min_price_change_1h_pct": 5.0,
    "max_price_change_1h_pct": 200.0,  # filter extreme pumps
}

SUPPORTED_CHAINS = {"solana", "ethereum", "bsc", "base"}

BOOSTED_TOKENS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
TOKEN_PAIRS_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"


def fetch_boosted_tokens(limit: int = 30) -> list[tuple[str, str]]:
    resp = requests.get(BOOSTED_TOKENS_URL, timeout=10)
    resp.raise_for_status()
    results = []
    for item in resp.json():
        chain = item.get("chainId", "")
        addr = item.get("tokenAddress", "")
        if chain in SUPPORTED_CHAINS and addr:
            results.append((chain, addr))
        if len(results) >= limit:
            break
    return results


def best_pair_for_token(token_address: str) -> dict | None:
    url = TOKEN_PAIRS_URL.format(address=token_address)
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    pairs = resp.json().get("pairs") or []
    if not pairs:
        return None
    return max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd", 0)))


def evaluate(pair: dict) -> dict | None:
    try:
        liquidity = float((pair.get("liquidity") or {}).get("usd", 0))
        volume_24h = float((pair.get("volume") or {}).get("h24", 0))
        price_change_1h = float((pair.get("priceChange") or {}).get("h1", 0))
        price_usd = float(pair.get("priceUsd") or 0)

        c = SIGNAL_CRITERIA
        if not (
            liquidity >= c["min_liquidity_usd"]
            and volume_24h >= c["min_volume_24h"]
            and c["min_price_change_1h_pct"] <= price_change_1h <= c["max_price_change_1h_pct"]
        ):
            return None

        base = pair.get("baseToken") or {}
        return {
            "signal": "buy now",
            "token": base.get("symbol", "UNKNOWN"),
            "token_name": base.get("name", ""),
            "token_address": base.get("address", ""),
            "chain": pair.get("chainId", ""),
            "price_usd": price_usd,
            "price_change_1h_pct": price_change_1h,
            "liquidity_usd": liquidity,
            "volume_24h_usd": volume_24h,
            "dexscreener_url": pair.get("url", ""),
        }
    except (TypeError, ValueError):
        return None


def main() -> None:
    try:
        tokens = fetch_boosted_tokens()
    except Exception as exc:
        print(json.dumps({"error": f"Failed to fetch boosted tokens: {exc}"}), file=sys.stderr)
        print("[]")
        return

    buy_signals: list[dict] = []
    for chain_id, token_address in tokens:
        try:
            pair = best_pair_for_token(token_address)
            if pair:
                signal = evaluate(pair)
                if signal:
                    buy_signals.append(signal)
        except Exception:
            continue

    print(json.dumps(buy_signals, indent=2))


if __name__ == "__main__":
    main()
