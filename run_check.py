#!/usr/bin/env python3
"""
Hourly memecoin signal checker.

Manual run:
    python run_check.py

Via cron (once per hour):
    0 * * * * /path/to/venv/bin/python /path/to/memecoin-intel/run_check.py >> /var/log/memecoin.log 2>&1

Deduplication: pair addresses seen in the last CHECK_INTERVAL_HOURS are skipped
so a single token only fires one alert per hour.
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import ALERT_EMAIL, CHECK_INTERVAL_HOURS
from signals import get_buy_signals
from notifier import send_buy_alert, log_to_notion

_SEEN_FILE = Path(__file__).parent / ".seen_signals.json"


def _load_seen():
    """Return {pair_address: iso_timestamp} for signals seen within the window."""
    if not _SEEN_FILE.exists():
        return {}
    try:
        data = json.loads(_SEEN_FILE.read_text())
        cutoff = datetime.now(timezone.utc) - timedelta(hours=CHECK_INTERVAL_HOURS)
        return {
            addr: ts
            for addr, ts in data.items()
            if datetime.fromisoformat(ts) > cutoff
        }
    except Exception:
        return {}


def _save_seen(seen):
    _SEEN_FILE.write_text(json.dumps(seen, indent=2))


def run():
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n[{now_str}] Checking signals…")

    try:
        signals = get_buy_signals()
    except Exception as exc:
        print(f"  ERROR fetching signals: {exc}", file=sys.stderr)
        return

    print(f"  {len(signals)} buy signal(s) found")

    if not signals:
        return

    seen      = _load_seen()
    new_sigs  = [s for s in signals if s["pair_address"] not in seen]

    if not new_sigs:
        print("  All signals already notified this window — nothing to do")
        return

    # Send one batched email
    email_sent = False
    try:
        send_buy_alert(new_sigs)
        email_sent = True
        print(f"  Email sent → {ALERT_EMAIL} ({len(new_sigs)} signal(s))")
    except Exception as exc:
        print(f"  ERROR sending email: {exc}", file=sys.stderr)

    # Log each signal to Notion
    now_iso = datetime.now(timezone.utc).isoformat()
    for sig in new_sigs:
        try:
            page_id = log_to_notion(sig, email_sent=email_sent)
            print(f"  Notion row created: {sig['symbol']} ({page_id[:8]}…)")
        except Exception as exc:
            print(f"  ERROR logging {sig['symbol']} to Notion: {exc}", file=sys.stderr)
        seen[sig["pair_address"]] = now_iso

    _save_seen(seen)


if __name__ == "__main__":
    run()
