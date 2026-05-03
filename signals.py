"""
Memecoin buy/sell signal logic using CoinCap API (free, no auth required).
Falls back to CoinGecko if COINGECKO_API_KEY is set.
Signals are based on: RSI-proxy momentum and 7d price trend.

Run directly:  python signals.py
Exit codes:    0 = success, 1 = error
Stdout:        JSON with signal, coin, price, reason
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# CoinCap asset IDs for memecoins (free API, no auth)
COINCAP_IDS = [
    "dogecoin",
    "shiba-inu",
    "pepe",
    "floki",
    "bonk",
    "dogwifhat",
]

COINCAP_BASE = "https://api.coincap.io/v2"

# Optional CoinGecko fallback
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Signal thresholds
RSI_OVERSOLD = 35        # RSI-proxy below this → oversold
PRICE_DROP_7D = -15      # % — large dip sets up reversal opportunity
PRICE_MOMENTUM_24H = 5   # % — minimum upward bounce to confirm buy signal


def _fetch(url: str, headers: dict | None = None, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "memecoin-intel/1.0", **(headers or {})},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def _get_market_data_coincap() -> list[dict]:
    """Fetch via CoinCap v2 (free, no API key needed)."""
    ids = ",".join(COINCAP_IDS)
    url = f"{COINCAP_BASE}/assets?ids={ids}"
    data = _fetch(url)
    coins = []
    for asset in data.get("data", []):
        try:
            change_24h = float(asset.get("changePercent24Hr") or 0)
            coins.append({
                "name": asset.get("name", ""),
                "symbol": (asset.get("symbol") or "").upper(),
                "current_price": float(asset.get("priceUsd") or 0),
                "price_change_percentage_24h": change_24h,
                "price_change_percentage_7d_in_currency": None,  # not in CoinCap v2
                "total_volume": float(asset.get("volumeUsd24Hr") or 0),
                "market_cap": float(asset.get("marketCapUsd") or 0),
            })
        except (TypeError, ValueError):
            continue
    return coins


def _get_market_data_coingecko() -> list[dict]:
    """Fetch via CoinGecko (requires API key)."""
    ids = "dogecoin,shiba-inu,pepe,floki,bonk,dogwifcoin"
    url = (
        f"{COINGECKO_BASE}/coins/markets"
        f"?vs_currency=usd&ids={ids}"
        f"&price_change_percentage=24h,7d&sparkline=false"
    )
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
    return _fetch(url, headers=headers)


def get_market_data() -> list[dict]:
    if COINGECKO_API_KEY:
        return _get_market_data_coingecko()
    return _get_market_data_coincap()


def _rsi_proxy(price_change_24h: float) -> float:
    """RSI proxy (0-100) from 24h price change. -20%→~15, 0%→50, +20%→~85."""
    return max(0.0, min(100.0, 50 + price_change_24h * 1.75))


def evaluate_coin(coin: dict) -> dict | None:
    """
    Return a signal dict if the coin qualifies as 'buy now', else None.
    Criteria: (oversold OR deep 7d dip) AND 24h bounce confirmation.
    """
    name = coin.get("name", "")
    symbol = coin.get("symbol", "").upper()
    price = coin.get("current_price", 0)
    change_24h = coin.get("price_change_percentage_24h") or 0.0
    change_7d = coin.get("price_change_percentage_7d_in_currency")
    volume_24h = coin.get("total_volume", 0)
    market_cap = coin.get("market_cap", 0)

    rsi = _rsi_proxy(change_24h)
    oversold = rsi < RSI_OVERSOLD
    deep_dip_7d = (change_7d is not None) and (change_7d < PRICE_DROP_7D)
    bouncing = change_24h > PRICE_MOMENTUM_24H
    has_volume = volume_24h > 0

    if (oversold or deep_dip_7d) and bouncing and has_volume:
        reasons = []
        if oversold:
            reasons.append(f"RSI-proxy {rsi:.1f} (oversold)")
        if deep_dip_7d:
            reasons.append(f"7d dip {change_7d:.1f}% (reversal setup)")
        reasons.append(f"24h bounce +{change_24h:.1f}%")

        return {
            "signal": "buy now",
            "coin": name,
            "symbol": symbol,
            "price_usd": price,
            "change_24h_pct": round(change_24h, 2),
            "change_7d_pct": round(change_7d, 2) if change_7d is not None else None,
            "rsi_proxy": round(rsi, 1),
            "volume_24h_usd": volume_24h,
            "market_cap_usd": market_cap,
            "reason": " | ".join(reasons),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return None


def run() -> dict:
    try:
        coins = get_market_data()
    except Exception as exc:
        return {
            "signal": "error",
            "error": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    buy_signals = [s for c in coins if (s := evaluate_coin(c))]

    if buy_signals:
        best = max(buy_signals, key=lambda x: x["change_24h_pct"])
        best["all_signals"] = buy_signals
        return best

    return {
        "signal": "hold",
        "coins_checked": len(coins),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _mock_buy_signal() -> dict:
    """Return a realistic 'buy now' signal for pipeline testing."""
    return {
        "signal": "buy now",
        "coin": "Dogecoin",
        "symbol": "DOGE",
        "price_usd": 0.1842,
        "change_24h_pct": 7.43,
        "change_7d_pct": -17.5,
        "rsi_proxy": 25.0,
        "volume_24h_usd": 1_820_000_000,
        "market_cap_usd": 27_400_000_000,
        "reason": "RSI-proxy 25.0 (oversold) | 7d dip -17.5% (reversal setup) | 24h bounce +7.43%",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "all_signals": [],
    }


if __name__ == "__main__":
    if "--test" in sys.argv:
        result = _mock_buy_signal()
    else:
        result = run()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("signal") != "error" else 1)
