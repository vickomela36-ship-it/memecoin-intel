"""
Buy/sell signal engine for memecoins.
Fetches live pair data from DexScreener and applies momentum + liquidity filters.
Outputs JSON so callers (Claude loop, dashboard, etc.) can parse results easily.
"""

import json
import sys
import argparse
from datetime import datetime, timezone
import urllib.request
import urllib.error

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search?q={}"
DEXSCREENER_TOKENS = "https://api.dexscreener.com/latest/dex/tokens/{}"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "memecoin-intel/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def score_pair(pair: dict) -> dict:
    """Return signal info for a single DexScreener pair."""
    price_change = pair.get("priceChange", {})
    h1  = float(price_change.get("h1",  0) or 0)
    h6  = float(price_change.get("h6",  0) or 0)
    h24 = float(price_change.get("h24", 0) or 0)

    volume = pair.get("volume", {})
    vol_h24 = float(volume.get("h24", 0) or 0)

    liquidity = pair.get("liquidity", {})
    liq_usd = float(liquidity.get("usd", 0) or 0)

    txns = pair.get("txns", {}).get("h1", {})
    buys  = int(txns.get("buys",  0) or 0)
    sells = int(txns.get("sells", 0) or 0)
    buy_pressure = (buys / (buys + sells)) if (buys + sells) > 0 else 0.5

    token = pair.get("baseToken", {})
    name    = token.get("name",    "Unknown")
    symbol  = token.get("symbol",  "???")
    address = token.get("address", "")
    price_usd = pair.get("priceUsd", "0")
    dex_url   = pair.get("url", "")

    # --- signal logic ---
    if (
        h1  >= 5   and
        h6  >= 10  and
        h24 >= 15  and
        vol_h24 >= 50_000   and
        liq_usd >= 25_000   and
        buy_pressure >= 0.55
    ):
        signal = "buy now"
    elif h24 <= -20 or (h1 <= -10 and liq_usd < 10_000):
        signal = "sell"
    else:
        signal = "hold"

    return {
        "signal":       signal,
        "name":         name,
        "symbol":       symbol,
        "address":      address,
        "price_usd":    price_usd,
        "h1_pct":       h1,
        "h6_pct":       h6,
        "h24_pct":      h24,
        "volume_24h":   vol_h24,
        "liquidity_usd": liq_usd,
        "buy_pressure": round(buy_pressure, 3),
        "dex_url":      dex_url,
        "checked_at":   datetime.now(timezone.utc).isoformat(),
    }


def check_token(address_or_query: str) -> list[dict]:
    """Return scored pairs for a token address or search query."""
    if address_or_query.startswith("0x") or len(address_or_query) > 30:
        data = fetch_json(DEXSCREENER_TOKENS.format(address_or_query))
    else:
        data = fetch_json(DEXSCREENER_SEARCH.format(
            urllib.parse.quote(address_or_query)
        ))
    pairs = data.get("pairs") or []
    # sort by 24h volume descending, take top 5
    pairs.sort(key=lambda p: float((p.get("volume") or {}).get("h24", 0) or 0), reverse=True)
    return [score_pair(p) for p in pairs[:5]]


def check_watchlist(watchlist: list[str]) -> list[dict]:
    results = []
    for item in watchlist:
        try:
            scored = check_token(item)
            results.extend(scored)
        except Exception as exc:
            results.append({"signal": "error", "query": item, "error": str(exc),
                            "checked_at": datetime.now(timezone.utc).isoformat()})
    return results


def buy_now_signals(watchlist: list[str]) -> list[dict]:
    """Return only 'buy now' results from the watchlist."""
    return [r for r in check_watchlist(watchlist) if r.get("signal") == "buy now"]


# --- CLI entry point ---
if __name__ == "__main__":
    import urllib.parse  # imported here to keep top-level imports minimal

    parser = argparse.ArgumentParser(description="Memecoin signal checker")
    parser.add_argument(
        "tokens", nargs="*",
        help="Token addresses or search queries. Falls back to config.WATCHLIST."
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Print all signals, not just buy-now."
    )
    args = parser.parse_args()

    try:
        from config import WATCHLIST
    except ImportError:
        WATCHLIST = []

    targets = args.tokens or WATCHLIST
    if not targets:
        print(json.dumps({"error": "No tokens specified and config.WATCHLIST is empty."}))
        sys.exit(1)

    import urllib.parse  # noqa: F811

    signals = check_watchlist(targets) if args.all else buy_now_signals(targets)
    print(json.dumps(signals, indent=2))
