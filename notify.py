"""
Standalone notifier — reads JSON from stdin (produced by check_signals.py),
sends a Gmail alert and logs a row to the Notion "Memecoin Buy Now Signals" DB
for every buy-now signal.

Required env vars:
  GMAIL_SENDER       - the Gmail address used to send (e.g. you@gmail.com)
  GMAIL_APP_PASSWORD - Gmail App Password (Settings → Security → App Passwords)
  NOTION_API_KEY     - Notion integration token  (secret_...)
"""

import json
import os
import smtplib
import sys
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText

from config import ALERT_EMAIL, NOTION_DATA_SOURCE_ID


def _send_email(token: dict) -> None:
    sender   = os.environ["GMAIL_SENDER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    symbol   = token.get("symbol", "???")
    name     = token.get("token", "Unknown")

    body = (
        f"Memecoin Buy Now Signal Detected\n\n"
        f"Token:        {name} ({symbol})\n"
        f"Price:        ${token.get('price_usd', 'N/A')}\n"
        f"1h Change:    {token.get('change_1h', 'N/A')}%\n"
        f"6h Change:    {token.get('change_6h', 'N/A')}%\n"
        f"24h Change:   {token.get('change_24h', 'N/A')}%\n"
        f"Volume 24h:   ${token.get('volume_24h', 'N/A')}\n"
        f"Liquidity:    ${token.get('liquidity_usd', 'N/A')}\n"
        f"Buy Pressure: {token.get('buy_pressure', 'N/A')}\n\n"
        f"DexScreener:  {token.get('dexscreener_url', 'N/A')}\n\n"
        f"Detected at:  {datetime.now(timezone.utc).isoformat()}\n"
    )

    msg            = MIMEText(body)
    msg["Subject"] = f"Memecoin Buy Now: {symbol}"
    msg["From"]    = sender
    msg["To"]      = ALERT_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, password)
        s.sendmail(sender, [ALERT_EMAIL], msg.as_string())
    print(f"  Email sent for {symbol}")


def _log_notion(token: dict) -> None:
    api_key = os.environ["NOTION_API_KEY"]
    now     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    symbol  = token.get("symbol", "???")
    name    = token.get("token", "Unknown")

    try:
        price = float(token.get("price_usd") or 0)
    except (ValueError, TypeError):
        price = 0.0

    bp_raw = token.get("buy_pressure", "0%").replace("%", "").strip()
    try:
        score = float(bp_raw)
    except (ValueError, TypeError):
        score = 0.0

    reason = (
        f"1h: {token.get('change_1h', '')}% | "
        f"6h: {token.get('change_6h', '')}% | "
        f"24h: {token.get('change_24h', '')}% | "
        f"Vol: ${token.get('volume_24h', '')} | "
        f"Liq: ${token.get('liquidity_usd', '')} | "
        f"Pressure: {token.get('buy_pressure', '')} | "
        f"{token.get('dexscreener_url', '')}"
    )

    payload = {
        "parent": {"database_id": NOTION_DATA_SOURCE_ID},
        "properties": {
            "Signal":     {"title":     [{"text": {"content": "buy now"}}]},
            "Token":      {"rich_text": [{"text": {"content": f"{name} ({symbol})"}}]},
            "Price":      {"number":    price},
            "Score":      {"number":    score},
            "Email Sent": {"checkbox":  True},
            "Timestamp":  {"date":      {"start": now}},
            "Reason":     {"rich_text": [{"text": {"content": reason[:2000]}}]},
        },
    }

    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=data,
        headers={
            "Authorization":  f"Bearer {api_key}",
            "Content-Type":   "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()
    print(f"  Notion row logged for {symbol}")


def main():
    data = json.load(sys.stdin)
    if "error" in data:
        print(f"[ERROR] {data['error']}", file=sys.stderr)
        sys.exit(0)

    buy_now = data.get("buy_now", [])
    if not buy_now:
        print("No buy-now signals this run.")
        return

    print(f"Found {len(buy_now)} buy-now signal(s):")
    for token in buy_now:
        print(f"  -> {token.get('symbol')} @ ${token.get('price_usd')}")
        _send_email(token)
        _log_notion(token)

    print("Done.")


if __name__ == "__main__":
    main()
