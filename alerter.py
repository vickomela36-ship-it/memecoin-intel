"""
Hourly alerter — runs the scanner, sends emails, and logs BUY NOW signals to Notion.

Invoked automatically by the /loop every hour (or by Claude Code hook).
Can also be run manually:
    python alerter.py

Email via Gmail SMTP (needs GMAIL_ADDRESS + GMAIL_APP_PASSWORD in env).
Notion via REST API (needs NOTION_API_KEY in env).

Deduplication: notified.json stores {mint_address: last_notified_iso} so the
same token isn't re-alerted within NOTIFY_COOLDOWN_HOURS.
"""

from __future__ import annotations

import json
import os
import smtplib
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests

import config

NOTIFIED_FILE = os.path.join(os.path.dirname(__file__), "notified.json")
NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION   = "2022-06-28"


# ─── Deduplication ────────────────────────────────────────────────────────────

def _load_notified() -> dict[str, str]:
    if not os.path.exists(NOTIFIED_FILE):
        return {}
    with open(NOTIFIED_FILE) as f:
        return json.load(f)


def _save_notified(data: dict[str, str]) -> None:
    with open(NOTIFIED_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _already_notified(mint: str, notified: dict[str, str]) -> bool:
    last = notified.get(mint)
    if not last:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.NOTIFY_COOLDOWN_HOURS)
    return datetime.fromisoformat(last) > cutoff


# ─── Email ────────────────────────────────────────────────────────────────────

def _build_email_body(signal: dict) -> str:
    def fmt(n: float) -> str:
        if n >= 1_000_000:
            return f"${n/1_000_000:.2f}M"
        if n >= 1_000:
            return f"${n/1_000:.1f}K"
        return f"${n:.8f}" if n < 0.01 else f"${n:.4f}"

    return f"""\
BUY NOW Signal Detected — {signal['token_symbol']} ({signal['token_name']})
{'=' * 60}

Token:       {signal['token_name']} ({signal['token_symbol']})
Mint:        {signal['mint_address']}
DEX:         {signal['dex_id']}  |  Pair: {signal['pair_address']}

Price:       {fmt(signal['price_usd'])}
1h change:   {signal['h1_change']:+.1f}%
6h change:   {signal['h6_change']:+.1f}%
24h change:  {signal['h24_change']:+.1f}%

Confidence:  {signal['confidence']:.0%}
FDV:         {fmt(signal['fdv'])}
Vol 24h:     {fmt(signal['volume_h24'])}
Buy ratio:   {signal['buy_ratio_h1']:.0%}

Analysis:
  {signal['reason']}

DexScreener: https://dexscreener.com/solana/{signal['pair_address']}
{'─' * 60}
⚠  This is NOT financial advice. DYOR before trading memecoins.
"""


def send_email(signal: dict) -> bool:
    if not config.GMAIL_ADDRESS or not config.GMAIL_APP_PASSWORD:
        print(f"  [email] Skipped (GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set)", file=sys.stderr)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚀 BUY NOW: {signal['token_symbol']} ({signal['token_name']})"
    msg["From"]    = config.GMAIL_ADDRESS
    msg["To"]      = config.ALERT_EMAIL

    body = _build_email_body(signal)
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            smtp.sendmail(config.GMAIL_ADDRESS, config.ALERT_EMAIL, msg.as_string())
        print(f"  [email] Sent for {signal['token_symbol']}")
        return True
    except Exception as e:
        print(f"  [email] Failed for {signal['token_symbol']}: {e}", file=sys.stderr)
        return False


# ─── Notion ───────────────────────────────────────────────────────────────────

def log_to_notion(signal: dict, email_sent: bool) -> bool:
    if not config.NOTION_API_KEY:
        print(f"  [notion] Skipped (NOTION_API_KEY not set)", file=sys.stderr)
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    title   = f"{signal['token_symbol']} — BUY NOW"

    payload: dict[str, Any] = {
        "parent": {"database_id": config.NOTION_DB_ID},
        "properties": {
            "Signal":    {"title": [{"text": {"content": title}}]},
            "Token":     {"rich_text": [{"text": {"content": signal["token_name"]}}]},
            "Price":     {"number": signal["price_usd"]},
            "Score":     {"number": signal["confidence"]},
            "Reason":    {"rich_text": [{"text": {"content": signal["reason"]}}]},
            "Timestamp": {"date": {"start": now_iso}},
            "Email Sent": {"checkbox": email_sent},
        },
    }

    headers = {
        "Authorization":  f"Bearer {config.NOTION_API_KEY}",
        "Content-Type":   "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    for attempt in range(3):
        try:
            r = requests.post(NOTION_PAGES_URL, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            print(f"  [notion] Logged {signal['token_symbol']}")
            return True
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"  [notion] Failed for {signal['token_symbol']}: {e}", file=sys.stderr)
    return False


# ─── Main ─────────────────────────────────────────────────────────────────────

def run() -> None:
    print(f"\n[alerter] {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    # Run scanner and capture JSON output
    scanner = os.path.join(os.path.dirname(__file__), "scanner.py")
    try:
        result = subprocess.run(
            [sys.executable, scanner, "--json"],
            capture_output=True, text=True, timeout=120
        )
    except Exception as e:
        print(f"[alerter] Scanner failed: {e}", file=sys.stderr)
        return

    if result.returncode != 0:
        print(f"[alerter] Scanner error: {result.stderr}", file=sys.stderr)
        return

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"[alerter] Bad JSON from scanner: {e}", file=sys.stderr)
        return

    buy_now = [s for s in data.get("signals", []) if s["signal_type"] == "BUY_NOW"]

    if not buy_now:
        print("[alerter] No BUY NOW signals this scan.")
        return

    print(f"[alerter] {len(buy_now)} BUY NOW signal(s) found.")

    notified = _load_notified()

    for signal in buy_now:
        mint = signal["mint_address"]
        if _already_notified(mint, notified):
            print(f"  [skip]  {signal['token_symbol']} — notified within cooldown window")
            continue

        print(f"  [alert] {signal['token_symbol']} (confidence {signal['confidence']:.0%})")
        email_ok  = send_email(signal)
        notion_ok = log_to_notion(signal, email_sent=email_ok)

        if email_ok or notion_ok:
            notified[mint] = datetime.now(timezone.utc).isoformat()

    _save_notified(notified)
    print("[alerter] Done.\n")


if __name__ == "__main__":
    run()
