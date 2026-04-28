"""
Standalone notifier — used when running outside a Claude Code session.
Requires env vars:
  GMAIL_SENDER      - sender Gmail address
  GMAIL_APP_PASSWORD- Gmail App Password (not your login password)
  NOTION_API_KEY    - Notion integration token (secret_...)

Usage: python notify.py  (reads JSON from stdin, produced by check_signals.py)
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
    sender = os.environ["GMAIL_SENDER"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    symbol = token.get("symbol", "???")
    name = token.get("token", "Unknown")

    body = f"""🚨 Memecoin Buy Now Signal Detected

Token:         {name} ({symbol})
Price:         ${token.get('price_usd', 'N/A')}
1h Change:     {token.get('change_1h', 'N/A')}%
24h Change:    {token.get('change_24h', 'N/A')}%
Volume 24h:    ${token.get('volume_24h', 'N/A')}
Liquidity:     ${token.get('liquidity_usd', 'N/A')}
Buy Pressure:  {token.get('buy_pressure', 'N/A')}

DexScreener:   {token.get('dexscreener_url', 'N/A')}

Checked at: {datetime.now(timezone.utc).isoformat()}
"""

    msg = MIMEText(body)
    msg["Subject"] = f"🚨 Memecoin Buy Now: {symbol}"
    msg["From"] = sender
    msg["To"] = ALERT_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, password)
        s.sendmail(sender, [ALERT_EMAIL], msg.as_string())
    print(f"  ✉ Email sent for {symbol}")


def _log_notion(token: dict) -> None:
    api_key = os.environ["NOTION_API_KEY"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    payload = {
        "parent": {"database_id": NOTION_DATA_SOURCE_ID},
        "properties": {
            "Token": {"title": [{"text": {"content": token.get("token", "Unknown")}}]},
            "Symbol": {"rich_text": [{"text": {"content": token.get("symbol", "")}}]},
            "Signal": {"select": {"name": "buy now"}},
            "Price USD": {"rich_text": [{"text": {"content": token.get("price_usd", "")}}]},
            "1h Change %": {"rich_text": [{"text": {"content": token.get("change_1h", "")}}]},
            "6h Change %": {"rich_text": [{"text": {"content": token.get("change_6h", "")}}]},
            "24h Change %": {"rich_text": [{"text": {"content": token.get("change_24h", "")}}]},
            "Volume 24h USD": {"rich_text": [{"text": {"content": token.get("volume_24h", "")}}]},
            "Liquidity USD": {"rich_text": [{"text": {"content": token.get("liquidity_usd", "")}}]},
            "Buy Pressure": {"rich_text": [{"text": {"content": token.get("buy_pressure", "")}}]},
            "DexScreener URL": {"url": token.get("dexscreener_url") or None},
            "Checked At": {"date": {"start": now}},
        },
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()
    print(f"  📋 Notion row logged for {token.get('symbol', '???')}")


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
        print(f"  → {token.get('symbol')} @ ${token.get('price_usd')}")
        _send_email(token)
        _log_notion(token)

    print("Done.")


if __name__ == "__main__":
    main()
