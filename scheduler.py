"""
Entry point for the memecoin-intel signal monitor.

Usage:
    python scheduler.py           # start hourly scheduler (runs first check immediately)
    python scheduler.py --once    # run a single check and exit (useful for testing / cron)
"""

import logging
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import CHECK_INTERVAL_HOURS
from notifier import notify
from signals import get_buy_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("memecoin_intel.log"),
    ],
)
logger = logging.getLogger(__name__)


def check_and_notify() -> None:
    """Fetch buy signals and dispatch email + Notion logging for 'buy now' ones."""
    logger.info("── Signal check started ──────────────────────────────────────")
    signals = get_buy_signals()

    buy_now = [s for s in signals if s.signal_type == "buy now"]

    if buy_now:
        coins = ", ".join(f"{s.coin} [{s.strength}]" for s in buy_now)
        logger.info(f"{len(buy_now)} 'buy now' signal(s): {coins}")
        notify(buy_now)
    else:
        logger.info("No 'buy now' signals this cycle — nothing to send")

    logger.info("── Signal check complete ─────────────────────────────────────")


def main() -> None:
    if "--once" in sys.argv:
        logger.info("Running single check (--once mode)")
        check_and_notify()
        return

    logger.info(
        f"Starting scheduler — signal check every {CHECK_INTERVAL_HOURS}h "
        f"(first run immediately)"
    )
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        check_and_notify,
        trigger=IntervalTrigger(hours=CHECK_INTERVAL_HOURS),
        # Run immediately on startup, then every CHECK_INTERVAL_HOURS
        next_run_time=datetime.now(timezone.utc),
        id="signal_check",
        name="Memecoin buy-signal check",
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")


if __name__ == "__main__":
    main()
