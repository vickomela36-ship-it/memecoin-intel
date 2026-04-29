"""
Memecoin Intel — hourly signal scanner.

Usage:
    python scheduler.py          # runs immediately, then every hour
    python scheduler.py --once   # single run then exit (useful for cron)
"""
import argparse
import logging
import sys
import time

import schedule

from notifier import process_buy_signal
from signals import run_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("memecoin_intel.log"),
    ],
)
logger = logging.getLogger(__name__)


def scan_and_alert() -> None:
    logger.info("Starting memecoin signal scan...")
    try:
        results = run_signals()
        buy_signals = [r for r in results if r["signal"] == "buy now"]
        if buy_signals:
            logger.info("%d BUY NOW signal(s) found — sending alerts", len(buy_signals))
            for signal in buy_signals:
                process_buy_signal(signal)
        else:
            logger.info("No buy signals this cycle")
    except Exception:
        logger.exception("Scan failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    logger.info("Memecoin Intel starting up")
    scan_and_alert()

    if args.once:
        return

    schedule.every(1).hours.do(scan_and_alert)
    logger.info("Scheduled — next run in 1 hour. Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Stopped by user")


if __name__ == "__main__":
    main()
