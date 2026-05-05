"""
Main entry point for the hourly signal check.

Invoked by the cron job (or scheduler.py).
Workflow:
  1. Fetch signals from DexScreener
  2. For each 'buy now' signal:
     a. Send email alert
     b. Log to Notion
"""

import logging
import sys
from datetime import datetime, timezone

from config import WATCH_TOKENS
from notifier import log_signal_to_notion, send_email
from signals import get_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("signal_check.log"),
    ],
)
logger = logging.getLogger(__name__)


def run() -> None:
    logger.info("=== Signal check started at %s ===", datetime.now(timezone.utc).isoformat())

    all_signals = get_signals(watch_tokens=WATCH_TOKENS or None)
    buy_signals = [s for s in all_signals if s.signal == "buy now"]

    logger.info("Found %d signal(s) total, %d 'buy now'", len(all_signals), len(buy_signals))

    if not buy_signals:
        logger.info("No buy now signals this run. Nothing to notify.")
        return

    # Send one consolidated email for all buy-now signals
    email_ok = send_email(buy_signals)

    # Log each signal individually to Notion
    for sig in buy_signals:
        log_signal_to_notion(sig, email_sent=email_ok)

    logger.info("=== Run complete. %d buy-now signal(s) processed. ===", len(buy_signals))


if __name__ == "__main__":
    run()
