import requests
from dataclasses import dataclass, field
from typing import Optional
import os

COINGECKO_API = "https://api.coingecko.com/api/v3"

MEMECOIN_IDS = [
    "dogecoin", "shiba-inu", "pepe", "floki", "bonk",
    "dogwifhat", "brett", "mog-coin", "popcat", "book-of-meme"
]


@dataclass
class CoinData:
    id: str
    name: str
    symbol: str
    price_usd: float
    change_24h: float
    change_1h: float
    change_7d: float
    volume_24h: float
    market_cap: float
    signal: Optional[str] = field(default=None)


def _headers() -> dict:
    api_key = os.environ.get("COINGECKO_API_KEY", "")
    if api_key:
        return {"x-cg-demo-api-key": api_key}
    return {}


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
    resp = requests.get(url, params=params, headers=_headers(), timeout=20)
    resp.raise_for_status()

    coins = []
    for item in resp.json():
        coins.append(CoinData(
            id=item["id"],
            name=item["name"],
            symbol=item["symbol"].upper(),
            price_usd=item.get("current_price") or 0.0,
            change_24h=item.get("price_change_percentage_24h") or 0.0,
            change_1h=item.get("price_change_percentage_1h_in_currency") or 0.0,
            change_7d=item.get("price_change_percentage_7d_in_currency") or 0.0,
            volume_24h=item.get("total_volume") or 0.0,
            market_cap=item.get("market_cap") or 0.0,
        ))
    return coins


def _score(coin: CoinData) -> int:
    score = 0
    # Volume surge: volume > 30% of market cap
    if coin.market_cap > 0 and coin.volume_24h / coin.market_cap > 0.30:
        score += 2
    # Short-term momentum
    if coin.change_1h > 2:
        score += 1
    # Medium-term momentum
    if coin.change_24h > 5:
        score += 2
    # Longer-term trend backing the move
    if coin.change_7d > 10:
        score += 1
    # All timeframes aligned
    if coin.change_1h > 0 and coin.change_24h > 0 and coin.change_7d > 0:
        score += 1
    return score


def generate_signals(coin_ids: list = None) -> list:
    ids = coin_ids or MEMECOIN_IDS
    coins = fetch_coin_data(ids)
    for coin in coins:
        s = _score(coin)
        if s >= 4:
            coin.signal = "buy now"
        elif s >= 2:
            coin.signal = "watch"
        else:
            coin.signal = "hold"
    return coins
