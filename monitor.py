#!/usr/bin/env python3
"""
Memecoin signal monitor — run hourly via cron.

  crontab -e
  0 * * * * cd /path/to/memecoin-intel && python monitor.py >> logs/monitor.log 2>&1

On a 'buy now' signal:
  1. Sends an HTML email alert to vickomela36@gmail.com
  2. Appends a row to the Notion "Memecoin Buy Signals" database

A per-token cooldown (default 4 h) prevents duplicate alerts.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import WATCHED_TOKENS, GMAIL_USER, GMAIL_APP_PASSWORD, NOTION_TOKEN
from signals import get_signals
from notify import send_buy_alert, log_to_notion

COOLDOWN_FILE  = Path(__file__).parent / ".signal_cooldowns.json"
COOLDOWN_HOURS = 4


# ---------------------------------------------------------------------------
# Cooldown helpers
# ---------------------------------------------------------------------------

def _load_cooldowns() -> dict:
    if COOLDOWN_FILE.exists():
        try:
            return json.loads(COOLDOWN_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_cooldowns(cooldowns: dict) -> None:
    COOLDOWN_FILE.write_text(json.dumps(cooldowns, indent=2))


def _on_cooldown(address: str, cooldowns: dict) -> bool:
    last_str = cooldowns.get(address)
    if not last_str:
        return False
    last = datetime.fromisoformat(last_str)
    return datetime.now(timezone.utc).replace(tzinfo=None) - last < timedelta(hours=COOLDOWN_HOURS)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    tokens = WATCHED_TOKENS
    if not tokens:
        print("[monitor] WATCHED_TOKENS is empty — add token addresses to .env")
        sys.exit(0)

    missing = []
    if not (GMAIL_USER and GMAIL_APP_PASSWORD):
        missing.append("GMAIL_USER / GMAIL_APP_PASSWORD")
    if not NOTION_TOKEN:
        missing.append("NOTION_TOKEN")
    if missing:
        print(f"[monitor] Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[monitor] Run started — {now_str} — watching {len(tokens)} token(s)")

    signals   = get_signals(tokens)
    cooldowns = _load_cooldowns()

    for sig in signals:
        sym    = sig["symbol"]
        label  = sig["signal"]
        addr   = sig["address"]
        marker = "***" if label == "buy now" else "   "
        print(
            f"  {marker} {sym:<10} {label:<8}  "
            f"1h={sig['h1_change']:+.2f}%  "
            f"vol=${sig['volume_24h']:>12,.0f}  "
            f"bp={sig['buy_pressure']}%"
        )

        if label != "buy now":
            continue

        if _on_cooldown(addr, cooldowns):
            print(f"         → skipped (cooldown active, re-alerts every {COOLDOWN_HOURS}h)")
            continue

        try:
            send_buy_alert(sig)
        except Exception as exc:
            print(f"         [error] email failed: {exc}")

        try:
            log_to_notion(sig)
        except Exception as exc:
            print(f"         [error] notion log failed: {exc}")

        cooldowns[addr] = datetime.utcnow().isoformat()

    _save_cooldowns(cooldowns)
    print("[monitor] Done.\n")


if __name__ == "__main__":
    run()
