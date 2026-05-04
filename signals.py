import requests
import json
from datetime import datetime, timezone

from config import BUY_SIGNAL_SCORE_THRESHOLD, TRENDING_TOKEN_LIMIT


def _fetch_trending_tokens() -> list[dict]:
    """Pull top boosted/trending Solana tokens from DexScreener."""
    try:
        r = requests.get(
            "https://api.dexscreener.com/token-boosts/top/v1",
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        solana = [t for t in data if t.get("chainId") == "solana"]
        return solana[:TRENDING_TOKEN_LIMIT]
    except Exception as e:
        print(f"[signals] fetch_trending error: {e}", flush=True)
        return []


def _score_token(address: str, label: str) -> tuple[float, float, str]:
    """Return (score 0-10, price_usd, reason_string) for one token."""
    try:
        r = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{address}",
            timeout=10,
        )
        r.raise_for_status()
        pairs = r.json().get("pairs") or []
        if not pairs:
            return 0.0, 0.0, "no pairs found"

        # Most-liquid pair
        pair = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))

        ch = pair.get("priceChange") or {}
        vol = pair.get("volume") or {}
        txns_h1 = (pair.get("txns") or {}).get("h1") or {}

        ch1h  = float(ch.get("h1")  or 0)
        ch6h  = float(ch.get("h6")  or 0)
        vol24 = float(vol.get("h24") or 0)
        liq   = float((pair.get("liquidity") or {}).get("usd") or 0)
        mcap  = float(pair.get("marketCap") or 0)
        price = float(pair.get("priceUsd") or 0)
        buys  = int(txns_h1.get("buys")  or 0)
        sells = int(txns_h1.get("sells") or 0)

        score = 0.0
        reasons: list[str] = []

        if ch1h > 20:
            score += 2.0; reasons.append(f"+{ch1h:.1f}% 1h")
        elif ch1h > 10:
            score += 1.0; reasons.append(f"+{ch1h:.1f}% 1h")

        if ch6h > 50:
            score += 2.0; reasons.append(f"+{ch6h:.1f}% 6h")
        elif ch6h > 20:
            score += 1.0; reasons.append(f"+{ch6h:.1f}% 6h")

        if vol24 > 1_000_000:
            score += 2.0; reasons.append(f"vol ${vol24:,.0f}")
        elif vol24 > 100_000:
            score += 1.0; reasons.append(f"vol ${vol24:,.0f}")

        if liq > 50_000:
            score += 1.0; reasons.append(f"liq ${liq:,.0f}")

        if buys > sells * 1.5 and buys > 10:
            score += 1.0; reasons.append(f"buys {buys} vs sells {sells}")

        if 50_000 < mcap < 5_000_000:
            score += 1.0; reasons.append(f"mcap ${mcap:,.0f}")

        return min(score, 10.0), price, " | ".join(reasons) or "low momentum"

    except Exception as e:
        return 0.0, 0.0, f"error: {e}"


def check_signals() -> list[dict]:
    """Return a list of signal dicts for all evaluated tokens."""
    tokens = _fetch_trending_tokens()
    results = []

    for token in tokens:
        address = token.get("tokenAddress", "")
        label = (token.get("description") or address)[:40]

        score, price, reason = _score_token(address, label)

        signal = (
            "buy now" if score >= BUY_SIGNAL_SCORE_THRESHOLD
            else "watch" if score >= 4.0
            else "skip"
        )

        results.append({
            "token":     label,
            "address":   address,
            "signal":    signal,
            "score":     round(score, 1),
            "price":     price,
            "reason":    reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return results


if __name__ == "__main__":
    signals = check_signals()
    buy_now = [s for s in signals if s["signal"] == "buy now"]
    print(json.dumps({"signals": signals, "buy_now_count": len(buy_now), "buy_now": buy_now}, indent=2))
