"""
Hourly scheduler — keeps running and calls run_check.run() every hour.

Usage:
    python scheduler.py

Alternatively, install as a cron job via setup_cron.sh for a lighter footprint.
"""

import logging
import time

import schedule

from run_check import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def job() -> None:
    try:
        run()
    except Exception as exc:
        logger.error("Unhandled error in signal check: %s", exc, exc_info=True)


if __name__ == "__main__":
    logger.info("Memecoin Intel scheduler started — running every hour.")
    job()                              # run immediately on startup
    schedule.every().hour.do(job)

    while True:
        schedule.run_pending()
        time.sleep(30)
