"""
Terminal-based memecoin swing recovery scanner.
Runs every 3 minutes, fetches trending tokens from DexScreener,
and flags dip recovery setups.

Usage: python scanner.py
"""

import time
import requests
from datetime import datetime, timezone

DEXSCREENER_BOOSTS = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens"
SCAN_INTERVAL = 180  # 3 minutes


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def fetch_trending() -> list[dict]:
    try:
        r = requests.get(DEXSCREENER_BOOSTS, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log(f"ERROR fetching trending: {e}")
        return []


def fetch_pairs(address: str) -> list[dict]:
    try:
        r = requests.get(f"{DEXSCREENER_TOKEN}/{address}", timeout=15)
        r.raise_for_status()
        return r.json().get("pairs") or []
    except Exception as e:
        log(f"  Pair fetch error for {address[:12]}...: {e}")
        return []


def classify_signal(h1: float, h6: float, h24: float) -> str:
    recovering = h1 > 2.0
    if h24 <= -30 and recovering:
        return "STRONG DIP"
    if h6 <= -25 and recovering:
        return "BUY DIP"
    if (h6 <= -20 or h24 <= -25) and h1 > 0:
        return "WATCH"
    return "SKIP"


def fmt_price(p: float) -> str:
    if p == 0: return "$0"
    if p < 0.0000001: return f"${p:.12f}"
    if p < 0.00001:   return f"${p:.10f}"
    if p < 0.001:     return f"${p:.8f}"
    if p < 1:         return f"${p:.6f}"
    return f"${p:,.4f}"


def fmt_usd(v: float) -> str:
    if v >= 1_000_000: return f"${v/1e6:.1f}M"
    if v >= 1_000:     return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def scan_once():
    """Run a single scan cycle."""
    log("=" * 65)
    log("SCANNING for dip recovery setups...")
    log("=" * 65)

    trending = fetch_trending()
    if not trending:
        log("No trending tokens returned.")
        return

    log(f"Fetched {len(trending)} boosted tokens — filtering for Solana...")

    seen = set()
    signals_found = 0

    for token in trending:
        address = token.get("tokenAddress", "")
        chain = token.get("chainId", "")

        if not address or address in seen:
            continue
        if chain and chain != "solana":
            continue
        seen.add(address)

        pairs = fetch_pairs(address)
        sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
        if not sol_pairs:
            continue

        best = max(sol_pairs, key=lambda p: float(p.get("volume", {}).get("h24", 0) or 0))

        pc = best.get("priceChange", {})
        h1  = float(pc.get("h1", 0) or 0)
        h6  = float(pc.get("h6", 0) or 0)
        h24 = float(pc.get("h24", 0) or 0)

        signal = classify_signal(h1, h6, h24)
        if signal == "SKIP":
            continue

        price = float(best.get("priceUsd", 0) or 0)
        fdv = float(best.get("fdv", 0) or 0)
        vol = float(best.get("volume", {}).get("h24", 0) or 0)
        liq = float(best.get("liquidity", {}).get("usd", 0) or 0)

        base = best.get("baseToken", {})
        symbol = base.get("symbol", "?")
        name = base.get("name", "?")
        url = best.get("url", "")

        signals_found += 1

        # Signal header
        marker = {"STRONG DIP": "***", "BUY DIP": "**", "WATCH": "*"}.get(signal, "")
        print()
        log(f"  {marker} [{signal}] {symbol} ({name})")
        log(f"     Price: {fmt_price(price)}  |  2x Target: {fmt_price(price * 2)}")
        log(f"     1h: {h1:+.1f}%  |  6h: {h6:+.1f}%  |  24h: {h24:+.1f}%")
        log(f"     MCap: {fmt_usd(fdv)}  |  Vol: {fmt_usd(vol)}  |  Liq: {fmt_usd(liq)}")
        log(f"     {url}")
        log(f"     {address}")

        time.sleep(0.25)

    print()
    if signals_found == 0:
        log("No dip recovery signals found this cycle.")
    else:
        log(f"Found {signals_found} signal(s).")


def main():
    print()
    log("=" * 65)
    log("  MEMECOIN SWING RECOVERY SCANNER")
    log("  Source: DexScreener (free, no API key)")
    log(f"  Scan interval: {SCAN_INTERVAL}s ({SCAN_INTERVAL // 60} min)")
    log("  Signals: STRONG DIP / BUY DIP / WATCH")
    log("  Criteria:")
    log("    STRONG DIP — down 30%+ in 24h + recovering 2%+ in 1h")
    log("    BUY DIP    — down 25%+ in 6h  + recovering 2%+ in 1h")
    log("    WATCH      — down 20%+ in 6h or 25%+ in 24h, any recovery")
    log("=" * 65)
    print()

    while True:
        try:
            scan_once()
            log(f"Next scan in {SCAN_INTERVAL // 60} minutes...")
            print()
            time.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt:
            print()
            log("Scanner stopped.")
            break
        except Exception as e:
            log(f"Scan error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
