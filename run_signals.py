"""
Entry point — run by cron every hour.
  1. Checks all configured tokens for buy signals.
  2. For each "buy now": sends email alert + logs row to Notion.

Usage:
    python run_signals.py
"""

import logging
import sys
from datetime import datetime, timezone

from signals import run_signal_check
from notifier import send_email, log_to_notion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    now = datetime.now(timezone.utc)
    logger.info("=== Signal check started at %s ===", now.strftime("%Y-%m-%d %H:%M UTC"))

    buy_signals = run_signal_check()

    if not buy_signals:
        logger.info("No buy signals this run.")
    else:
        logger.info("%d buy signal(s) found.", len(buy_signals))

    for sig in buy_signals:
        token  = sig["token"]
        price  = sig["price"]
        score  = sig["score"]
        reason = sig["reason"]
        signal = sig["signal"]

        email_sent = send_email(token, price, score, reason)
        log_to_notion(token, price, score, reason, signal, now, email_sent)

    logger.info("=== Signal check complete ===")


if __name__ == "__main__":
    main()
