"""
signals.py — Memecoin buy/sell signal detection using CoinGecko price data.

Signal logic:
- Fetches watched Solana memecoins via CoinGecko /coins/markets
- Emits 'buy now' when 1h price change >= threshold and 24h trend is positive
- Outputs JSON list of signal dicts (empty = no buy signals)
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Set COINGECKO_API_KEY env var to use the demo/pro tier (avoids rate limiting)
import os as _os
_CGKO_KEY = _os.getenv("COINGECKO_API_KEY", "")

WATCHED_TOKENS = [
    "bonk",
    "dogwifcoin",
    "popcat",
    "book-of-meme",
    "cat-in-a-dogs-world",
    "pepe",
    "floki",
    "shiba-inu",
]

# Emit 'buy now' when 1h change exceeds this and 24h trend is positive
BUY_1H_THRESHOLD = 3.0

DEXSCREENER_SEARCH = "https://dexscreener.com/solana/search?q={symbol}"


def _fetch_json(url: str, retries: int = 3) -> list | dict:
    if _CGKO_KEY:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}x_cg_demo_api_key={_CGKO_KEY}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "memecoin-intel/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
            elif e.code == 403:
                raise RuntimeError(
                    "CoinGecko returned 403 Forbidden. "
                    "Set COINGECKO_API_KEY env var with a free demo key from "
                    "https://www.coingecko.com/en/api to resolve this."
                ) from e
            else:
                raise
    raise RuntimeError(f"Failed to fetch after {retries} retries: {url}")


def get_market_data(token_ids: list[str]) -> list[dict]:
    ids = ",".join(token_ids)
    url = (
        f"{COINGECKO_BASE}/coins/markets"
        f"?vs_currency=usd"
        f"&ids={ids}"
        f"&price_change_percentage=1h,6h,24h"
        f"&sparkline=false"
        f"&order=market_cap_desc"
    )
    return _fetch_json(url)


def _fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"


def _fmt_usd(val) -> str:
    if val is None:
        return "N/A"
    if val >= 1_000_000_000:
        return f"${val/1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"${val/1_000_000:.2f}M"
    if val >= 1_000:
        return f"${val/1_000:.2f}K"
    return f"${val:.6f}"


def evaluate_token(token: dict) -> dict | None:
    symbol = (token.get("symbol") or "").upper()
    name = token.get("name") or symbol
    price = token.get("current_price") or 0
    change_1h = token.get("price_change_percentage_1h_in_currency") or 0
    change_6h = token.get("price_change_percentage_6h_in_currency") or 0
    change_24h = token.get("price_change_percentage_24h") or 0
    volume_24h = token.get("total_volume") or 0

    if not (change_1h >= BUY_1H_THRESHOLD and change_24h > 0):
        return None

    buy_pressure = "HIGH" if change_1h > 6.0 else "MODERATE"

    return {
        "signal": "buy now",
        "token": name,
        "symbol": symbol,
        "price_usd": _fmt_usd(price),
        "change_1h": _fmt_pct(change_1h),
        "change_6h": _fmt_pct(change_6h),
        "change_24h": _fmt_pct(change_24h),
        "volume_24h_usd": _fmt_usd(volume_24h),
        "buy_pressure": buy_pressure,
        "dexscreener_url": DEXSCREENER_SEARCH.format(symbol=symbol),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "reason": (
            f"{symbol} surging {change_1h:.1f}% in 1h "
            f"({change_24h:.1f}% 24h) — price {_fmt_usd(price)}"
        ),
    }


def check_signals(token_ids: list[str] | None = None) -> list[dict]:
    """Return list of 'buy now' signal dicts. Empty list = no signals."""
    tokens = token_ids or WATCHED_TOKENS
    market_data = get_market_data(tokens)
    return [s for t in market_data if (s := evaluate_token(t))]


if __name__ == "__main__":
    now = datetime.now(timezone.utc).isoformat()
    try:
        results = check_signals()
        if results:
            print(json.dumps(results))
        else:
            print(json.dumps([{"signal": "hold", "checked_at": now, "reason": "No buy signals at this time"}]))
    except Exception as exc:
        print(json.dumps([{"signal": "error", "checked_at": now, "reason": str(exc)}]))
        raise SystemExit(1)
