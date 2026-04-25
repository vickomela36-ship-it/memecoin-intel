"""
Main scanner entry point.

Run:
    python scanner.py              # pretty terminal output
    python scanner.py --json       # machine-readable JSON (used by alerter)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

import signals as sig_module


def _fmt_usd(n: float) -> str:
    if n >= 1_000_000:
        return f"${n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"${n/1_000:.1f}K"
    return f"${n:.4f}" if n < 1 else f"${n:.2f}"


def _print_signal(s: sig_module.Signal) -> None:
    tag = "*** BUY NOW ***" if s.is_buy_now() else "   WATCH      "
    print(f"\n  {tag}  {s.token_symbol} ({s.token_name})")
    print(f"    Price:      {_fmt_usd(s.price_usd)}")
    print(f"    1h / 6h:    {s.h1_change:+.1f}% / {s.h6_change:+.1f}%")
    print(f"    Confidence: {s.confidence:.0%}")
    print(f"    FDV:        {_fmt_usd(s.fdv)}   Vol 24h: {_fmt_usd(s.volume_h24)}")
    print(f"    Reason:     {s.reason}")
    print(f"    DEX:        {s.dex_id}   Pair: {s.pair_address}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memecoin swing-recovery scanner")
    parser.add_argument("--json", action="store_true", help="Output JSON for alerter")
    args = parser.parse_args()

    scanned_at = datetime.now(timezone.utc).isoformat()

    if not args.json:
        print(f"\n[memecoin-intel] Scanning Solana memecoins… ({scanned_at})")

    results = sig_module.scan_all()
    buy_now = [s for s in results if s.is_buy_now()]
    watch   = [s for s in results if s.signal_type == "WATCH"]

    if args.json:
        output = {
            "scanned_at": scanned_at,
            "signals": [
                {
                    "token_name":   s.token_name,
                    "token_symbol": s.token_symbol,
                    "mint_address": s.mint_address,
                    "pair_address": s.pair_address,
                    "dex_id":       s.dex_id,
                    "signal_type":  s.signal_type,
                    "price_usd":    s.price_usd,
                    "confidence":   s.confidence,
                    "reason":       s.reason,
                    "h1_change":    s.h1_change,
                    "h6_change":    s.h6_change,
                    "h24_change":   s.h24_change,
                    "fdv":          s.fdv,
                    "volume_h24":   s.volume_h24,
                    "liquidity":    s.liquidity,
                    "buy_ratio_h1": s.buy_ratio_h1,
                }
                for s in results
                if s.signal_type in ("BUY_NOW", "WATCH")
            ],
        }
        print(json.dumps(output))
        return

    if not buy_now and not watch:
        print("  No signals this scan.\n")
        return

    if buy_now:
        print(f"\n  ── BUY NOW ({len(buy_now)}) ──────────────────────────────────────")
        for s in buy_now:
            _print_signal(s)

    if watch:
        print(f"\n  ── WATCH ({len(watch)}) ──────────────────────────────────────────")
        for s in watch:
            _print_signal(s)

    print()


if __name__ == "__main__":
    main()
