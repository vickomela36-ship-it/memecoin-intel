"""
Hourly scheduler — checks signals and fires notifications on 'buy now'.

Run once:    python scheduler.py --once
Run forever: python scheduler.py          (checks every CHECK_INTERVAL_HOURS)
"""

from __future__ import annotations

import argparse
import logging
import time

import schedule

from signals  import get_signals
from notifier import send_email, log_to_notion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scheduler.log"),
    ],
)
log = logging.getLogger(__name__)


def check_and_notify() -> None:
    log.info("─── Signal check started ───────────────────────────────")
    try:
        signals = get_signals()
    except Exception as exc:
        log.error(f"Signal fetch failed: {exc}")
        return

    if not signals:
        log.warning("No tokens returned — add entries to TOKENS_TO_WATCH in config.py")
        return

    for sig in signals:
        label = sig["signal"].upper()
        log.info(f"  {sig['symbol']:12s}  {label:8s}  1h={sig['1h_change']}  "
                 f"vol={sig['volume_24h']}  liq={sig['liquidity_usd']}  "
                 f"pressure={sig['buy_pressure']}")

        if sig["signal"] == "buy now":
            log.info(f"  ★ BUY NOW — triggering email + Notion for {sig['symbol']}")
            send_email(sig)
            log_to_notion(sig)

    log.info("─── Signal check complete ──────────────────────────────")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memecoin Intel Scheduler")
    parser.add_argument("--once", action="store_true",
                        help="Run a single check and exit (useful for cron)")
    args = parser.parse_args()

    if args.once:
        check_and_notify()
        return

    from config import CHECK_INTERVAL_HOURS
    log.info(f"Scheduler started — running every {CHECK_INTERVAL_HOURS}h")

    # Fire immediately, then on schedule
    check_and_notify()
    schedule.every(CHECK_INTERVAL_HOURS).hours.do(check_and_notify)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
