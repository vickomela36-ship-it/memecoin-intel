#!/usr/bin/env python3
"""
Hourly memecoin signal runner.

Checks DexScreener for buy signals, emails vickomela36@gmail.com,
and logs every hit to the "Memecoin Buy Signals" Notion database.

Cron entry (runs every hour on the hour):
    0 * * * * cd /home/user/memecoin-intel && /usr/bin/python3 runner.py

Manual run:
    python3 runner.py
    python3 runner.py --dry-run   # fetch + evaluate but do NOT email/Notion
    python3 runner.py --demo      # send a fake signal to test email + Notion
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

from signals import get_buy_signals
from notifier import send_email, log_to_notion

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("signal_runner.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ── Main ─────────────────────────────────────────────────────────────────────
def run(dry_run: bool = False) -> None:
    start = datetime.now(timezone.utc)
    log.info("══ Signal check started at %s ══", start.strftime("%Y-%m-%d %H:%M UTC"))

    try:
        buy_signals = get_buy_signals()
    except Exception as exc:
        log.exception("Signal fetch failed: %s", exc)
        sys.exit(1)

    log.info("Found %d buy signal(s) this run.", len(buy_signals))

    if not buy_signals:
        log.info("Nothing to notify. Exiting.")
        return

    if dry_run:
        log.info("[DRY RUN] Would send email and log the following signal(s):")
        for s in buy_signals:
            log.info("  • %s | %s | +%s%% (1h) | $%s price", s["token"], s["chain"], s["change_1h"], s["price_usd"])
        return

    # Log every signal to Notion first (so data is captured even if email fails)
    for sig in buy_signals:
        log_to_notion(sig)

    # Send a single batched email for all signals in this cycle
    send_email(buy_signals)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    log.info("══ Done in %.1fs ══", elapsed)


_DEMO_SIGNAL = {
    "token":         "DEMOTOKEN",
    "token_address": "DeMo1111111111111111111111111111111111111111",
    "chain":         "solana",
    "dex":           "raydium",
    "dex_url":       "https://dexscreener.com",
    "price_usd":     "0.00042",
    "volume_24h":    "250000",
    "liquidity":     "80000",
    "change_1h":     "12.5",
    "change_6h":     "28.3",
    "change_24h":    "55.1",
    "signal":        "buy now",
    "reason":        "Vol $250,000 | Liq $80,000 | +12.5% (1h) [DEMO]",
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Memecoin hourly signal runner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and evaluate signals but do not send email or write to Notion",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Send a fake signal to validate email and Notion credentials",
    )
    args = parser.parse_args()

    if args.demo:
        log.info("Running in DEMO mode — sending fake signal to test credentials")
        log_to_notion(_DEMO_SIGNAL)
        send_email([_DEMO_SIGNAL])
    else:
        run(dry_run=args.dry_run)
