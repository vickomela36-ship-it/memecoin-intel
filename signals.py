import requests
import json
import os
from datetime import datetime, timezone


DEXSCREENER_BOOSTS_URL = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKENS_URL  = "https://api.dexscreener.com/latest/dex/tokens/{address}"

# Thresholds
MIN_1H_CHANGE    = 15.0    # % price gain in 1 h
MIN_24H_CHANGE   = 50.0    # % price gain in 24 h
MIN_VOLUME_24H   = 50_000  # USD
MIN_LIQUIDITY    = 20_000  # USD
VOL_FDV_RATIO    = 0.30    # volume / FDV

DEMO_MODE = os.getenv("SIGNALS_DEMO", "0") == "1"


def _fetch_pairs(token_address: str) -> list:
    try:
        r = requests.get(
            DEXSCREENER_TOKENS_URL.format(address=token_address),
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception:
        return []


def _classify(pair: dict) -> tuple[str, list[str]]:
    pc  = pair.get("priceChange") or {}
    h1  = float(pc.get("h1")  or 0)
    h24 = float(pc.get("h24") or 0)
    vol24 = float((pair.get("volume")    or {}).get("h24") or 0)
    liq   = float((pair.get("liquidity") or {}).get("usd") or 0)
    fdv   = float(pair.get("fdv") or 0)

    reasons = []
    if h1 >= MIN_1H_CHANGE and vol24 >= MIN_VOLUME_24H and liq >= MIN_LIQUIDITY:
        reasons.append(f"+{h1:.1f}% in 1h")
    if h24 >= MIN_24H_CHANGE and vol24 >= MIN_VOLUME_24H:
        reasons.append(f"+{h24:.1f}% in 24h")
    if fdv > 0 and (vol24 / fdv) >= VOL_FDV_RATIO and h1 > 5:
        reasons.append(f"vol/FDV={vol24/fdv:.2f}")

    return ("buy now" if reasons else "hold"), reasons


def _demo_signals() -> list[dict]:
    """Return synthetic signals for sandbox / offline environments."""
    ts = _now()
    return [
        {
            "token":            "PEPE (PEPE)",
            "chain":            "ethereum",
            "price_usd":        "0.00001423",
            "price_change_1h":  22.5,
            "price_change_24h": 61.3,
            "volume_24h_usd":   8_200_000,
            "liquidity_usd":    4_100_000,
            "signal":           "buy now",
            "reasons":          "+22.5% in 1h, +61.3% in 24h",
            "pair_url":         "https://dexscreener.com/ethereum/0xpepe",
            "timestamp":        ts,
        },
        {
            "token":            "WIF (WIF)",
            "chain":            "solana",
            "price_usd":        "1.87",
            "price_change_1h":  8.1,
            "price_change_24h": 17.4,
            "volume_24h_usd":   3_100_000,
            "liquidity_usd":    950_000,
            "signal":           "hold",
            "reasons":          "",
            "pair_url":         "https://dexscreener.com/solana/wif",
            "timestamp":        ts,
        },
    ]


def get_signals() -> list[dict]:
    """Return signal dicts for the top boosted tokens."""
    if DEMO_MODE:
        return _demo_signals()

    try:
        resp = requests.get(DEXSCREENER_BOOSTS_URL, timeout=10)
        resp.raise_for_status()
        boosted = resp.json()
    except Exception as exc:
        return [{"error": str(exc), "timestamp": _now()}]

    results = []
    for token in boosted[:30]:
        address = token.get("tokenAddress", "")
        chain   = token.get("chainId", "")
        pairs   = _fetch_pairs(address)
        if not pairs:
            continue

        pair = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
        signal, reasons = _classify(pair)

        base = pair.get("baseToken") or {}
        results.append({
            "token":            f"{base.get('name','?')} ({base.get('symbol','?')})",
            "chain":            chain,
            "price_usd":        pair.get("priceUsd", "0"),
            "price_change_1h":  float((pair.get("priceChange") or {}).get("h1")  or 0),
            "price_change_24h": float((pair.get("priceChange") or {}).get("h24") or 0),
            "volume_24h_usd":   float((pair.get("volume")    or {}).get("h24") or 0),
            "liquidity_usd":    float((pair.get("liquidity") or {}).get("usd") or 0),
            "signal":           signal,
            "reasons":          ", ".join(reasons),
            "pair_url":         pair.get("url", ""),
            "timestamp":        _now(),
        })

    return results


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


if __name__ == "__main__":
    print(json.dumps(get_signals(), indent=2))
