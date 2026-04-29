import requests
import json
from datetime import datetime, timezone
from typing import Optional

# Signal thresholds
BUY_NOW_5M_CHANGE = 10.0    # >10% gain in 5m
BUY_NOW_1H_CHANGE = 5.0     # >5% gain in 1h
BUY_NOW_VOLUME_5M = 10_000  # >$10k volume in 5m
BUY_NOW_LIQUIDITY = 50_000  # >$50k liquidity
SELL_5M_CHANGE    = -10.0   # <-10% in 5m
SELL_1H_CHANGE    = -20.0   # <-20% in 1h

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "memecoin-intel/1.0"


def _get(url: str, **kwargs) -> Optional[dict]:
    try:
        r = SESSION.get(url, timeout=10, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[signals] {url}: {e}")
        return None


# ── Source 1: DexScreener boosted tokens ─────────────────────────────────────

def _dexscreener_tokens(chain: str) -> list[dict]:
    """Fetch top boosted tokens via DexScreener."""
    data = _get("https://api.dexscreener.com/token-boosts/latest/v1")
    if not data:
        return []
    token_addresses = [
        t["tokenAddress"] for t in data
        if isinstance(t, dict) and t.get("chainId", "").lower() == chain.lower()
    ][:20]

    results = []
    for addr in token_addresses:
        pairs = (_get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}") or {}).get("pairs") or []
        if pairs:
            results.append(max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0)))
    return results


# ── Source 2: GeckoTerminal trending pools ───────────────────────────────────

def _geckoterminal_tokens(chain: str) -> list[dict]:
    """Fetch trending pools from GeckoTerminal and normalize to DexScreener shape."""
    network = chain.lower()
    data = _get(f"https://api.geckoterminal.com/api/v2/networks/{network}/trending_pools",
                params={"page": 1}, headers={"Accept": "application/json;version=20230302"})
    if not data:
        return []

    pairs = []
    for pool in (data.get("data") or [])[:20]:
        attr = pool.get("attributes") or {}
        rel  = pool.get("relationships") or {}
        base_token = (rel.get("base_token") or {}).get("data") or {}

        price_changes = attr.get("price_change_percentage") or {}
        volumes       = attr.get("volume_usd") or {}

        pairs.append({
            "pairAddress": pool.get("id", "").replace(f"{network}_", ""),
            "baseToken": {"symbol": attr.get("name", "").split("/")[0]},
            "priceUsd":  str(attr.get("base_token_price_usd") or 0),
            "priceChange": {
                "m5": float(price_changes.get("m5") or 0),
                "h1": float(price_changes.get("h1") or 0),
            },
            "volume": {
                "m5": float(volumes.get("m5") or 0),
            },
            "liquidity": {
                "usd": float(attr.get("reserve_in_usd") or 0),
            },
        })
    return pairs


# ── Source 3: CoinGecko meme-token market data ───────────────────────────────

def _coingecko_tokens() -> list[dict]:
    """Fetch meme token market data from CoinGecko and normalize to DexScreener shape."""
    data = _get(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={
            "vs_currency": "usd",
            "category": "meme-token",
            "order": "volume_desc",
            "per_page": 20,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "5m,1h",
        },
    )
    if not isinstance(data, list):
        return []

    pairs = []
    for coin in data:
        pct = coin.get("price_change_percentage_1h_in_currency") or 0
        pairs.append({
            "pairAddress": coin.get("id", ""),
            "baseToken": {"symbol": (coin.get("symbol") or "").upper()},
            "priceUsd": str(coin.get("current_price") or 0),
            "priceChange": {
                "m5": 0.0,   # CoinGecko free tier lacks 5m granularity
                "h1": float(pct),
            },
            "volume": {
                "m5": float(coin.get("total_volume") or 0) / 288,  # rough 5m slice
            },
            "liquidity": {
                "usd": float(coin.get("market_cap") or 0) * 0.05,  # rough estimate
            },
        })
    return pairs


# ── Signal evaluation ─────────────────────────────────────────────────────────

def evaluate_signal(pair: dict) -> str:
    pc  = pair.get("priceChange") or {}
    vol = pair.get("volume") or {}
    liq = pair.get("liquidity") or {}

    change_5m = float(pc.get("m5") or 0)
    change_1h = float(pc.get("h1") or 0)
    volume_5m = float(vol.get("m5") or 0)
    liquidity = float(liq.get("usd") or 0)

    if (
        change_5m >= BUY_NOW_5M_CHANGE
        and change_1h >= BUY_NOW_1H_CHANGE
        and volume_5m >= BUY_NOW_VOLUME_5M
        and liquidity >= BUY_NOW_LIQUIDITY
    ):
        return "buy now"

    if change_5m <= SELL_5M_CHANGE or change_1h <= SELL_1H_CHANGE:
        return "sell"

    return "hold"


# ── Main scan ─────────────────────────────────────────────────────────────────

def scan_signals(chain: str = "solana") -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()

    # Try data sources in order; use first one that returns results
    print("[signals] Trying DexScreener…")
    pairs = _dexscreener_tokens(chain)

    if not pairs:
        print("[signals] Trying GeckoTerminal…")
        pairs = _geckoterminal_tokens(chain)

    if not pairs:
        print("[signals] Trying CoinGecko…")
        pairs = _coingecko_tokens()

    if not pairs:
        print("[signals] All data sources unavailable.")
        return []

    results = []
    for pair in pairs:
        pc  = pair.get("priceChange") or {}
        vol = pair.get("volume") or {}
        liq = pair.get("liquidity") or {}
        base = pair.get("baseToken") or {}

        results.append({
            "signal":          evaluate_signal(pair),
            "symbol":          base.get("symbol", "UNKNOWN"),
            "pair_address":    pair.get("pairAddress", ""),
            "price_usd":       float(pair.get("priceUsd") or 0),
            "price_change_5m": float(pc.get("m5") or 0),
            "price_change_1h": float(pc.get("h1") or 0),
            "volume_5m_usd":   float(vol.get("m5") or 0),
            "liquidity_usd":   float(liq.get("usd") or 0),
            "timestamp":       now,
        })

    return results


if __name__ == "__main__":
    signals = scan_signals()
    print(json.dumps(signals, indent=2))
    buy = [s for s in signals if s["signal"] == "buy now"]
    print(f"\n{len(buy)} BUY NOW signal(s) from {len(signals)} tokens scanned.")
