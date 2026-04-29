"""
Handles 'buy now' notifications:
  - send_email()    → SMTP email to ALERT_EMAIL
  - log_to_notion() → Notion API row in the Buy Signals database
"""

import smtplib
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from signals import SignalResult


def send_email(signal: SignalResult) -> None:
    from config import ALERT_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    subject = f"BUY NOW Signal: {signal.token} ({signal.symbol})"

    plain = f"""\
BUY NOW Signal Detected!

Token:         {signal.token} ({signal.symbol})
Price:         ${signal.price_usd:.8f}
1h Change:     {signal.change_1h:+.2f}%
6h Change:     {signal.change_6h:+.2f}%
24h Change:    {signal.change_24h:+.2f}%
Volume 24h:    ${signal.volume_24h:,.0f}
Liquidity:     ${signal.liquidity_usd:,.0f}
Buy Pressure:  {signal.buy_pressure * 100:.1f}%

Reason: {signal.reason}

DexScreener: {signal.dexscreener_url}
Checked at:  {ts}
"""

    def _color(val: float) -> str:
        return "green" if val >= 0 else "red"

    html = f"""\
<html><body style="font-family:sans-serif;max-width:600px">
<h2 style="color:green">&#x1F6A8; BUY NOW: {signal.token} ({signal.symbol})</h2>
<table border="1" cellpadding="8" cellspacing="0"
       style="border-collapse:collapse;width:100%">
  <tr><td><b>Price</b></td><td>${signal.price_usd:.8f}</td></tr>
  <tr><td><b>1h Change</b></td>
      <td style="color:{_color(signal.change_1h)}">{signal.change_1h:+.2f}%</td></tr>
  <tr><td><b>6h Change</b></td>
      <td style="color:{_color(signal.change_6h)}">{signal.change_6h:+.2f}%</td></tr>
  <tr><td><b>24h Change</b></td>
      <td style="color:{_color(signal.change_24h)}">{signal.change_24h:+.2f}%</td></tr>
  <tr><td><b>Volume 24h</b></td><td>${signal.volume_24h:,.0f}</td></tr>
  <tr><td><b>Liquidity</b></td><td>${signal.liquidity_usd:,.0f}</td></tr>
  <tr><td><b>Buy Pressure</b></td><td>{signal.buy_pressure * 100:.1f}%</td></tr>
  <tr><td><b>Reason</b></td><td>{signal.reason}</td></tr>
</table>
<br>
<a href="{signal.dexscreener_url}">&#x1F4C8; View on DexScreener</a>
<br><br><small>Checked at: {ts}</small>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    print(f"[notifier] Email sent → {ALERT_EMAIL} for {signal.token}")


def log_to_notion(signal: SignalResult) -> None:
    from config import NOTION_TOKEN, NOTION_DATABASE_ID

    now = datetime.now(timezone.utc).isoformat()

    properties = {
        "Token": {"title": [{"text": {"content": signal.token}}]},
        "Symbol": {"rich_text": [{"text": {"content": signal.symbol}}]},
        "Signal": {"select": {"name": signal.signal}},
        "Price USD": {"rich_text": [{"text": {"content": f"${signal.price_usd:.8f}"}}]},
        "Volume 24h USD": {
            "rich_text": [{"text": {"content": f"${signal.volume_24h:,.0f}"}}]
        },
        "Liquidity USD": {
            "rich_text": [{"text": {"content": f"${signal.liquidity_usd:,.0f}"}}]
        },
        "1h Change %": {
            "rich_text": [{"text": {"content": f"{signal.change_1h:+.2f}%"}}]
        },
        "6h Change %": {
            "rich_text": [{"text": {"content": f"{signal.change_6h:+.2f}%"}}]
        },
        "24h Change %": {
            "rich_text": [{"text": {"content": f"{signal.change_24h:+.2f}%"}}]
        },
        "Buy Pressure": {
            "rich_text": [{"text": {"content": f"{signal.buy_pressure * 100:.1f}%"}}]
        },
        "Checked At": {"date": {"start": now}},
    }

    if signal.dexscreener_url:
        properties["DexScreener URL"] = {"url": signal.dexscreener_url}

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        json=payload,
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    print(f"[notifier] Notion logged: {signal.token} — {signal.signal}")
