"""
Hourly signal scheduler for memecoin-intel.

Run once:   python scheduler.py
Keep alive: the script loops forever, checking signals every CHECK_INTERVAL_SECONDS.

Required env vars (set in .env or shell):
  GMAIL_USER        — sender Gmail address
  GMAIL_APP_PASS    — Gmail App Password
  NOTION_TOKEN      — Notion internal integration token
  TRACKED_PAIRS     — comma-separated DexScreener Solana pair addresses
  NOTION_DB_ID      — (optional) Notion DB ID; defaults to the one created at setup
  CHECK_INTERVAL_SECONDS — (optional) override interval, default 3600
"""

import time
import signal as os_signal
import sys
from datetime import datetime, timezone

from config import CHECK_INTERVAL_SECONDS
from signals import run_signals
from notifier import handle_buy_signal


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def check_and_notify() -> None:
    print(f"\n[scheduler] Running signal check at {_now()}")
    results = run_signals()

    buy_count = 0
    for item in results:
        sig = item.get("signal", "hold")
        symbol = item.get("symbol", "?")
        print(f"  {symbol}: {sig}")
        if sig == "buy now":
            buy_count += 1
            handle_buy_signal(item)

    print(f"[scheduler] Done. {buy_count} buy-now signal(s) found.")


def _graceful_exit(signum, frame):
    print("\n[scheduler] Shutting down.")
    sys.exit(0)


def main():
    os_signal.signal(os_signal.SIGINT, _graceful_exit)
    os_signal.signal(os_signal.SIGTERM, _graceful_exit)

    print(f"[scheduler] Starting. Interval: {CHECK_INTERVAL_SECONDS}s "
          f"({CHECK_INTERVAL_SECONDS // 60} min)")
    print("[scheduler] Press Ctrl+C to stop.\n")

    while True:
        check_and_notify()
        print(f"[scheduler] Next check in {CHECK_INTERVAL_SECONDS // 60} minute(s)…")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
