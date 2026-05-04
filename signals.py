import time
import requests
from datetime import datetime, timezone
from typing import Optional
from config import WATCHED_TOKENS, CHAIN, PRICE_CHANGE_1H_MIN, VOLUME_1H_MIN, LIQUIDITY_MIN

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"


def _get_best_pair(symbol: str) -> Optional[dict]:
    try:
        resp = requests.get(DEXSCREENER_SEARCH, params={"q": symbol}, timeout=10)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        chain_pairs = [p for p in pairs if p.get("chainId") == CHAIN] or pairs
        chain_pairs.sort(
            key=lambda p: float((p.get("liquidity") or {}).get("usd", 0)),
            reverse=True,
        )
        return chain_pairs[0] if chain_pairs else None
    except Exception as e:
        print(f"[signals] fetch error for {symbol}: {e}")
        return None


def _score(pair: dict) -> float:
    pc1h  = float((pair.get("priceChange") or {}).get("h1", 0) or 0)
    pc5m  = float((pair.get("priceChange") or {}).get("m5", 0) or 0)
    vol1h = float((pair.get("volume") or {}).get("h1", 0) or 0)
    txns  = (pair.get("txns") or {}).get("h1", {}) or {}
    buys  = int(txns.get("buys", 0))
    sells = int(txns.get("sells", 0))

    score = 0.0
    score += min(max(pc1h, 0) * 2, 40)                          # momentum (0-40)
    score += min((vol1h / max(VOLUME_1H_MIN, 1)) * 15, 30)      # volume   (0-30)
    total = buys + sells
    if total:
        score += (buys / total) * 20                             # buy pressure (0-20)
    score += min(max(pc5m, 0) * 2, 10)                          # recent spike (0-10)
    return round(score, 1)


def _build_details(pair: dict) -> dict:
    pc1h  = float((pair.get("priceChange") or {}).get("h1", 0) or 0)
    vol1h = float((pair.get("volume") or {}).get("h1", 0) or 0)
    liq   = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
    token = pair.get("baseToken") or {}
    return {
        "signal":        "buy now",
        "token":         token.get("symbol", "UNKNOWN"),
        "token_name":    token.get("name", ""),
        "price_usd":     float(pair.get("priceUsd") or 0),
        "price_change_1h": pc1h,
        "volume_1h":     vol1h,
        "liquidity_usd": liq,
        "score":         _score(pair),
        "reason":        f"+{pc1h:.1f}% in 1h | vol ${vol1h:,.0f} | liq ${liq:,.0f}",
        "pair_address":  pair.get("pairAddress", ""),
        "dex_url":       pair.get("url", ""),
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


def _is_buy(pair: dict) -> bool:
    pc1h  = float((pair.get("priceChange") or {}).get("h1", 0) or 0)
    vol1h = float((pair.get("volume") or {}).get("h1", 0) or 0)
    liq   = float((pair.get("liquidity") or {}).get("usd", 0) or 0)
    return pc1h >= PRICE_CHANGE_1H_MIN and vol1h >= VOLUME_1H_MIN and liq >= LIQUIDITY_MIN


def scan_all_tokens() -> list[dict]:
    """Return list of signal dicts for every token that meets buy criteria."""
    buy_signals = []
    for symbol in WATCHED_TOKENS:
        symbol = symbol.strip()
        if not symbol:
            continue
        pair = _get_best_pair(symbol)
        if pair and _is_buy(pair):
            buy_signals.append(_build_details(pair))
        time.sleep(0.4)  # polite rate-limiting
    return buy_signals
