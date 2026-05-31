import requests
import config

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


def fetch_coin_data(coin_ids: list[str]) -> list[dict]:
    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h,7d",
    }
    resp = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def evaluate_signal(coin: dict) -> str:
    change_24h = coin.get("price_change_percentage_24h") or 0.0
    volume = coin.get("total_volume") or 0
    market_cap = coin.get("market_cap") or 1
    volume_ratio = volume / max(market_cap, 1)

    if change_24h >= config.BUY_MIN_CHANGE_24H and volume_ratio >= config.BUY_MIN_VOLUME_RATIO:
        return "Buy Now"
    if change_24h <= config.SELL_MAX_CHANGE_24H:
        return "Sell"
    return "Hold"


def get_signals(coin_ids: list[str]) -> list[dict]:
    coins = fetch_coin_data(coin_ids)
    results = []
    for coin in coins:
        signal = evaluate_signal(coin)
        results.append({
            "id": coin["id"],
            "name": coin["name"],
            "symbol": coin["symbol"].upper(),
            "price": coin.get("current_price") or 0.0,
            "change_24h": coin.get("price_change_percentage_24h") or 0.0,
            "volume_24h": coin.get("total_volume") or 0.0,
            "market_cap": coin.get("market_cap") or 0.0,
            "signal": signal,
        })
    return results
