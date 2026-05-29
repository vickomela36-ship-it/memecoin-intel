#!/usr/bin/env python3
"""
Daily memecoin signal runner.

Usage:
    python run_daily.py

Reads WATCHLIST from config.py (or scans trending tokens if the list is empty),
evaluates each token, and for every 'buy now' signal:
  1. Sends an alert email to ALERT_EMAIL_TO
  2. Logs the signal to the Notion database

Environment variables required:
    NOTION_TOKEN         – Notion integration secret
    GMAIL_USER           – Gmail address to send alerts from
    GMAIL_APP_PASSWORD   – Gmail App Password (not your account password)
"""

import logging
import sys

from notifier import notify_buy_signal
from signals import run_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== Memecoin Intel — Daily Signal Scan ===")

    all_signals = run_scan()

    buy_signals = [s for s in all_signals if s.signal == "buy now"]
    logger.info("Found %d buy-now signal(s)", len(buy_signals))

    for sig in buy_signals:
        logger.info("Processing buy signal: %s", sig.symbol)
        notify_buy_signal(sig)

    if not buy_signals:
        logger.info("No buy signals today — no emails sent")

    logger.info("=== Done ===")


if __name__ == "__main__":
    main()
