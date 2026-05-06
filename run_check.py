#!/usr/bin/env python3
from __future__ import annotations
import sys
import time
import logging

from config import WATCH_TOKENS, BUY_SCORE_THRESHOLD
from signals import fetch_signals
from notifier import notify_buy_signals

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

CHECK_INTERVAL = 3600  # 1 hour


def check_once() -> None:
    log.info("=== memecoin-intel check start ===")
    all_signals = fetch_signals(WATCH_TOKENS, BUY_SCORE_THRESHOLD)

    buy_signals = [s for s in all_signals if s.signal == "buy now"]
    other       = [s for s in all_signals if s.signal != "buy now"]

    log.info(f"Scanned {len(all_signals)} token(s) — {len(buy_signals)} buy now, {len(other)} hold/sell")

    for s in all_signals:
        log.info(f"  [{s.signal.upper():8}] {s.token:<10} ${s.price:.6g:<14} score={s.score:.0f}  {s.reason}")

    if buy_signals:
        log.info(f"Sending notifications for {len(buy_signals)} buy signal(s)…")
        notify_buy_signals(buy_signals)
    else:
        log.info("No buy signals this run.")

    log.info("=== check complete ===")


def main() -> None:
    if "--loop" in sys.argv:
        log.info(f"Loop mode — checking every {CHECK_INTERVAL}s")
        while True:
            try:
                check_once()
            except Exception as e:
                log.error(f"check_once error: {e}")
            time.sleep(CHECK_INTERVAL)
    else:
        check_once()


if __name__ == "__main__":
    main()
