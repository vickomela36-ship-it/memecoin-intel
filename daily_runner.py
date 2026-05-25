#!/usr/bin/env python3
"""Entry point for the daily memecoin signal check."""
import sys

from signals import get_signals
from notifier import send_email, log_to_notion


def main() -> int:
    print("=" * 50)
    print("Memecoin Intel — daily signal check")
    print("=" * 50)

    try:
        signals = get_signals()
    except Exception as exc:
        print(f"Failed to fetch signals: {exc}")
        return 1

    buy_signals = [s for s in signals if s["signal"] == "buy now"]
    hold = sum(1 for s in signals if s["signal"] == "hold")
    sell = sum(1 for s in signals if s["signal"] == "sell")

    print(f"Scanned {len(signals)} coins | buy now: {len(buy_signals)} | hold: {hold} | sell: {sell}")

    if not buy_signals:
        print("No buy now signals today — no email or Notion entry created.")
        return 0

    print(f"\nBUY NOW signals:")
    for s in buy_signals:
        print(f"  {s['token']}: ${s['price']:.6f} ({s['change_24h']:+.2f}%) vol=${s['volume_24h']:,.0f}")

    print("\nSending email...")
    try:
        send_email(buy_signals)
    except Exception as exc:
        print(f"Email error: {exc}")

    print("Logging to Notion...")
    for signal in buy_signals:
        try:
            log_to_notion(signal)
        except Exception as exc:
            print(f"Notion error for {signal['token']}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
