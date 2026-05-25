import requests
from datetime import datetime, timezone

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"


def get_memecoin_data(top_n: int = 20) -> list[dict]:
    params = {
        "vs_currency": "usd",
        "category": "meme-token",
        "order": "volume_desc",
        "per_page": top_n,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h",
    }
    resp = requests.get(COINGECKO_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _classify(coin: dict) -> str:
    from config import BUY_NOW_CHANGE_THRESHOLD, BUY_NOW_VOLUME_RATIO

    change = coin.get("price_change_percentage_24h") or 0.0
    market_cap = coin.get("market_cap") or 1
    volume = coin.get("total_volume") or 0
    vol_ratio = volume / market_cap

    if change >= BUY_NOW_CHANGE_THRESHOLD and vol_ratio >= BUY_NOW_VOLUME_RATIO:
        return "buy now"
    if change <= -10:
        return "sell"
    return "hold"


def get_signals() -> list[dict]:
    from config import TOP_COINS_TO_SCAN

    coins = get_memecoin_data(top_n=TOP_COINS_TO_SCAN)
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for coin in coins:
        results.append({
            "id": coin["id"],
            "token": coin["symbol"].upper(),
            "name": coin["name"],
            "signal": _classify(coin),
            "price": coin.get("current_price") or 0,
            "change_24h": coin.get("price_change_percentage_24h") or 0,
            "volume_24h": coin.get("total_volume") or 0,
            "market_cap": coin.get("market_cap") or 0,
            "timestamp": now,
        })
    return results


if __name__ == "__main__":
    sigs = get_signals()
    buys = [s for s in sigs if s["signal"] == "buy now"]
    print(f"Scanned {len(sigs)} memecoins — {len(buys)} buy now signal(s)")
    for s in buys:
        print(f"  {s['token']}: ${s['price']:.6f} ({s['change_24h']:+.2f}%)")
