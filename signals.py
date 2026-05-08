import requests
import json
import os
import random
from datetime import datetime

MEMECOINS = [
    {"id": "dogecoin",  "name": "Dogecoin",    "symbol": "DOGE"},
    {"id": "shiba-inu", "name": "Shiba Inu",   "symbol": "SHIB"},
    {"id": "pepe",      "name": "Pepe",         "symbol": "PEPE"},
    {"id": "floki",     "name": "Floki",        "symbol": "FLOKI"},
    {"id": "bonk",      "name": "Bonk",         "symbol": "BONK"},
    {"id": "dogwifhat", "name": "dogwifhat",    "symbol": "WIF"},
    {"id": "brett",     "name": "Brett",        "symbol": "BRETT"},
    {"id": "mog-coin",  "name": "Mog Coin",     "symbol": "MOG"},
]

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "memecoin-intel/1.0",
}

DEMO_MODE = os.environ.get("SIGNALS_DEMO", "0") == "1"


# --- data fetching ---

def fetch_binance(coin):
    symbol = coin["symbol"] + "USDT"
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    d = r.json()
    return {
        "price_usd":  float(d["lastPrice"]),
        "change_24h": float(d["priceChangePercent"]),
        "volume_usd": float(d["quoteVolume"]),
        "market_cap": None,  # Binance doesn't expose market cap
    }


def fetch_coingecko(ids_str):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    r = requests.get(url, headers=HEADERS, timeout=15, params={
        "vs_currency": "usd",
        "ids": ids_str,
        "order": "market_cap_desc",
        "sparkline": "false",
        "price_change_percentage": "24h",
    })
    r.raise_for_status()
    return {
        d["id"]: {
            "price_usd":  d["current_price"],
            "change_24h": d.get("price_change_percentage_24h") or 0,
            "volume_usd": d.get("total_volume") or 0,
            "market_cap": d.get("market_cap") or 0,
        }
        for d in r.json()
    }


def demo_data(coin):
    """Generates plausible random market data for offline testing."""
    rng = random.Random(coin["id"] + datetime.utcnow().strftime("%Y%m%d%H"))
    price = rng.uniform(0.00001, 5.0)
    change = rng.uniform(-15, 25)
    vol = price * rng.uniform(1e6, 1e9)
    mcap = price * rng.uniform(1e7, 5e10)
    return {"price_usd": price, "change_24h": change, "volume_usd": vol, "market_cap": mcap}


def get_market_data():
    if DEMO_MODE:
        return {c["id"]: demo_data(c) for c in MEMECOINS}

    # Try CoinGecko first (has market cap)
    try:
        ids = ",".join(c["id"] for c in MEMECOINS)
        return fetch_coingecko(ids)
    except Exception:
        pass

    # Fall back to Binance per-coin
    result = {}
    for coin in MEMECOINS:
        try:
            result[coin["id"]] = fetch_binance(coin)
        except Exception:
            pass
    return result


# --- scoring ---

def score_coin(market):
    score = 0
    reasons = []

    change_24h = market.get("change_24h") or 0
    volume_usd = market.get("volume_usd") or 0
    market_cap = market.get("market_cap") or 0
    volume_ratio = volume_usd / market_cap if market_cap else 0

    if change_24h > 10:
        score += 3
        reasons.append(f"+{change_24h:.1f}% in 24h (strong momentum)")
    elif change_24h > 5:
        score += 2
        reasons.append(f"+{change_24h:.1f}% in 24h")
    elif change_24h > 2:
        score += 1
        reasons.append(f"+{change_24h:.1f}% in 24h (mild)")

    if market_cap and volume_ratio > 0.5:
        score += 3
        reasons.append(f"Volume/MCap={volume_ratio:.2f} (high activity)")
    elif market_cap and volume_ratio > 0.3:
        score += 2
        reasons.append(f"Volume/MCap={volume_ratio:.2f} (elevated)")
    elif market_cap and volume_ratio > 0.15:
        score += 1
        reasons.append(f"Volume/MCap={volume_ratio:.2f} (moderate)")
    elif not market_cap and volume_usd > 5_000_000:
        # Binance fallback: raw volume check
        score += 1
        reasons.append(f"24h volume ${volume_usd:,.0f}")

    return score, reasons


# --- main ---

def generate_signals():
    market_data = get_market_data()
    signals = []
    ts = datetime.utcnow().isoformat() + "Z"

    for coin in MEMECOINS:
        market = market_data.get(coin["id"])
        if not market:
            continue

        score, reasons = score_coin(market)

        signal_type = "buy now" if score >= 5 else "hold"
        confidence = min(score * 10, 95) if score >= 5 else max(score * 12, 20)

        signals.append({
            "coin": coin["name"],
            "symbol": coin["symbol"],
            "price_usd": round(market["price_usd"], 8),
            "signal": signal_type,
            "confidence": confidence,
            "score": score,
            "reasons": reasons,
            "timestamp": ts,
            "change_24h": round(market["change_24h"], 2),
            "volume_usd": round(market["volume_usd"], 2),
        })

    return signals


if __name__ == "__main__":
    try:
        signals = generate_signals()
        print(json.dumps(signals, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
