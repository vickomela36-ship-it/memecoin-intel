#!/usr/bin/env python3
"""Daily memecoin signal runner.

Run directly:
    python runner.py

Or via cron (see setup_cron.sh).
"""

import logging
import sys
from datetime import datetime

from signals import run_scan, SIGNAL_BUY_NOW
from notify import send_email, log_to_notion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("runner.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=" * 60)
    logger.info(f"Daily scan started at {datetime.now().isoformat()}")

    all_signals = run_scan()
    buy_now = [t for t in all_signals if t.signal == SIGNAL_BUY_NOW]

    logger.info(f"Scan results: {len(buy_now)} BUY NOW out of {len(all_signals)} scanned")

    if not buy_now:
        logger.info("No buy now signals today — no email sent")
        return

    email_sent = send_email(buy_now)

    for token in buy_now:
        log_to_notion(token, email_sent=email_sent)

    logger.info(f"Done. {len(buy_now)} signal(s) processed.")


if __name__ == "__main__":
    main()
