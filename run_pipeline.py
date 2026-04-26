#!/usr/bin/env python3
"""
Hourly buy-signal pipeline.
  1. Runs the signal engine (signals.py)
  2. For each "buy now" signal: sends email + logs to Notion
  3. Skips silently if no buy signals found

Credentials are read from environment variables (see .env.example).
"""
import json
import os
import smtplib
import sys
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Ensure project directory is importable
sys.path.insert(0, str(Path(__file__).parent))
from signals import run as get_signals  # noqa: E402

# ── Credentials (set as env vars or in a .env file sourced by cron) ──────────
ALERT_EMAIL    = "vickomela36@gmail.com"
GMAIL_SENDER   = os.environ.get("GMAIL_SENDER", "")      # your gmail address
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS", "")    # gmail app password
NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")      # secret_xxx...
# Notion database created for this project:
NOTION_DB_ID   = "07d27f13d540461fbe2c131eedcbde6a"


def _str(v) -> str:
    return "" if v is None else str(v)


def send_email(sig: dict) -> None:
    sym  = sig["token_symbol"]
    name = sig["token_name"]

    msg             = MIMEMultipart("alternative")
    msg["Subject"]  = f"\U0001f680 Buy Signal: {sym} ({name})"
    msg["From"]     = GMAIL_SENDER
    msg["To"]       = ALERT_EMAIL

    body = (
        f"Memecoin Buy Signal\n"
        f"{'='*40}\n"
        f"Token:      {sym} – {name}\n"
        f"Address:    {sig['token_address']}\n"
        f"Chain/DEX:  {sig['chain']} / {sig['dex']}\n"
        f"\n"
        f"Price:      ${sig['price_usd']}\n"
        f"1h Change:  {sig['change_1h_pct']}%\n"
        f"6h Change:  {sig['change_6h_pct']}%\n"
        f"24h Change: {sig['change_24h_pct']}%\n"
        f"Volume 24h: ${sig['volume_24h_usd']}\n"
        f"Liquidity:  ${sig['liquidity_usd']}\n"
        f"\n"
        f"Reason: {sig['reason']}\n"
        f"\n"
        f"Chart:      {sig['dex_url']}\n"
        f"Checked at: {sig['checked_at']}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
        smtp.sendmail(GMAIL_SENDER, ALERT_EMAIL, msg.as_string())

    print(f"  ✉  Email sent → {ALERT_EMAIL} [{sym}]")


def _rt(text: str) -> dict:
    """Notion rich_text property value."""
    return {"rich_text": [{"text": {"content": text}}]}


def log_to_notion(sig: dict) -> None:
    title = f"{sig['token_symbol']} – {sig['token_name']}"

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Token":          {"title": [{"text": {"content": title}}]},
            "Signal":         {"select": {"name": "buy now"}},
            "Price USD":      _rt(_str(sig["price_usd"])),
            "1h Change %":    _rt(_str(sig["change_1h_pct"])),
            "6h Change %":    _rt(_str(sig["change_6h_pct"])),
            "24h Change %":   _rt(_str(sig["change_24h_pct"])),
            "Volume 24h USD": _rt(_str(sig["volume_24h_usd"])),
            "Liquidity USD":  _rt(_str(sig["liquidity_usd"])),
            "Chain":          _rt(_str(sig["chain"])),
            "DEX":            _rt(_str(sig["dex"])),
            "Reason":         _rt(_str(sig["reason"])),
            "DEX URL":        {"url": sig["dex_url"] or None},
            "Token Address":  _rt(sig["token_address"]),
            "Checked At":     {"date": {"start": sig["checked_at"]}},
        },
    }

    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=data,
        headers={
            "Authorization":  f"Bearer {NOTION_TOKEN}",
            "Content-Type":   "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()

    print(f"  \U0001f4cb Notion row added [{title}]")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] memecoin-intel signal check")

    signals     = get_signals()
    buy_signals = [s for s in signals if s["signal"] == "buy now"]

    print(f"  Scanned {len(signals)} token(s)  →  {len(buy_signals)} buy signal(s)")

    for sig in buy_signals:
        sym = sig["token_symbol"]
        print(f"  \U0001f525 BUY NOW: {sym} | {sig['reason']}")

        if GMAIL_SENDER and GMAIL_APP_PASS:
            try:
                send_email(sig)
            except Exception as exc:
                print(f"  ⚠  Email error [{sym}]: {exc}", file=sys.stderr)
        else:
            print("  ⚠  GMAIL_SENDER / GMAIL_APP_PASS not set — skipping email")

        if NOTION_TOKEN:
            try:
                log_to_notion(sig)
            except Exception as exc:
                print(f"  ⚠  Notion error [{sym}]: {exc}", file=sys.stderr)
        else:
            print("  ⚠  NOTION_TOKEN not set — skipping Notion log")

    if not buy_signals:
        print("  No buy signals this hour.")


if __name__ == "__main__":
    main()
