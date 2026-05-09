import requests
from datetime import datetime, timezone
from typing import Optional

COINGECKO_API = "https://api.coingecko.com/api/v3"

DEFAULT_COINS = [
    "dogecoin", "shiba-inu", "pepe", "bonk", "dogwifcoin",
    "floki", "baby-doge-coin", "brett", "book-of-meme", "popcat",
]


def fetch_coin_data(coin_ids: list) -> list:
    url = f"{COINGECKO_API}/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "order": "market_cap_desc",
        "per_page": 50,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def compute_signal(coin: dict) -> dict:
    price_change_24h = coin.get("price_change_percentage_24h") or 0
    price_change_7d = coin.get("price_change_percentage_7d_in_currency") or 0
    price_change_1h = coin.get("price_change_percentage_1h_in_currency") or 0
    volume = coin.get("total_volume") or 0
    market_cap = coin.get("market_cap") or 1
    volume_ratio = volume / market_cap

    score = 0
    reasons = []

    if price_change_24h > 15:
        score += 3
        reasons.append(f"+{price_change_24h:.1f}% in 24h")
    elif price_change_24h > 7:
        score += 2
        reasons.append(f"+{price_change_24h:.1f}% in 24h")
    elif price_change_24h > 2:
        score += 1
        reasons.append(f"+{price_change_24h:.1f}% in 24h")
    elif price_change_24h < -15:
        score -= 3
        reasons.append(f"{price_change_24h:.1f}% in 24h")
    elif price_change_24h < -5:
        score -= 2
        reasons.append(f"{price_change_24h:.1f}% in 24h")
    elif price_change_24h < 0:
        score -= 1
        reasons.append(f"{price_change_24h:.1f}% in 24h")

    if price_change_7d > 30:
        score += 2
        reasons.append(f"+{price_change_7d:.1f}% in 7d")
    elif price_change_7d > 10:
        score += 1
        reasons.append(f"+{price_change_7d:.1f}% in 7d")
    elif price_change_7d < -30:
        score -= 2
        reasons.append(f"{price_change_7d:.1f}% in 7d")
    elif price_change_7d < -10:
        score -= 1
        reasons.append(f"{price_change_7d:.1f}% in 7d")

    # 1h momentum as confirmation
    if price_change_1h > 3:
        score += 1
        reasons.append(f"+{price_change_1h:.1f}% in 1h")
    elif price_change_1h < -3:
        score -= 1
        reasons.append(f"{price_change_1h:.1f}% in 1h")

    if volume_ratio > 0.5:
        score += 2
        reasons.append(f"high volume/mcap {volume_ratio:.2f}")
    elif volume_ratio > 0.2:
        score += 1
        reasons.append(f"moderate volume/mcap {volume_ratio:.2f}")

    if score >= 4:
        signal = "buy now"
        confidence = round(min(score / 8.0, 1.0), 2)
    elif score >= 0:
        signal = "hold"
        confidence = 0.5
    else:
        signal = "sell"
        confidence = round(max(0.1, 1.0 + score / 10.0), 2)

    return {
        "signal_label": f"{coin['symbol'].upper()} - {signal.title()}",
        "coin": coin["symbol"].upper(),
        "coin_id": coin["id"],
        "name": coin["name"],
        "signal": signal,
        "confidence": confidence,
        "price_usd": coin.get("current_price") or 0,
        "price_change_24h": price_change_24h,
        "reason": "; ".join(reasons) if reasons else "neutral momentum",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_signals(coin_ids: Optional[list] = None) -> list:
    if coin_ids is None:
        coin_ids = DEFAULT_COINS
    coins = fetch_coin_data(coin_ids)
    return [compute_signal(c) for c in coins]
