#!/usr/bin/env python3
"""Hourly runner: check signals, email + log to Notion on 'buy now'."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict

import config
from notifier import log_to_notion, send_email
from signals import Signal, get_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert-cooldown state  (persisted to a small JSON file)
# ---------------------------------------------------------------------------

def _load_state() -> Dict[str, str]:
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE) as fh:
                return json.load(fh)
        except Exception:
            pass
    return {}


def _save_state(state: Dict[str, str]) -> None:
    try:
        with open(config.STATE_FILE, "w") as fh:
            json.dump(state, fh)
    except Exception as exc:
        log.warning("Could not save state: %s", exc)


def _is_on_cooldown(coin: str, state: Dict[str, str]) -> bool:
    last_str = state.get(coin)
    if not last_str:
        return False
    last = datetime.fromisoformat(last_str)
    return datetime.now(timezone.utc) - last < timedelta(hours=config.ALERT_COOLDOWN_HOURS)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    log.info("=== memecoin-intel hourly scan ===")
    all_signals = get_signals()

    if not all_signals:
        log.warning("No signals returned (API error or empty token list).")
        return

    state = _load_state()
    buy_signals_to_alert: list[Signal] = []

    for sig in all_signals:
        if sig.signal != "buy now":
            continue

        # Always log every buy-now to Notion
        log_to_notion(sig)

        # Email only if outside the cooldown window
        if _is_on_cooldown(sig.coin, state):
            log.info("Skipping email for %s (cooldown active)", sig.coin)
        else:
            buy_signals_to_alert.append(sig)
            state[sig.coin] = datetime.now(timezone.utc).isoformat()

    if buy_signals_to_alert:
        send_email(buy_signals_to_alert)
    else:
        log.info("No new buy-now alerts to email this cycle.")

    _save_state(state)
    log.info("=== scan complete ===")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        log.exception("Fatal error: %s", exc)
        sys.exit(1)
