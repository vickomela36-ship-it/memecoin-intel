#!/usr/bin/env python3
"""Daily memecoin signal runner.

Designed to be called by cron once per day:
    0 9 * * * cd /path/to/memecoin-intel && /usr/bin/python3 run_daily.py
"""

import logging
import sys
from datetime import datetime

from signals import get_buy_signals
from notifier import send_email, log_to_notion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler("memecoin_intel.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def main() -> None:
    log.info("=== Daily scan started — %s ===", datetime.now().strftime("%Y-%m-%d %H:%M"))

    signals = get_buy_signals()
    log.info("Buy-now signals found: %d", len(signals))

    if not signals:
        log.info("Nothing to do today.")
        return

    # Send one consolidated email for all signals found today
    email_sent = False
    try:
        email_sent = send_email(signals)
    except Exception as exc:
        log.error("Email delivery failed: %s", exc)

    # Log each signal individually to Notion
    for sig in signals:
        try:
            ok = log_to_notion(sig, email_sent)
            status = "logged" if ok else "FAILED"
            log.info("Notion %s: %s (%s)", status, sig["token_name"], sig["symbol"])
        except Exception as exc:
            log.error("Notion error for %s: %s", sig["token_name"], exc)

    log.info("=== Scan complete ===")


if __name__ == "__main__":
    main()
