import requests
from config import (
    TRACKED_TOKENS,
    BUY_SIGNAL_MIN_PRICE_CHANGE_24H,
    BUY_SIGNAL_MIN_VOLUME_24H,
    BUY_SIGNAL_MIN_LIQUIDITY,
    BUY_SIGNAL_MIN_BUY_SELL_RATIO,
)

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"


def fetch_pair_data(chain: str, pair_address: str) -> dict | None:
    url = f"{DEXSCREENER_API}/pairs/{chain}/{pair_address}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        pairs = resp.json().get("pairs")
        return pairs[0] if pairs else None
    except Exception as e:
        print(f"[WARN] Failed to fetch {chain}/{pair_address}: {e}")
        return None


def evaluate_signal(pair: dict) -> str:
    price_change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
    liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0) or 0)

    txns_h1 = pair.get("txns", {}).get("h1", {})
    buys = int(txns_h1.get("buys", 0) or 0)
    sells = int(txns_h1.get("sells", 1) or 1)
    buy_sell_ratio = buys / max(sells, 1)

    if (
        price_change_24h >= BUY_SIGNAL_MIN_PRICE_CHANGE_24H
        and volume_24h >= BUY_SIGNAL_MIN_VOLUME_24H
        and liquidity_usd >= BUY_SIGNAL_MIN_LIQUIDITY
        and buy_sell_ratio >= BUY_SIGNAL_MIN_BUY_SELL_RATIO
    ):
        return "buy now"
    elif price_change_24h <= -5.0:
        return "sell"
    return "hold"


def run_signal_scan() -> list[dict]:
    results = []
    for token in TRACKED_TOKENS:
        pair = fetch_pair_data(token["chain"], token["pair_address"])
        if not pair:
            continue

        signal = evaluate_signal(pair)
        base = pair.get("baseToken", {})
        chain_raw = pair.get("chainId", token["chain"])
        chain_label = {"solana": "Solana", "ethereum": "Ethereum", "bsc": "BSC"}.get(
            chain_raw.lower(), "Other"
        )

        entry = {
            "signal": signal,
            "token_name": base.get("symbol", "UNKNOWN"),
            "chain": chain_label,
            "price_usd": float(pair.get("priceUsd", 0) or 0),
            "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0) or 0),
            "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
            "market_cap": float(pair.get("marketCap", 0) or 0),
            "dexscreener_url": pair.get("url", ""),
        }
        results.append(entry)
        print(
            f"[{signal.upper():8}] {entry['token_name']:10} | "
            f"${entry['price_usd']:.6f} | "
            f"24h: {entry['price_change_24h']:+.1f}% | "
            f"Vol: ${entry['volume_24h']:,.0f}"
        )

    return results
