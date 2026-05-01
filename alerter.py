"""
Standalone hourly alerter — runs via system cron without requiring Claude to be active.
Reads signals, sends email via Gmail SMTP, and logs to Notion REST API.

Required env vars:
  NOTION_TOKEN      — Notion integration secret (starts with ntn_...)
  GMAIL_ADDRESS     — sender Gmail address
  GMAIL_APP_PASSWORD — Gmail App Password (16-char, spaces OK)
  NOTIFY_EMAIL      — recipient (default: vickomela36@gmail.com)
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

sys.path.insert(0, os.path.dirname(__file__))
from signals import get_signals

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DS_ID = "44763c62-4d07-4fde-bb1c-503846807aeb"
NOTION_API   = "https://api.notion.com/v1"

GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL       = os.environ.get("NOTIFY_EMAIL", "vickomela36@gmail.com")


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def log_to_notion(sig: dict, ts: str) -> None:
    if not NOTION_TOKEN:
        print("[WARN] NOTION_TOKEN not set — skipping Notion log")
        return
    payload = {
        "parent": {"database_id": NOTION_DS_ID},
        "properties": {
            "Signal Entry": {"title": [{"text": {"content": f"{sig['symbol']} @ ${sig['price_usd']:.6f} ({sig['chain']})"}}]},
            "Symbol":           {"rich_text": [{"text": {"content": sig["symbol"]}}]},
            "Pair Address":     {"rich_text": [{"text": {"content": sig["pair_address"]}}]},
            "Signal":           {"select": {"name": "buy now"}},
            "Price USD":        {"number": sig["price_usd"]},
            "Price Change 5m %": {"number": sig["price_change_5m"]},
            "Price Change 1h %": {"number": sig["price_change_1h"]},
            "Volume 5m USD":    {"number": sig["volume_5m_usd"]},
            "Liquidity USD":    {"number": sig["liquidity_usd"]},
            "Email Sent":       {"checkbox": True},
            "Timestamp":        {"date": {"start": ts}},
        },
    }
    resp = requests.post(f"{NOTION_API}/pages", headers=_notion_headers(), json=payload, timeout=10)
    resp.raise_for_status()


def _html_email(sig: dict, ts: str) -> str:
    return f"""
<html><body>
<h2 style="color:#d63031">🚨 Buy Now Signal: {sig['symbol']} on {sig['chain'].upper()}</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:monospace">
  <tr style="background:#dfe6e9"><th>Field</th><th>Value</th></tr>
  <tr><td>Symbol</td><td>{sig['symbol']}</td></tr>
  <tr><td>Chain</td><td>{sig['chain'].upper()}</td></tr>
  <tr><td>Price USD</td><td>${sig['price_usd']:.8f}</td></tr>
  <tr><td>5m Change %</td><td style="color:#00b894">+{sig['price_change_5m']:.2f}%</td></tr>
  <tr><td>1h Change %</td><td style="color:#00b894">+{sig['price_change_1h']:.2f}%</td></tr>
  <tr><td>Volume 5m USD</td><td>${sig['volume_5m_usd']:,.0f}</td></tr>
  <tr><td>Liquidity USD</td><td>${sig['liquidity_usd']:,.0f}</td></tr>
  <tr><td>Pair Address</td><td>{sig['pair_address']}</td></tr>
  <tr><td>DexScreener</td><td><a href="{sig['dex_url']}">{sig['dex_url']}</a></td></tr>
  <tr><td>Timestamp (UTC)</td><td>{ts}</td></tr>
</table>
</body></html>
"""


def send_email(sig: dict, ts: str) -> None:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("[WARN] Gmail credentials not set — skipping email")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 Buy Now Signal: {sig['symbol']} on {sig['chain'].upper()}"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(_html_email(sig, ts), "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD.replace(" ", ""))
        smtp.sendmail(GMAIL_ADDRESS, NOTIFY_EMAIL, msg.as_string())


def main() -> None:
    buy_signals = get_signals(only_buy=True)
    if not buy_signals:
        print(f"[{datetime.now(timezone.utc).isoformat()}] No buy-now signals.")
        return

    ts = datetime.now(timezone.utc).isoformat()
    for sig in buy_signals:
        print(f"[BUY NOW] {sig['symbol']} @ ${sig['price_usd']:.8f} ({sig['chain']})")
        try:
            send_email(sig, ts)
            print(f"  ✓ Email sent to {NOTIFY_EMAIL}")
        except Exception as e:
            print(f"  ✗ Email failed: {e}")
        try:
            log_to_notion(sig, ts)
            print(f"  ✓ Logged to Notion")
        except Exception as e:
            print(f"  ✗ Notion log failed: {e}")

    print(f"Done. Processed {len(buy_signals)} buy-now signal(s).")


if __name__ == "__main__":
    main()
