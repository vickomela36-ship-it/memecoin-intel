import requests
from config import TRACKED_COINS, COINGECKO_API_KEY, BUY_NOW_MIN_SCORE, BUY_NOW_MIN_PRICE_CHANGE

COINGECKO_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"


def fetch_coin_data(coin_ids: list) -> list:
    params = {
        "ids": ",".join(coin_ids),
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": len(coin_ids),
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d",
    }
    if COINGECKO_API_KEY:
        params["x_cg_demo_api_key"] = COINGECKO_API_KEY

    resp = requests.get(COINGECKO_MARKETS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def compute_signal(coin: dict) -> dict:
    price_change_24h = coin.get("price_change_percentage_24h") or 0
    price_change_1h = coin.get("price_change_percentage_1h_in_currency") or 0
    price_change_7d = coin.get("price_change_percentage_7d_in_currency") or 0
    volume_24h = coin.get("total_volume") or 0
    market_cap = coin.get("market_cap") or 1
    price = coin.get("current_price") or 0

    # Volume-to-market-cap ratio as % (high = lots of trading activity)
    vol_ratio = (volume_24h / market_cap * 100) if market_cap > 0 else 0

    # Composite score: momentum + volume surge
    momentum_score = price_change_24h * 2.5 + price_change_1h * 1.5
    volume_score = min(vol_ratio * 1.5, 35)
    trend_score = max(price_change_7d * 0.5, 0)  # only reward positive 7d trend
    total_score = momentum_score + volume_score + trend_score

    if price_change_24h >= BUY_NOW_MIN_PRICE_CHANGE and total_score >= BUY_NOW_MIN_SCORE:
        signal_type = "buy now"
    elif price_change_24h <= -10:
        signal_type = "sell"
    else:
        signal_type = "hold"

    confidence = round(min(max(total_score, 0), 100), 1)

    reasons = []
    reasons.append(f"24h: {price_change_24h:+.1f}%")
    if abs(price_change_1h) >= 1:
        reasons.append(f"1h: {price_change_1h:+.1f}%")
    if vol_ratio > 8:
        reasons.append(f"vol/mcap: {vol_ratio:.0f}%")
    if price_change_7d > 0:
        reasons.append(f"7d trend: {price_change_7d:+.1f}%")

    return {
        "coin": coin.get("name", coin.get("id", "Unknown")),
        "symbol": coin.get("symbol", "").upper(),
        "signal_type": signal_type,
        "price_usd": price,
        "confidence": confidence,
        "reason": "; ".join(reasons),
        "price_change_24h": price_change_24h,
    }


def get_signals() -> list:
    try:
        coins_data = fetch_coin_data(TRACKED_COINS)
        return [compute_signal(c) for c in coins_data]
    except Exception as e:
        print(f"Error fetching signals: {e}")
        return []


def get_buy_now_signals() -> list:
    return [s for s in get_signals() if s["signal_type"] == "buy now"]
