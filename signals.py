"""
Buy/sell signal logic using DexScreener public API.
Outputs a list of SignalResult dicts — no API key required.
"""

import json
import urllib.request
from dataclasses import dataclass, asdict
from typing import Optional
from config import (
    WATCHED_PAIRS, BUY_1H_MIN_PCT, BUY_VOL24H_MIN, BUY_PRESSURE_MIN,
    SELL_1H_MAX_PCT, SELL_PRESSURE_MAX,
)

DEXSCREENER_BASE = "https://api.dexscreener.com"


@dataclass
class SignalResult:
    token: str
    symbol: str
    signal: str          # "buy now" | "sell" | "hold"
    price_usd: str
    change_1h: str
    change_6h: str
    change_24h: str
    volume_24h: str
    liquidity_usd: str
    buy_pressure: str
    dexscreener_url: str


def _get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; memecoin-intel/1.0)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"DexScreener API error {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network unreachable: {e.reason}") from e


def _buy_pressure(pair: dict) -> Optional[float]:
    txns = pair.get("txns", {})
    h1 = txns.get("h1", {})
    buys = h1.get("buys", 0)
    sells = h1.get("sells", 0)
    total = buys + sells
    return round(buys / total * 100, 1) if total else None


def _classify(pair: dict) -> str:
    changes = pair.get("priceChange", {})
    ch1 = float(changes.get("h1", 0) or 0)
    vol = float((pair.get("volume") or {}).get("h24", 0) or 0)
    bp  = _buy_pressure(pair)

    if (
        ch1 >= BUY_1H_MIN_PCT
        and vol >= BUY_VOL24H_MIN
        and bp is not None
        and bp >= BUY_PRESSURE_MIN
    ):
        return "buy now"
    if ch1 <= SELL_1H_MAX_PCT or (bp is not None and bp <= SELL_PRESSURE_MAX):
        return "sell"
    return "hold"


def _pair_to_result(pair: dict) -> SignalResult:
    base    = pair.get("baseToken", {})
    bp      = _buy_pressure(pair)
    changes = pair.get("priceChange", {})
    vol     = pair.get("volume") or {}
    liq     = pair.get("liquidity") or {}
    return SignalResult(
        token           = base.get("name", "Unknown"),
        symbol          = base.get("symbol", "???"),
        signal          = _classify(pair),
        price_usd       = str(pair.get("priceUsd", "")),
        change_1h       = str(changes.get("h1", "")),
        change_6h       = str(changes.get("h6", "")),
        change_24h      = str(changes.get("h24", "")),
        volume_24h      = str(vol.get("h24", "")),
        liquidity_usd   = str(liq.get("usd", "")),
        buy_pressure    = f"{bp}%" if bp is not None else "",
        dexscreener_url = pair.get("url", ""),
    )


def _fetch_watched() -> list[dict]:
    pairs = []
    for addr in WATCHED_PAIRS:
        data = _get(f"{DEXSCREENER_BASE}/latest/dex/pairs/{addr}")
        pairs += data.get("pairs") or []
    return pairs


def _fetch_trending() -> list[dict]:
    queries = ["meme", "pepe", "doge", "shib", "wojak"]
    seen: set[str] = set()
    results = []
    for q in queries:
        try:
            data = _get(f"{DEXSCREENER_BASE}/latest/dex/search?q={q}")
        except Exception:
            continue
        for p in data.get("pairs") or []:
            addr = (p.get("baseToken") or {}).get("address", "")
            vol  = float((p.get("volume") or {}).get("h24", 0) or 0)
            if addr and addr not in seen and vol >= 10_000:
                seen.add(addr)
                results.append(p)
    results.sort(
        key=lambda x: float((x.get("volume") or {}).get("h24", 0) or 0),
        reverse=True,
    )
    return results[:20]


def get_signals() -> list[SignalResult]:
    raw_pairs = _fetch_watched() if WATCHED_PAIRS else _fetch_trending()
    return [_pair_to_result(p) for p in raw_pairs]


if __name__ == "__main__":
    results = get_signals()
    print(json.dumps([asdict(r) for r in results], indent=2))
