"""
Notification handler for memecoin buy-now signals.

Reads signals from stdin (JSON output of signals.py) or accepts a file path.
For each buy-now signal:
  1. Logs a row to the Notion database
  2. Sends an email via Gmail SMTP

Environment variables required:
  NOTION_TOKEN          — Notion integration secret (secret_...)
  NOTION_DATABASE_ID    — Target database ID (without dashes)
  GMAIL_USER            — Your Gmail address
  GMAIL_APP_PASSWORD    — Gmail app password (not your account password)
  ALERT_EMAIL           — Recipient email address

Usage:
    python3 signals.py | python3 notify.py
    python3 notify.py signals_output.json
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText

import requests

NOTION_API = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


def load_signals(source) -> dict:
    if source == "-" or source is None:
        return json.load(sys.stdin)
    with open(source) as f:
        return json.load(f)


def notion_log(signal: dict, token: str, database_id: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    ts = signal["timestamp"].replace("+00:00", "Z")
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Signal": {
                "title": [{"text": {"content": f"{signal['symbol']}: {signal['coin']}"}}]
            },
            "Coin": {"rich_text": [{"text": {"content": signal["coin"]}}]},
            "Signal Type": {"select": {"name": "buy now"}},
            "Confidence": {"number": signal["confidence"]},
            "Price USD": {"number": signal["price_usd"]},
            "Reason": {"rich_text": [{"text": {"content": signal["reason"]}}]},
            "Timestamp": {"date": {"start": ts}},
        },
    }
    resp = requests.post(NOTION_API, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_email(signal: dict, gmail_user: str, app_password: str, recipient: str):
    pct = signal["price_change_24h_pct"]
    vol = signal["volume_24h_usd"]
    conf_pct = int(signal["confidence"] * 100)

    body = f"""MEMECOIN BUY NOW SIGNAL
=======================
Coin:       {signal['coin']} ({signal['symbol']})
Price:      ${signal['price_usd']:,.6f}
24h Change: +{pct:.1f}%
Volume:     ${vol:,.0f}
Confidence: {conf_pct}%
Reason:     {signal['reason']}
Time:       {signal['timestamp']}

This signal was generated automatically by memecoin-intel.
"""
    msg = MIMEText(body)
    msg["Subject"] = f"🚀 MEMECOIN BUY NOW: {signal['symbol']} (+{pct:.1f}%)"
    msg["From"] = gmail_user
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_user, app_password)
        smtp.sendmail(gmail_user, [recipient], msg.as_string())


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else None
    data = load_signals(source)

    buy_now = data.get("buy_now_signals", [])
    if not buy_now:
        print("No buy-now signals — nothing to notify.")
        return

    notion_token = os.environ.get("NOTION_TOKEN", "")
    database_id = os.environ.get("NOTION_DATABASE_ID", "")
    gmail_user = os.environ.get("GMAIL_USER", "")
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipient = os.environ.get("ALERT_EMAIL", "vickomela36@gmail.com")

    for signal in buy_now:
        name = signal["coin"]
        sym = signal["symbol"]
        print(f"Processing: {sym} ({name}) — {signal['price_change_24h_pct']:+.1f}%")

        if notion_token and database_id:
            try:
                notion_log(signal, notion_token, database_id)
                print(f"  ✓ Logged to Notion")
            except Exception as exc:
                print(f"  ✗ Notion error: {exc}", file=sys.stderr)
        else:
            print("  ! NOTION_TOKEN or NOTION_DATABASE_ID not set — skipping Notion log")

        if gmail_user and app_password:
            try:
                send_email(signal, gmail_user, app_password, recipient)
                print(f"  ✓ Email sent to {recipient}")
            except Exception as exc:
                print(f"  ✗ Email error: {exc}", file=sys.stderr)
        else:
            print("  ! GMAIL_USER or GMAIL_APP_PASSWORD not set — skipping email")

    print(f"\nDone. Processed {len(buy_now)} buy-now signal(s).")


if __name__ == "__main__":
    main()
