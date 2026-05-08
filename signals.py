"""
Fetches trending Solana memecoins from DexScreener and emits 'buy now' signals
when a pair meets all configured thresholds.

Usage:
    python signals.py            # prints JSON array of buy signals to stdout
    python signals.py --all      # include all signals regardless of state file
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone

from config import (
    MIN_LIQUIDITY_USD,
    MIN_VOL_LIQ_RATIO,
    MIN_24H_CHANGE_PCT,
    MIN_5M_CHANGE_PCT,
    STATE_FILE,
)

DEXSCREENER_BOOSTS   = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKEN    = "https://api.dexscreener.com/latest/dex/tokens/{}"
DEXSCREENER_SEARCH   = "https://api.dexscreener.com/latest/dex/search?q=solana"
TARGET_CHAIN         = "solana"
MAX_TOKENS_TO_SCAN   = 25
REQUEST_TIMEOUT      = 10


# ── state helpers ──────────────────────────────────────────────────────────────

def load_notified() -> set:
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE) as f:
        return set(json.load(f))


def save_notified(notified: set) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(notified), f)


# ── DexScreener helpers ────────────────────────────────────────────────────────

def _get(url: str) -> dict | list | None:
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_trending_pairs() -> list[dict]:
    """Return raw DexScreener pair objects for trending Solana tokens."""
    pairs: list[dict] = []
    seen_pairs: set[str] = set()

    # Primary source: boosted tokens
    boosts = _get(DEXSCREENER_BOOSTS) or []
    solana_tokens = [t["tokenAddress"] for t in boosts
                     if t.get("chainId") == TARGET_CHAIN][:MAX_TOKENS_TO_SCAN]

    for addr in solana_tokens:
        data = _get(DEXSCREENER_TOKEN.format(addr)) or {}
        for p in (data.get("pairs") or []):
            pa = p.get("pairAddress", "")
            if pa and pa not in seen_pairs:
                seen_pairs.add(pa)
                pairs.append(p)

    # Fallback: search endpoint if boosts returned nothing
    if not pairs:
        data = _get(DEXSCREENER_SEARCH) or {}
        for p in (data.get("pairs") or [])[:50]:
            if p.get("chainId") == TARGET_CHAIN:
                pa = p.get("pairAddress", "")
                if pa and pa not in seen_pairs:
                    seen_pairs.add(pa)
                    pairs.append(p)

    return pairs


# ── signal evaluation ──────────────────────────────────────────────────────────

def evaluate_pair(pair: dict) -> dict | None:
    """Return a signal dict if the pair meets buy thresholds, else None."""
    liquidity    = (pair.get("liquidity") or {}).get("usd") or 0
    volume_24h   = (pair.get("volume") or {}).get("h24") or 0
    change_24h   = (pair.get("priceChange") or {}).get("h24") or 0
    change_5m    = (pair.get("priceChange") or {}).get("m5") or 0

    if liquidity < MIN_LIQUIDITY_USD:
        return None

    vol_liq = volume_24h / liquidity if liquidity else 0

    if (vol_liq   >= MIN_VOL_LIQ_RATIO
            and change_24h >= MIN_24H_CHANGE_PCT
            and change_5m  >= MIN_5M_CHANGE_PCT):
        base = pair.get("baseToken") or {}
        return {
            "signal":          "buy now",
            "token_name":      base.get("name", "Unknown"),
            "symbol":          base.get("symbol", ""),
            "price_usd":       str(pair.get("priceUsd") or "0"),
            "change_24h_pct":  round(float(change_24h), 2),
            "volume_24h_usd":  round(float(volume_24h), 2),
            "liquidity_usd":   round(float(liquidity), 2),
            "vol_liq_ratio":   round(vol_liq, 2),
            "pair_address":    pair.get("pairAddress", ""),
            "dexscreener_url": pair.get("url", ""),
            "timestamp":       datetime.now(timezone.utc).isoformat(),
        }
    return None


def get_buy_signals(skip_seen: bool = True) -> list[dict]:
    """
    Return new 'buy now' signals.

    If skip_seen is True (default), pair addresses already in STATE_FILE are
    excluded so each pair only triggers one notification.
    """
    notified = load_notified() if skip_seen else set()
    pairs    = fetch_trending_pairs()

    signals: list[dict] = []
    for pair in pairs:
        sig = evaluate_pair(pair)
        if sig and sig["pair_address"] not in notified:
            signals.append(sig)

    return signals


def mark_notified(pair_addresses: list[str]) -> None:
    """Persist pair addresses so they are not re-alerted."""
    notified = load_notified()
    notified.update(pair_addresses)
    save_notified(notified)


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    skip = "--all" not in sys.argv
    signals = get_buy_signals(skip_seen=skip)
    print(json.dumps(signals, indent=2))
