#!/usr/bin/env python3
"""
Daily runner — scans configured memecoins, fires email alerts and logs every
'buy now' signal to Notion and the local CSV.
"""

import sys
from datetime import datetime, timezone

from signals import run_all
from email_sender import send_buy_alert
from notion_logger import log_signal
from tracker import log_result
from config import NOTION_API_TOKEN


def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"  Memecoin Intel — Daily Signal Scan")
    print(f"  {ts}")
    print(f"{'='*60}\n")

    print("Fetching signals…")
    results = run_all()

    buy_signals = [r for r in results if r["signal"] == "buy now"]

    print(f"\n{'─'*60}")
    print(f"  Total coins scanned : {len(results)}")
    print(f"  Buy Now signals     : {len(buy_signals)}")
    print(f"{'─'*60}\n")

    # Always log everything to local CSV
    for r in results:
        log_result(r)

    if not buy_signals:
        print("No buy signals today — no email or Notion entry created.\n")
        return 0

    # Send a single batched email for all buy signals
    email_sent = send_buy_alert(buy_signals)

    # Log each buy signal to Notion
    if NOTION_API_TOKEN:
        print("\nLogging to Notion…")
        for r in buy_signals:
            try:
                log_signal(r, email_sent=email_sent)
            except Exception as exc:
                print(f"  [Notion] Failed for {r['name']}: {exc}")
    else:
        print("  [Notion] NOTION_API_TOKEN not set — skipping Notion logging.")

    print("\nDone.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
