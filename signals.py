"""
Memecoin buy/sell signal generator.
Returns a signal dict with keys: signal, token, price, timestamp, reason, confidence.
Signal values: 'buy now' | 'sell' | 'hold'

Run standalone: python signals.py
Output: JSON line to stdout
"""

import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Optional integrations — import only if available
# ---------------------------------------------------------------------------
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration (override via env vars or config.py)
# ---------------------------------------------------------------------------
try:
    import config
    WALLET_ADDRESS = getattr(config, "WALLET_ADDRESS", os.getenv("WALLET_ADDRESS", ""))
    BIRDEYE_API_KEY = getattr(config, "BIRDEYE_API_KEY", os.getenv("BIRDEYE_API_KEY", ""))
    TARGET_TOKEN = getattr(config, "TARGET_TOKEN", os.getenv("TARGET_TOKEN", "SOL"))
except ImportError:
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
    BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "")
    TARGET_TOKEN = os.getenv("TARGET_TOKEN", "SOL")

# Signal thresholds
BUY_PRICE_CHANGE_THRESHOLD = float(os.getenv("BUY_PRICE_CHANGE_PCT", "5.0"))   # % 1h gain
SELL_PRICE_CHANGE_THRESHOLD = float(os.getenv("SELL_PRICE_CHANGE_PCT", "-5.0")) # % 1h drop
VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.0"))    # vs 24h avg


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_birdeye_price(token: str) -> dict | None:
    """Fetch 1h OHLCV data from Birdeye for a Solana token symbol."""
    if not REQUESTS_AVAILABLE or not BIRDEYE_API_KEY:
        return None
    url = "https://public-api.birdeye.so/public/history_price"
    headers = {"X-API-KEY": BIRDEYE_API_KEY}
    params = {"address": token, "address_type": "token", "type": "1H", "time_from": 0}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_dexscreener(token_address: str) -> dict | None:
    """Fetch token pair data from DexScreener (no API key required)."""
    if not REQUESTS_AVAILABLE:
        return None
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Signal logic
# ---------------------------------------------------------------------------

def _signal_from_dexscreener(data: dict) -> dict:
    """Derive a signal from DexScreener pair data."""
    pairs = data.get("pairs") or []
    if not pairs:
        return _hold_signal("No pairs found on DexScreener")

    # Use the highest-liquidity Solana pair
    sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
    if not sol_pairs:
        sol_pairs = pairs
    pair = max(sol_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

    price_usd = float(pair.get("priceUsd") or 0)
    price_change_1h = float((pair.get("priceChange") or {}).get("h1") or 0)
    price_change_24h = float((pair.get("priceChange") or {}).get("h24") or 0)
    volume_1h = float((pair.get("volume") or {}).get("h1") or 0)
    volume_24h = float((pair.get("volume") or {}).get("h24") or 0)
    token_name = (pair.get("baseToken") or {}).get("symbol", TARGET_TOKEN)

    avg_hourly_volume = volume_24h / 24 if volume_24h else 0
    volume_spike = (volume_1h / avg_hourly_volume) if avg_hourly_volume else 0

    # Buy: strong 1h gain + volume spike
    if (
        price_change_1h >= BUY_PRICE_CHANGE_THRESHOLD
        and volume_spike >= VOLUME_SPIKE_MULTIPLIER
    ):
        return {
            "signal": "buy now",
            "token": token_name,
            "price": price_usd,
            "price_change_1h_pct": price_change_1h,
            "price_change_24h_pct": price_change_24h,
            "volume_1h_usd": volume_1h,
            "volume_spike_multiplier": round(volume_spike, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": (
                f"+{price_change_1h:.1f}% in 1h with {volume_spike:.1f}x volume spike"
            ),
            "confidence": "high" if price_change_1h >= BUY_PRICE_CHANGE_THRESHOLD * 1.5 else "medium",
            "source": "dexscreener",
        }

    # Sell: sharp 1h drop
    if price_change_1h <= SELL_PRICE_CHANGE_THRESHOLD:
        return {
            "signal": "sell",
            "token": token_name,
            "price": price_usd,
            "price_change_1h_pct": price_change_1h,
            "price_change_24h_pct": price_change_24h,
            "volume_1h_usd": volume_1h,
            "volume_spike_multiplier": round(volume_spike, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": f"{price_change_1h:.1f}% drop in 1h",
            "confidence": "medium",
            "source": "dexscreener",
        }

    return _hold_signal(
        f"No strong signal: 1h={price_change_1h:+.1f}%, vol_spike={volume_spike:.1f}x",
        token=token_name,
        price=price_usd,
        source="dexscreener",
    )


def _hold_signal(reason: str, token: str = TARGET_TOKEN, price: float = 0.0, source: str = "none") -> dict:
    return {
        "signal": "hold",
        "token": token,
        "price": price,
        "price_change_1h_pct": None,
        "price_change_24h_pct": None,
        "volume_1h_usd": None,
        "volume_spike_multiplier": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "confidence": "low",
        "source": source,
    }


def get_signal() -> dict:
    """
    Main entry point. Returns a signal dict.
    Falls back gracefully when API keys / network are unavailable.
    """
    token_address = os.getenv("TOKEN_ADDRESS", TARGET_TOKEN)

    # Try DexScreener first (no API key needed)
    if REQUESTS_AVAILABLE and token_address and token_address != "SOL":
        data = fetch_dexscreener(token_address)
        if data:
            return _signal_from_dexscreener(data)

    # No real data available — return hold with explanation
    return _hold_signal(
        reason=(
            "No TOKEN_ADDRESS env var set, or requests library not installed. "
            "Set TOKEN_ADDRESS to a Solana token mint address to get live signals."
        )
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = get_signal()
    print(json.dumps(result, indent=2))
    # Exit 0 always; callers check result["signal"]
    sys.exit(0)
