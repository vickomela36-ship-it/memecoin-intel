"""
Hourly memecoin signal monitor.

Run with:  python scheduler.py
Stop with: Ctrl-C

The scheduler fires once immediately on start, then every hour.
Any 'buy now' signal is:
  1. Logged as a row in the Notion database
  2. Sent as an HTML email to ALERT_EMAIL
"""
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from notifier import log_signal_to_notion, send_buy_alert_email
from signals import get_buy_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("memecoin_intel.log"),
    ],
)
logger = logging.getLogger(__name__)


def run_check():
    logger.info("--- Signal check started ---")
    try:
        signals = get_buy_signals()
    except Exception as exc:
        logger.error("Failed to fetch signals: %s", exc)
        return

    if not signals:
        logger.info("No buy signals this cycle.")
        return

    logger.info("%d buy signal(s) found — notifying.", len(signals))

    for signal in signals:
        log_signal_to_notion(signal)

    send_buy_alert_email(signals)
    logger.info("--- Signal check complete ---")


def main():
    logger.info("memecoin-intel scheduler starting (interval: 1 hour).")

    # Run once immediately so you don't wait a full hour on first launch.
    run_check()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_check,
        trigger=IntervalTrigger(hours=1),
        id="hourly_signal_check",
        name="Hourly memecoin buy-signal check",
        misfire_grace_time=300,
        coalesce=True,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
