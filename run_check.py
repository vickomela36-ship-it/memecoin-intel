#!/usr/bin/env python3
"""
Daily memecoin signal checker.

Usage:
    python run_check.py            # single run (called by GitHub Actions / cron)
    python run_check.py --loop     # stay alive and run every 24 h
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

DAILY_INTERVAL = 86_400  # 24 hours in seconds


def check_once() -> None:
    log.info("=== Signal check started  %s UTC ===",
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))

    all_signals  = fetch_signals(WATCH_TOKENS or None, BUY_SCORE_THRESHOLD)
    buy_signals  = [s for s in all_signals if s.signal == "buy now"]
    other        = [s for s in all_signals if s.signal != "buy now"]

    log.info("Scanned %d token(s): %d buy-now  |  %d hold/sell",
             len(all_signals), len(buy_signals), len(other))

    for s in all_signals:
        log.info("[%-8s]  %-14s  $%.8f  score=%.0f  %s",
                 s.signal.upper(), s.token, s.price, s.score, s.reason)

    if buy_signals:
        log.info("Sending notifications for %d buy signal(s)…", len(buy_signals))
        notify_buy_signals(buy_signals)
    else:
        log.info("No buy signals this run — nothing to notify.")

    log.info("=== Check complete ===\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memecoin daily signal checker")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously, once every 24 hours")
    args = parser.parse_args()

    if args.loop:
        log.info("Loop mode: checking every %d seconds (24 h)", DAILY_INTERVAL)
        while True:
            try:
                check_once()
            except Exception as exc:
                log.error("Unexpected error: %s", exc)
            time.sleep(DAILY_INTERVAL)
    else:
        check_once()


if __name__ == "__main__":
    main()
