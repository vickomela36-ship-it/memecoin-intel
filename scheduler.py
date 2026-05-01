#!/usr/bin/env python3
"""
Memecoin Intel — hourly signal checker.

Runs signal detection every hour. When a 'buy now' signal is found:
  1. Sends an email alert to the configured address.
  2. Logs the signal in the Notion "Memecoin Buy Signals Log" database.

Usage:
    python scheduler.py               # runs forever, checks every hour
    python scheduler.py --once        # single check then exit (good for cron)
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

import schedule

from signals import get_signals
from notifier import send_email, log_to_notion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("memecoin_intel.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def check_and_notify() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logger.info("Signal check started at %s", now)

    try:
        all_signals = get_signals()
    except Exception as e:
        logger.error("Signal fetch failed: %s", e)
        return

    buy_signals = [s for s in all_signals if s.signal_type == "buy now"]
    logger.info(
        "Checked %d tokens — %d buy signal(s) found", len(all_signals), len(buy_signals)
    )

    for signal in buy_signals:
        logger.info(
            "BUY NOW: %s @ $%.8f | confidence %.0f%% | %s",
            signal.coin,
            signal.price,
            signal.confidence * 100,
            signal.notes,
        )
        email_sent = send_email(signal)
        log_to_notion(signal, email_sent)


def main() -> None:
    parser = argparse.ArgumentParser(description="Memecoin Intel signal scheduler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single check and exit (suitable for cron)",
    )
    args = parser.parse_args()

    if args.once:
        check_and_notify()
        return

    logger.info("Scheduler started — checking every hour")
    check_and_notify()  # immediate first run

    schedule.every().hour.do(check_and_notify)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
