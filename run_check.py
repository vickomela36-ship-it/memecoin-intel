#!/usr/bin/env python3
"""
Hourly memecoin signal checker — called by cron every hour.
Fetches live signals, sends email + logs to Notion for any 'buy now' hits.

Usage:
    python run_check.py
"""

import logging
from datetime import datetime, timezone

from config import WATCH_TOKENS, BUY_SCORE_THRESHOLD
from signals import run as fetch_signals
from notifier import notify_buy_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def main():
    log.info("─── Signal check %s UTC ───", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    all_signals = fetch_signals(WATCH_TOKENS or None, BUY_SCORE_THRESHOLD)
    buy = [s for s in all_signals if s.signal == "buy now"]
    log.info("Scanned %d token(s) — %d buy now", len(all_signals), len(buy))
    for s in all_signals:
        log.info("[%s]  %-12s  $%.8f  score=%.0f  %s",
                 s.signal.upper(), s.token, s.price, s.score, s.reason)
    if buy:
        notify_buy_signals(buy)
    else:
        log.info("No buy signals — nothing sent.")
    log.info("─── Done ───")


if __name__ == "__main__":
    main()
