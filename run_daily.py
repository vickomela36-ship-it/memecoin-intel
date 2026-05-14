#!/usr/bin/env python3
"""Daily runner: check signals, email + log any 'buy now' hits."""

import logging
import sys
from datetime import datetime

from notifier import log_to_notion, send_email
from signals import get_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("memecoin_intel.log"),
        logging.StreamHandler(sys.stdout),
    ],
)


def main() -> None:
    logging.info("=== Memecoin Intel run started at %s ===", datetime.utcnow().isoformat())

    all_signals = get_signals()
    logging.info("Evaluated %d pair(s)", len(all_signals))

    buy_signals = [s for s in all_signals if s["signal"] == "buy now"]
    logging.info("Found %d 'buy now' signal(s)", len(buy_signals))

    for sig in buy_signals:
        logging.info("Buy Now → %s  pair=%s", sig["coin_symbol"], sig["pair_address"])
        email_ok = send_email(sig)
        notion_ok = log_to_notion(sig, email_sent=email_ok)
        logging.info(
            "  email=%s  notion=%s",
            "sent" if email_ok else "FAILED",
            "logged" if notion_ok else "FAILED",
        )

    logging.info("=== Run complete ===\n")


if __name__ == "__main__":
    main()
