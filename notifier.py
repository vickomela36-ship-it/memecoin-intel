"""
Handles outbound notifications for 'buy now' signals:
  - send_email()    → Gmail SMTP (HTML email)
  - log_to_notion() → Notion REST API (adds a row to the Buy Signals database)
"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

import requests


# ── Email ──────────────────────────────────────────────────────────────────────

def send_email(signal: dict) -> bool:
    from config import GMAIL_SENDER, GMAIL_APP_PASSWORD, NOTIFICATION_EMAIL

    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        print("[notifier] Email skipped — GMAIL_SENDER / GMAIL_APP_PASSWORD not set in config.py")
        return False

    symbol   = signal["symbol"]
    token    = signal["token"]
    price    = signal["price_usd"]
    url      = signal["dexscreener_url"]
    checked  = signal["checked_at"]

    subject = f"BUY NOW Signal: {symbol}"

    html = f"""\
<html><body style="font-family:sans-serif;max-width:600px">
<h2 style="color:#16a34a">&#x1F7E2; BUY NOW Signal — {symbol}</h2>
<table border="1" cellpadding="8" cellspacing="0"
       style="border-collapse:collapse;width:100%">
  <tr><td><b>Token</b></td>        <td>{token} ({symbol})</td></tr>
  <tr><td><b>Signal</b></td>       <td style="color:#16a34a"><b>BUY NOW</b></td></tr>
  <tr><td><b>Price</b></td>        <td>${price}</td></tr>
  <tr><td><b>1h change</b></td>    <td>{signal["1h_change"]}</td></tr>
  <tr><td><b>6h change</b></td>    <td>{signal["6h_change"]}</td></tr>
  <tr><td><b>24h change</b></td>   <td>{signal["24h_change"]}</td></tr>
  <tr><td><b>Volume 24h</b></td>   <td>{signal["volume_24h"]}</td></tr>
  <tr><td><b>Liquidity</b></td>    <td>{signal["liquidity_usd"]}</td></tr>
  <tr><td><b>Buy pressure</b></td> <td>{signal["buy_pressure"]}</td></tr>
  <tr><td><b>Checked at</b></td>   <td>{checked}</td></tr>
</table>
{"<p><a href='" + url + "'>View on DexScreener →</a></p>" if url else ""}
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = NOTIFICATION_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, NOTIFICATION_EMAIL, msg.as_string())
        print(f"[notifier] Email sent → {NOTIFICATION_EMAIL} ({symbol})")
        return True
    except Exception as exc:
        print(f"[notifier] Email failed: {exc}")
        return False


# ── Notion ─────────────────────────────────────────────────────────────────────

_NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
_NOTION_VERSION   = "2022-06-28"


def log_to_notion(signal: dict) -> bool:
    from config import NOTION_TOKEN, NOTION_DATABASE_ID

    if not NOTION_TOKEN:
        print("[notifier] Notion skipped — NOTION_TOKEN not set in config.py")
        return False

    headers = {
        "Authorization":  f"Bearer {NOTION_TOKEN}",
        "Content-Type":   "application/json",
        "Notion-Version": _NOTION_VERSION,
    }

    checked_at = signal.get("checked_at") or datetime.now(timezone.utc).isoformat()
    dex_url    = signal.get("dexscreener_url") or None

    def rich(text: str) -> list:
        return [{"text": {"content": str(text)}}]

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token":          {"title":     rich(signal["token"])},
            "Symbol":         {"rich_text": rich(signal["symbol"])},
            "Signal":         {"select":    {"name": signal["signal"]}},
            "Price USD":      {"rich_text": rich(signal["price_usd"])},
            "1h Change %":    {"rich_text": rich(signal["1h_change"])},
            "6h Change %":    {"rich_text": rich(signal["6h_change"])},
            "24h Change %":   {"rich_text": rich(signal["24h_change"])},
            "Volume 24h USD": {"rich_text": rich(signal["volume_24h"])},
            "Liquidity USD":  {"rich_text": rich(signal["liquidity_usd"])},
            "Buy Pressure":   {"rich_text": rich(signal["buy_pressure"])},
            "Checked At":     {"date":      {"start": checked_at}},
            **({"DexScreener URL": {"url": dex_url}} if dex_url else {}),
        },
    }

    try:
        resp = requests.post(_NOTION_PAGES_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        print(f"[notifier] Notion row added ({signal['symbol']})")
        return True
    except Exception as exc:
        print(f"[notifier] Notion failed: {exc}")
        return False
