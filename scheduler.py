#!/usr/bin/env python3
"""Memecoin Intel hourly scheduler.

Runs signal detection immediately on startup, then every hour.
For each 'buy now' signal: sends an email alert and logs to Notion.

Usage:
    python scheduler.py

Required env vars (see .env.example):
    NOTION_TOKEN, GMAIL_SENDER, GMAIL_APP_PASSWORD
"""
import logging
import time

import schedule

from notifier import process_signal
from signals import run_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def check_and_alert() -> None:
    log.info("Running hourly signal check...")
    signals = run_signals()
    buy_signals = [s for s in signals if s.signal_type == "buy now"]
    log.info(f"Signal check complete: {len(buy_signals)} buy-now signal(s) found")

    for sig in buy_signals:
        log.info(f"Processing: {sig.token_name} | {sig.signal_strength} | +{sig.price_change_24h:.1f}%")
        process_signal(sig)


if __name__ == "__main__":
    log.info("Memecoin Intel Scheduler started. Checks every 1 hour.")

    check_and_alert()                         # run immediately on startup
    schedule.every(1).hour.do(check_and_alert)

    while True:
        schedule.run_pending()
        time.sleep(30)
