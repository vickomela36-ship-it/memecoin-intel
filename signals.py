"""
Buy/sell signal logic for Solana memecoin swing recovery strategy.

Strategy: detect tokens that dumped ≥20% in 6h and are now recovering ≥3% in 1h,
with healthy buy-side pressure and sufficient liquidity.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import requests

import config

DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS_URL  = "https://api.dexscreener.com/latest/dex/tokens/{address}"

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "memecoin-intel/1.0"})


@dataclass
class Signal:
    token_name:   str
    token_symbol: str
    mint_address: str
    pair_address: str
    dex_id:       str
    signal_type:  str   # "BUY_NOW" | "WATCH" | "NONE"
    price_usd:    float
    confidence:   float  # 0.0 – 1.0
    reason:       str
    h1_change:    float
    h6_change:    float
    h24_change:   float
    fdv:          float
    volume_h24:   float
    liquidity:    float
    buy_ratio_h1: float = 0.0
    extra:        dict  = field(default_factory=dict)

    def is_buy_now(self) -> bool:
        return self.signal_type == "BUY_NOW"


def _get(url: str, retries: int = 3) -> Optional[dict | list]:
    for attempt in range(retries):
        try:
            r = _SESSION.get(url, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def fetch_trending_solana_addresses() -> list[str]:
    """Return a deduplicated list of Solana token addresses from DexScreener boosts."""
    data = _get(DEXSCREENER_BOOSTS_URL)
    if not data or not isinstance(data, list):
        return []
    return list({
        item["tokenAddress"]
        for item in data
        if item.get("chainId") == "solana" and item.get("tokenAddress")
    })


def fetch_pairs_for_address(address: str) -> list[dict]:
    """Return all DexScreener pairs for a Solana token address."""
    data = _get(DEXSCREENER_TOKENS_URL.format(address=address))
    if not data:
        return []
    pairs = data.get("pairs") or []
    return [p for p in pairs if p.get("chainId") == "solana"]


def _compute_confidence(pair: dict, h1: float, h6: float, buy_ratio: float) -> float:
    score = 0.0
    if h6 <= -35:
        score += 0.25
    elif h6 <= -25:
        score += 0.15

    if h1 >= 10:
        score += 0.20
    elif h1 >= 5:
        score += 0.10

    vol_h1 = (pair.get("volume") or {}).get("h1", 0)
    vol_h6 = (pair.get("volume") or {}).get("h6", 0)
    avg_h6_hourly = vol_h6 / 6 if vol_h6 else 0
    if avg_h6_hourly and vol_h1 >= avg_h6_hourly * 2:
        score += 0.20
    elif avg_h6_hourly and vol_h1 >= avg_h6_hourly * 1.5:
        score += 0.10

    if buy_ratio >= 0.70:
        score += 0.20
    elif buy_ratio >= 0.60:
        score += 0.10

    fdv = pair.get("fdv") or 0
    if config.MIN_FDV_USD <= fdv <= 10_000_000:
        score += 0.15

    return min(round(score, 2), 1.0)


def analyze_pair(pair: dict) -> Signal:
    """Analyse a single DexScreener pair and return a Signal."""
    base      = pair.get("baseToken") or {}
    name      = base.get("name", "Unknown")
    symbol    = base.get("symbol", "???")
    address   = base.get("address", "")
    pair_addr = pair.get("pairAddress", "")
    dex_id    = pair.get("dexId", "")

    try:
        price = float(pair.get("priceUsd") or 0)
    except (TypeError, ValueError):
        price = 0.0

    changes  = pair.get("priceChange") or {}
    h1       = float(changes.get("h1") or 0)
    h6       = float(changes.get("h6") or 0)
    h24      = float(changes.get("h24") or 0)

    volumes  = pair.get("volume") or {}
    vol_h24  = float(volumes.get("h24") or 0)

    liq      = float((pair.get("liquidity") or {}).get("usd") or 0)
    fdv      = float(pair.get("fdv") or 0)

    txns_h1  = pair.get("txns", {}).get("h1") or {}
    buys_h1  = int(txns_h1.get("buys") or 0)
    sells_h1 = int(txns_h1.get("sells") or 0)
    total_h1 = buys_h1 + sells_h1
    buy_ratio = buys_h1 / total_h1 if total_h1 > 0 else 0.0

    # ── Filter: liquidity, volume, FDV ────────────────────────────────────────
    if (
        liq < config.MIN_LIQUIDITY_USD
        or vol_h24 < config.MIN_VOLUME_H24_USD
        or fdv < config.MIN_FDV_USD
        or fdv > config.MAX_FDV_USD
    ):
        return Signal(
            token_name=name, token_symbol=symbol, mint_address=address,
            pair_address=pair_addr, dex_id=dex_id, signal_type="NONE",
            price_usd=price, confidence=0.0,
            reason="Below minimum liquidity/volume/FDV thresholds",
            h1_change=h1, h6_change=h6, h24_change=h24,
            fdv=fdv, volume_h24=vol_h24, liquidity=liq, buy_ratio_h1=buy_ratio,
        )

    # ── Signal logic ──────────────────────────────────────────────────────────
    is_dump     = h6 <= config.DUMP_THRESHOLD_H6
    is_recovery = h1 >= config.RECOVERY_H1_MIN
    has_buyers  = buy_ratio >= config.MIN_BUY_RATIO

    if is_dump and is_recovery and has_buyers:
        signal_type = "BUY_NOW"
        confidence  = _compute_confidence(pair, h1, h6, buy_ratio)
        reason = (
            f"Dumped {h6:+.1f}% in 6h, recovering {h1:+.1f}% in 1h | "
            f"Buy ratio {buy_ratio:.0%} | "
            f"Liq ${liq:,.0f} | FDV ${fdv:,.0f}"
        )
    elif is_dump and is_recovery:
        signal_type = "WATCH"
        confidence  = _compute_confidence(pair, h1, h6, buy_ratio) * 0.6
        reason = (
            f"Dump {h6:+.1f}% + recovery {h1:+.1f}% but weak buy pressure ({buy_ratio:.0%})"
        )
    else:
        signal_type = "NONE"
        confidence  = 0.0
        reason = f"No signal (h6={h6:+.1f}%, h1={h1:+.1f}%)"

    return Signal(
        token_name=name, token_symbol=symbol, mint_address=address,
        pair_address=pair_addr, dex_id=dex_id, signal_type=signal_type,
        price_usd=price, confidence=confidence, reason=reason,
        h1_change=h1, h6_change=h6, h24_change=h24,
        fdv=fdv, volume_h24=vol_h24, liquidity=liq, buy_ratio_h1=buy_ratio,
    )


def scan_all() -> list[Signal]:
    """Fetch trending Solana tokens and return all BUY_NOW (and WATCH) signals."""
    addresses = fetch_trending_solana_addresses()
    if not addresses:
        return []

    buy_now: list[Signal] = []
    watch:   list[Signal] = []

    seen_mints: set[str] = set()

    for address in addresses:
        pairs = fetch_pairs_for_address(address)
        if not pairs:
            continue

        # Pick the highest-liquidity pair per token
        best = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
        sig  = analyze_pair(best)

        if sig.mint_address in seen_mints:
            continue
        seen_mints.add(sig.mint_address)

        if sig.signal_type == "BUY_NOW":
            buy_now.append(sig)
        elif sig.signal_type == "WATCH":
            watch.append(sig)

        time.sleep(0.2)   # gentle rate-limit

    # Sort by confidence descending
    buy_now.sort(key=lambda s: s.confidence, reverse=True)
    watch.sort(key=lambda s: s.confidence, reverse=True)
    return buy_now + watch
