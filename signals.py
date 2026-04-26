"""
Memecoin buy/sell signal engine using DexScreener public API.
Targets Solana-based tokens (Meteora-compatible chain).

Exit codes: 0 = success, 1 = fetch error
Stdout: single JSON line with signal data
"""

import json
import sys
from datetime import datetime, timezone

import requests

CHAIN = "solana"
BUY_THRESHOLD = 65          # minimum score to emit 'buy now'
MIN_LIQUIDITY_USD = 50_000
MIN_VOLUME_24H = 100_000
MIN_PAIR_AGE_HOURS = 1      # ignore brand-new pairs (rug risk)
DEXSCREENER = "https://api.dexscreener.com"


def _safe(value, default=0.0):
    return value if value is not None else default


def score_pair(pair: dict) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    price_change = pair.get("priceChange") or {}
    h1  = _safe(price_change.get("h1"))
    h6  = _safe(price_change.get("h6"))
    h24 = _safe(price_change.get("h24"))

    volume = pair.get("volume") or {}
    vol_h24 = _safe(volume.get("h24"))

    liquidity = pair.get("liquidity") or {}
    liq_usd = _safe(liquidity.get("usd"))

    txns = pair.get("txns") or {}
    h1_txns = txns.get("h1") or {}
    buys_h1  = _safe(h1_txns.get("buys"))
    sells_h1 = _safe(h1_txns.get("sells"))

    fdv = _safe(pair.get("fdv"))

    # --- 1h momentum (max 25 pts) ---
    if h1 >= 10:
        score += 25; reasons.append(f"+{h1:.1f}% (1h)")
    elif h1 >= 5:
        score += 15; reasons.append(f"+{h1:.1f}% (1h)")
    elif h1 >= 2:
        score += 8;  reasons.append(f"+{h1:.1f}% (1h)")

    # --- 6h momentum (max 20 pts) ---
    if h6 >= 25:
        score += 20; reasons.append(f"+{h6:.1f}% (6h)")
    elif h6 >= 12:
        score += 12; reasons.append(f"+{h6:.1f}% (6h)")
    elif h6 >= 5:
        score += 6;  reasons.append(f"+{h6:.1f}% (6h)")

    # --- 24h momentum (max 15 pts) ---
    if h24 >= 50:
        score += 15; reasons.append(f"+{h24:.1f}% (24h)")
    elif h24 >= 20:
        score += 10; reasons.append(f"+{h24:.1f}% (24h)")

    # --- Volume (max 15 pts) ---
    if vol_h24 >= 2_000_000:
        score += 15; reasons.append(f"${vol_h24/1e6:.1f}M vol")
    elif vol_h24 >= 500_000:
        score += 10; reasons.append(f"${vol_h24/1e3:.0f}K vol")
    elif vol_h24 >= 100_000:
        score += 5;  reasons.append(f"${vol_h24/1e3:.0f}K vol")

    # --- Liquidity (max 15 pts) ---
    if liq_usd >= 1_000_000:
        score += 15; reasons.append(f"${liq_usd/1e6:.1f}M liq")
    elif liq_usd >= 200_000:
        score += 10; reasons.append(f"${liq_usd/1e3:.0f}K liq")
    elif liq_usd >= 50_000:
        score += 5;  reasons.append(f"${liq_usd/1e3:.0f}K liq")

    # --- Buy pressure (max 10 pts) ---
    total_h1 = buys_h1 + sells_h1
    if total_h1 > 0:
        buy_ratio = buys_h1 / total_h1
        if buy_ratio >= 0.70:
            score += 10; reasons.append(f"{buy_ratio*100:.0f}% buys (1h)")
        elif buy_ratio >= 0.60:
            score += 5;  reasons.append(f"{buy_ratio*100:.0f}% buys (1h)")

    # --- FDV/Liquidity ratio: low ratio = undervalued (max 10 pts) ---
    if fdv > 0 and liq_usd > 0:
        ratio = fdv / liq_usd
        if ratio < 5:
            score += 10; reasons.append(f"FDV/Liq {ratio:.1f}x")
        elif ratio < 15:
            score += 5;  reasons.append(f"FDV/Liq {ratio:.1f}x")

    return score, reasons


def fetch_trending_pairs() -> list[dict]:
    """Return Solana pair dicts for trending/boosted tokens."""
    try:
        r = requests.get(f"{DEXSCREENER}/token-boosts/top/v1", timeout=10)
        r.raise_for_status()
        boosts = r.json() or []
    except Exception as exc:
        print(json.dumps({"signal": "error", "reason": f"boost fetch: {exc}"}))
        sys.exit(1)

    addresses = [
        b["tokenAddress"]
        for b in boosts
        if b.get("chainId") == CHAIN and b.get("tokenAddress")
    ][:25]

    if not addresses:
        return []

    try:
        r2 = requests.get(
            f"{DEXSCREENER}/latest/dex/tokens/{','.join(addresses)}",
            timeout=15,
        )
        r2.raise_for_status()
        return r2.json().get("pairs") or []
    except Exception as exc:
        print(json.dumps({"signal": "error", "reason": f"pairs fetch: {exc}"}))
        sys.exit(1)


def get_signal() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    pairs = fetch_trending_pairs()

    best_pair = None
    best_score = 0
    best_reasons: list[str] = []

    for pair in pairs:
        liq_usd  = _safe((pair.get("liquidity") or {}).get("usd"))
        vol_h24  = _safe((pair.get("volume") or {}).get("h24"))
        h1       = _safe((pair.get("priceChange") or {}).get("h1"))
        created  = pair.get("pairCreatedAt")  # epoch ms

        # Basic quality gates
        if liq_usd < MIN_LIQUIDITY_USD or vol_h24 < MIN_VOLUME_24H:
            continue
        if h1 <= 0:
            continue
        if created:
            age_hours = (datetime.now(timezone.utc).timestamp() - created / 1000) / 3600
            if age_hours < MIN_PAIR_AGE_HOURS:
                continue

        score, reasons = score_pair(pair)
        if score > best_score:
            best_score = score
            best_pair = pair
            best_reasons = reasons

    if best_pair and best_score >= BUY_THRESHOLD:
        base = best_pair.get("baseToken") or {}
        return {
            "signal": "buy now",
            "token": f"{base.get('name', '')} ({base.get('symbol', 'UNKNOWN')})",
            "symbol": base.get("symbol", "UNKNOWN"),
            "price_usd": float(best_pair.get("priceUsd") or 0),
            "score": best_score,
            "reason": "; ".join(best_reasons),
            "pair_url": best_pair.get("url", ""),
            "timestamp": now,
        }

    return {
        "signal": "hold",
        "token": "",
        "score": best_score,
        "reason": "No qualifying buy signal found",
        "timestamp": now,
    }


if __name__ == "__main__":
    if "--demo" in sys.argv:
        # Synthetic 'buy now' for pipeline testing (no network required)
        now = datetime.now(timezone.utc).isoformat()
        print(json.dumps({
            "signal": "buy now",
            "token": "DEMO TOKEN (DEMO)",
            "symbol": "DEMO",
            "price_usd": 0.000042,
            "score": 82,
            "reason": "+12.3% (1h); +31.5% (6h); $2.1M vol; $450K liq; 73% buys (1h)",
            "pair_url": "https://dexscreener.com/solana/demo",
            "timestamp": now,
        }))
    else:
        print(json.dumps(get_signal()))
