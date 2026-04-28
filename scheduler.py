"""
Entry point — runs signal checks every hour.

Usage:
    python scheduler.py

On start it runs one immediate check, then repeats every 60 minutes.
Set TOKEN_ADDRESSES in .env before running.
"""
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

import config as cfg
import notifier
import notion_logger
from signals import check_tokens

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def run_check() -> None:
    if not cfg.TOKEN_ADDRESSES:
        log.warning("TOKEN_ADDRESSES is empty — add token addresses to .env")
        return

    log.info("Checking %d token(s)...", len(cfg.TOKEN_ADDRESSES))
    results = check_tokens(cfg.TOKEN_ADDRESSES)

    for s in results:
        log.info("  %-10s  %-8s  1h: %s%%", s.symbol, s.signal, s.change_1h)

        if s.signal == "buy now":
            log.info("  >>> BUY NOW — %s @ $%s", s.symbol, s.price_usd)
            try:
                notifier.send_buy_signal_email(s, cfg)
            except Exception as exc:
                log.error("Email failed for %s: %s", s.symbol, exc)
            try:
                notion_logger.log_signal(s, cfg)
            except Exception as exc:
                log.error("Notion log failed for %s: %s", s.symbol, exc)


if __name__ == "__main__":
    log.info("memecoin-intel scheduler starting (interval: 1 hour)")
    run_check()  # immediate first run

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_check, "interval", hours=1, id="signal_check")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped")
