"""
Standalone hourly alerter — no Claude session required.
Checks signals, sends Gmail alert and logs to Notion on 'buy now'.

Run manually:         python alerter.py
Run every hour (cron): 0 * * * * /usr/bin/python3 /path/to/alerter.py
"""

import smtplib
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    GMAIL_SENDER, GMAIL_APP_PASSWORD, ALERT_RECIPIENT,
    NOTION_TOKEN, NOTION_DATABASE_ID,
)
from signals import get_signals


def send_email(token: dict) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Buy Now Signal: {token['token']} ({token['chain'].upper()})"
    msg["From"] = GMAIL_SENDER
    msg["To"] = ALERT_RECIPIENT

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""
<html><body style="font-family:sans-serif;max-width:600px">
<h2 style="color:#16a34a">🚨 Buy Now Signal — {token['token']}</h2>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:6px;font-weight:bold">Token</td><td>{token['token']}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">Chain</td><td>{token['chain'].upper()}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">Price</td><td>${token['price_usd']:.8f}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">1h Change</td><td style="color:#16a34a">+{token['price_change_1h']:.1f}%</td></tr>
  <tr><td style="padding:6px;font-weight:bold">24h Volume</td><td>${token['volume_24h']:,.0f}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">Liquidity</td><td>${token['liquidity_usd']:,.0f}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">Token Address</td><td style="font-size:12px">{token['token_address']}</td></tr>
  <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">DexScreener</td>
    <td><a href="{token['dexscreener_url']}">{token['dexscreener_url']}</a></td></tr>
  <tr><td style="padding:6px;font-weight:bold">Detected at</td><td>{ts}</td></tr>
</table>
</body></html>"""

    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_SENDER, ALERT_RECIPIENT, msg.as_string())
    print(f"  Email sent for {token['token']}")


def log_to_notion(token: dict) -> None:
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token": {"title": [{"text": {"content": token["token"]}}]},
            "Chain": {"rich_text": [{"text": {"content": token["chain"]}}]},
            "Price USD": {"number": token["price_usd"]},
            "Price Change 1h %": {"number": token["price_change_1h"]},
            "Volume 24h": {"number": token["volume_24h"]},
            "Liquidity USD": {"number": token["liquidity_usd"]},
            "DexScreener URL": {"url": token["dexscreener_url"]},
            "Token Address": {"rich_text": [{"text": {"content": token["token_address"]}}]},
            "Signal": {"select": {"name": "buy now"}},
        },
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=data,
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()
    print(f"  Notion logged for {token['token']}")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] Checking signals...")

    signals = get_signals()
    buy_now = [s for s in signals if s.get("signal") == "buy now"]
    errors = [s for s in signals if s.get("fetch_failed")]

    if errors:
        print(f"  Fetch error: {errors[0].get('error')}")
        return

    checked = len(signals)
    print(f"  Checked {checked} tokens, {len(buy_now)} buy now signal(s)")

    for token in buy_now:
        print(f"  → {token['token']} on {token['chain']} +{token['price_change_1h']:.1f}%")
        try:
            send_email(token)
        except Exception as e:
            print(f"  Email error: {e}")
        try:
            log_to_notion(token)
        except Exception as e:
            print(f"  Notion error: {e}")


if __name__ == "__main__":
    main()
