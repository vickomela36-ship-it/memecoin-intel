#!/usr/bin/env python3
"""
Memecoin signal runner – checks signals and fires alerts for 'buy now' hits.

Usage
-----
Run once (ideal for cron):
    python runner.py

Run as a continuous hourly loop:
    python runner.py --loop

Cron example (every hour):
    0 * * * * cd /path/to/memecoin-intel && python runner.py >> /var/log/memecoin.log 2>&1
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from signals import get_signals
from notifier import notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 3600  # 1 hour


def run_once() -> None:
    logger.info("─" * 50)
    logger.info("Checking signals at %s UTC", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    try:
        signals = get_signals()
    except Exception as exc:
        logger.error("Signal fetch failed: %s", exc)
        return

    buy_signals = [s for s in signals if s.action == "buy now"]
    logger.info(
        "Scanned %d coins → %d buy signal(s), %d hold, %d sell",
        len(signals),
        len(buy_signals),
        sum(1 for s in signals if s.action == "hold"),
        sum(1 for s in signals if s.action == "sell"),
    )

    for signal in buy_signals:
        logger.info(
            "BUY NOW ▶ %s @ $%s  confidence=%.0f%%  %s",
            signal.coin,
            signal.price,
            signal.confidence * 100,
            signal.notes,
        )
        notify(signal)

    if not buy_signals:
        logger.info("No buy signals this run.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memecoin hourly signal runner")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously every hour (default: run once and exit)",
    )
    args = parser.parse_args()

    if args.loop:
        logger.info("Starting hourly loop. Press Ctrl+C to stop.")
        try:
            while True:
                run_once()
                logger.info("Sleeping %d minutes until next check…", INTERVAL_SECONDS // 60)
                time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
    else:
        run_once()


if __name__ == "__main__":
    main()
