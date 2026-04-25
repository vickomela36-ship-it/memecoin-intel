#!/usr/bin/env python3
"""
Hourly memecoin signal checker.
Run by cron every hour. Fetches live signals, notifies on 'buy now'.

Usage:
    python run_check.py           # single run (for cron)
    python run_check.py --loop    # stay alive and run every 3600 s
"""

import argparse
import logging
import time
from datetime import datetime, timezone

from config import WATCH_TOKENS, BUY_SCORE_THRESHOLD
from signals import run as fetch_signals
from notifier import notify_buy_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

CHECK_INTERVAL = 3600  # seconds


def check_once() -> None:
    log.info("─── Signal check started (%s UTC) ───",
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))

    all_signals = fetch_signals(WATCH_TOKENS or None, BUY_SCORE_THRESHOLD)

    buy_signals = [s for s in all_signals if s.signal == "buy now"]
    other       = [s for s in all_signals if s.signal != "buy now"]

    log.info("Scanned %d token(s) — %d buy now, %d hold/sell",
             len(all_signals), len(buy_signals), len(other))

    for s in all_signals:
        label = f"[{s.signal.upper():8}]"
        log.info("%s  %-12s  $%.8f  score=%.0f  %s", label, s.token, s.price, s.score, s.reason)

    if buy_signals:
        log.info("Sending notifications for %d buy signal(s)…", len(buy_signals))
        notify_buy_signals(buy_signals)
    else:
        log.info("No buy signals this run — no notifications sent.")

    log.info("─── Check complete ───\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memecoin signal checker")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously every hour instead of once")
    args = parser.parse_args()

    if args.loop:
        log.info("Loop mode: checking every %d seconds", CHECK_INTERVAL)
        while True:
            try:
                check_once()
            except Exception as exc:
                log.error("Unexpected error during check: %s", exc)
            time.sleep(CHECK_INTERVAL)
    else:
        check_once()


if __name__ == "__main__":
    main()
