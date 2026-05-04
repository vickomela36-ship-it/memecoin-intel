"""
Hourly signal monitor.

For each 'buy now' signal detected by signals.py:
  1. Sends an alert email to ALERT_EMAIL via Gmail SMTP.
  2. Logs a row in the Notion 'Memecoin Buy Now Signals' database.

Environment variables required:
  GMAIL_SENDER        – Gmail address used to send (e.g. alerts@gmail.com)
  GMAIL_APP_PASSWORD  – Gmail App Password (Settings → Security → App passwords)
  NOTION_TOKEN        – Notion internal-integration token (secret_...)
  NOTION_DATA_SOURCE  – Notion data-source ID for the signal log database
                        (default: c57d31d6-ddd4-49bb-ba4a-ee5b97b580e3)

Usage:
  python monitor.py            # one-shot check
  python monitor.py --loop     # block forever, checking every INTERVAL_SECONDS
  python monitor.py --test     # dry-run: print signals without sending
"""

import argparse
import json
import os
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import requests

from signals import get_buy_now_signals, SignalResult

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ALERT_EMAIL       = "vickomela36@gmail.com"
INTERVAL_SECONDS  = 3600           # 1 hour
DEDUP_CACHE_FILE  = Path(__file__).parent / ".signal_dedup_cache.json"

NOTION_API_BASE   = "https://api.notion.com/v1"
NOTION_VERSION    = "2022-06-28"

# Notion data-source (collection) ID for "Memecoin Buy Now Signals"
NOTION_DATA_SOURCE = os.getenv(
    "NOTION_DATA_SOURCE",
    "c57d31d6-ddd4-49bb-ba4a-ee5b97b580e3",
)


# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    if DEDUP_CACHE_FILE.exists():
        try:
            return json.loads(DEDUP_CACHE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    DEDUP_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def _cache_key(signal: SignalResult) -> str:
    hour_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    return f"{signal.token_address}:{hour_bucket}"


def _already_notified(signal: SignalResult, cache: dict) -> bool:
    return _cache_key(signal) in cache


def _mark_notified(signal: SignalResult, cache: dict) -> None:
    cache[_cache_key(signal)] = datetime.now(timezone.utc).isoformat()
    # Prune entries older than 48 h to keep the file small
    cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache = {k: v for k, v in cache.items() if v[:10] >= cutoff}
    _save_cache(cache)


# ---------------------------------------------------------------------------
# Gmail SMTP
# ---------------------------------------------------------------------------

def send_email(signal: SignalResult) -> None:
    sender   = os.environ["GMAIL_SENDER"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    subject = (
        f"MEMECOIN BUY NOW: {signal.token} "
        f"({signal.chain.upper()}) "
        f"+{signal.price_change_1h:.1f}% 1h"
    )
    body = f"""\
BUY NOW signal detected by memecoin-intel
==========================================

Token:        {signal.token}
Address:      {signal.token_address}
Chain:        {signal.chain}
Price:        ${signal.price_usd:.8f}
1h Change:    {signal.price_change_1h:+.2f}%
24h Volume:   ${signal.volume_24h:,.0f}
Liquidity:    ${signal.liquidity_usd:,.0f}
DexScreener:  {signal.dexscreener_url}
Detected at:  {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

--
memecoin-intel monitor  |  signals.py
"""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = ALERT_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

    print(f"    [email] sent to {ALERT_EMAIL}", flush=True)


# ---------------------------------------------------------------------------
# Notion REST API
# ---------------------------------------------------------------------------

def _notion_headers() -> dict:
    token = os.environ["NOTION_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def log_to_notion(signal: SignalResult) -> None:
    # The Notion data-source ID is a collection; the parent for page creation
    # is the underlying database (we derive the database ID from the collection).
    # We use the public pages endpoint with the database_id parent.
    #
    # The collection ID and database ID share the same UUID in Notion's API
    # when the database has a single source, so we can use it directly.
    database_id = NOTION_DATA_SOURCE.replace("collection://", "")

    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Token": {
                "title": [{"text": {"content": signal.token}}]
            },
            "Token Address": {
                "rich_text": [{"text": {"content": signal.token_address}}]
            },
            "Chain": {
                "rich_text": [{"text": {"content": signal.chain}}]
            },
            "Signal": {
                "select": {"name": "buy now"}
            },
            "Price USD": {
                "number": signal.price_usd
            },
            "Price Change 1h %": {
                "number": signal.price_change_1h
            },
            "Volume 24h": {
                "number": signal.volume_24h
            },
            "Liquidity USD": {
                "number": signal.liquidity_usd
            },
            "DexScreener URL": {
                "url": signal.dexscreener_url or None
            },
        },
    }

    r = requests.post(
        f"{NOTION_API_BASE}/pages",
        headers=_notion_headers(),
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    print(f"    [notion] logged row for {signal.token}", flush=True)


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def run_check(dry_run: bool = False) -> int:
    """Run one check cycle. Returns the number of buy-now signals found."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{now}] Running signal check…", flush=True)

    signals = get_buy_now_signals()
    cache   = _load_cache()

    if not signals:
        print(f"[{now}] No buy-now signals found.", flush=True)
        return 0

    notified = 0
    for signal in signals:
        tag = f"{signal.token} ({signal.chain})"
        if _already_notified(signal, cache):
            print(f"  [skip]    {tag} — already notified this hour", flush=True)
            continue

        print(
            f"  [BUY NOW] {tag} | "
            f"price: ${signal.price_usd:.8f} | "
            f"1h: {signal.price_change_1h:+.1f}% | "
            f"vol: ${signal.volume_24h:,.0f}",
            flush=True,
        )

        if not dry_run:
            try:
                send_email(signal)
            except Exception as exc:
                print(f"    [email ERROR] {exc}", file=sys.stderr, flush=True)

            try:
                log_to_notion(signal)
            except Exception as exc:
                print(f"    [notion ERROR] {exc}", file=sys.stderr, flush=True)

            _mark_notified(signal, cache)
        notified += 1

    print(f"[{now}] Done — {notified} new buy-now signal(s) notified.", flush=True)
    return notified


def run_loop() -> None:
    print(f"Starting monitor loop (interval: {INTERVAL_SECONDS // 60} min)…", flush=True)
    while True:
        try:
            run_check()
        except Exception as exc:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            print(f"[{ts}] [ERROR] {exc}", file=sys.stderr, flush=True)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Memecoin buy-now signal monitor")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously every hour")
    parser.add_argument("--test", action="store_true",
                        help="Dry-run: print signals without emailing or logging")
    args = parser.parse_args()

    if args.loop:
        run_loop()
    else:
        run_check(dry_run=args.test)
