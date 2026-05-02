#!/usr/bin/env python3
"""
Hourly memecoin signal scheduler.

Usage:
    python scheduler.py

Runs check_signals.run_check() immediately on startup, then every hour.
Set CHECK_INTERVAL_HOURS in config.py to change the cadence.
"""
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from check_signals import run_check
from config import CHECK_INTERVAL_HOURS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

if __name__ == "__main__":
    log.info("Starting memecoin-intel scheduler (interval: %dh).", CHECK_INTERVAL_HOURS)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_check,
        trigger="interval",
        hours=CHECK_INTERVAL_HOURS,
        id="signal_check",
        max_instances=1,
        coalesce=True,
    )

    # Fire immediately so the first check doesn't wait an hour
    run_check()
    scheduler.start()
