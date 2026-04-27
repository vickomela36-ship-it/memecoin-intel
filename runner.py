#!/usr/bin/env python3
"""runner.py - Hourly signal checker: logs 'buy now' signals to Notion and sends email alerts.

Required env vars (set in .env or export before running):
  NOTION_API_KEY       - Notion integration token (starts with 'secret_')
  GMAIL_USER           - Your Gmail address
  GMAIL_APP_PASSWORD   - Gmail app password (16-char, spaces stripped)
"""

import json
import os
import smtplib
import sys
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from signals import get_signals
import config

# Notion database ID for the 'Memecoin Buy Signals' database
NOTION_DATABASE_ID = "29d22a95-7503-40b9-9255-6757039bd87d"
NOTION_API_VERSION = "2022-06-28"


# ---------------------------------------------------------------------------
# Notion helper
# ---------------------------------------------------------------------------

def _notion_headers() -> dict:
    token = os.environ.get("NOTION_API_KEY", "").strip()
    if not token:
        raise RuntimeError("NOTION_API_KEY env var is not set")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def log_to_notion(signal: dict) -> None:
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token": {"title": [{"text": {"content": signal["token"]}}]},
            "Symbol": {"rich_text": [{"text": {"content": signal["symbol"]}}]},
            "Signal": {"select": {"name": signal["signal"]}},
            "Price USD": {"rich_text": [{"text": {"content": f"${signal['price_usd']}"}}]},
            "1h Change %": {"rich_text": [{"text": {"content": f"{signal['price_change_1h']:+.2f}%"}}]},
            "6h Change %": {"rich_text": [{"text": {"content": f"{signal['price_change_6h']:+.2f}%"}}]},
            "24h Change %": {"rich_text": [{"text": {"content": f"{signal['price_change_24h']:+.2f}%"}}]},
            "Volume 24h USD": {"rich_text": [{"text": {"content": f"${signal['volume_24h_usd']:,.0f}"}}]},
            "Liquidity USD": {"rich_text": [{"text": {"content": f"${signal['liquidity_usd']:,.0f}"}}]},
            "Buy Pressure": {"rich_text": [{"text": {"content": signal["buy_pressure"]}}]},
            "DexScreener URL": {"url": signal["dexscreener_url"] or None},
            "Checked At": {"date": {"start": signal["checked_at"]}},
        },
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=data,
        headers=_notion_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    print(f"  [notion] logged page id={result.get('id')}")


# ---------------------------------------------------------------------------
# Email helper
# ---------------------------------------------------------------------------

def send_email(signal: dict) -> None:
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    if not gmail_user or not app_password:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD env vars are not set")

    subject = f"Buy Now Signal: {signal['symbol']} ({signal['token']})"
    html = f"""
    <html><body style="font-family:sans-serif;max-width:600px">
    <h2 style="color:#16a34a">Buy Now Signal Detected</h2>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
      <tr><th style="background:#f0fdf4">Token</th><td>{signal['token']} ({signal['symbol']})</td></tr>
      <tr><th style="background:#f0fdf4">Price USD</th><td>${signal['price_usd']}</td></tr>
      <tr><th style="background:#f0fdf4">1h Change</th><td>{signal['price_change_1h']:+.2f}%</td></tr>
      <tr><th style="background:#f0fdf4">6h Change</th><td>{signal['price_change_6h']:+.2f}%</td></tr>
      <tr><th style="background:#f0fdf4">24h Change</th><td>{signal['price_change_24h']:+.2f}%</td></tr>
      <tr><th style="background:#f0fdf4">Volume 24h</th><td>${signal['volume_24h_usd']:,.0f}</td></tr>
      <tr><th style="background:#f0fdf4">Liquidity</th><td>${signal['liquidity_usd']:,.0f}</td></tr>
      <tr><th style="background:#f0fdf4">Buy Pressure</th><td>{signal['buy_pressure']}</td></tr>
      <tr><th style="background:#f0fdf4">Checked At</th><td>{signal['checked_at']}</td></tr>
    </table>
    <p><a href="{signal['dexscreener_url']}">View on DexScreener</a></p>
    <p style="color:#6b7280;font-size:12px">This is an automated alert from memecoin-intel. Not financial advice.</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = config.ALERT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_user, app_password)
        smtp.sendmail(gmail_user, config.ALERT_EMAIL, msg.as_string())
    print(f"  [email] sent to {config.ALERT_EMAIL}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Load .env if present
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{now}] Running signal check...")

    signals = get_signals()
    buy_now = [s for s in signals if s["signal"] == "buy now"]
    print(f"  {len(signals)} pairs evaluated, {len(buy_now)} buy-now signal(s)")

    for s in buy_now:
        print(f"  >>> BUY NOW: {s['symbol']} ({s['token']}) price=${s['price_usd']} 1h={s['price_change_1h']:+.2f}%")
        try:
            log_to_notion(s)
        except Exception as exc:
            print(f"  [notion] ERROR: {exc}", file=sys.stderr)
        try:
            send_email(s)
        except Exception as exc:
            print(f"  [email] ERROR: {exc}", file=sys.stderr)

    print("[done]")


if __name__ == "__main__":
    main()
