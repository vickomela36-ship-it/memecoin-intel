"""
Notification layer: email via Gmail SMTP + row logging to Notion database.

Required env vars:
  GMAIL_USER         — sender Gmail address
  GMAIL_APP_PASSWORD — 16-char Google App Password (not your account password)
  NOTION_TOKEN       — Notion internal integration token (secret_...)

Notion database ID is hardcoded to the existing 'Memecoin Buy Now Signals' DB.
"""

import os
import smtplib
import requests
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)

RECIPIENT       = "vickomela36@gmail.com"
NOTION_DB_ID    = "ec3ba050-a06d-40c2-a92e-a87b51ceb459"
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION  = "2022-06-28"


# ── Email ─────────────────────────────────────────────────────────────────────

def send_buy_email(signal: dict) -> None:
    user     = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    token     = signal.get("token", "UNKNOWN")
    chain     = signal.get("chain", "")
    price     = signal.get("price_usd", 0)
    change    = signal.get("price_change_1h", 0)
    liquidity = signal.get("liquidity_usd", 0)
    volume    = signal.get("volume_24h", 0)
    dex_url   = signal.get("dex_url", "")
    address   = signal.get("token_address", "")
    ts        = signal.get("timestamp", "")

    subject = f"BUY NOW: {token} on {chain.upper()} (+{change:.1f}% in 1h)"

    html_body = f"""\
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
  <h2 style="color:#16a34a">🚀 Buy Signal Detected</h2>
  <table cellpadding="8" style="border-collapse:collapse;width:100%">
    <tr style="background:#f0fdf4"><td><b>Token</b></td><td>{token}</td></tr>
    <tr><td><b>Chain</b></td><td>{chain}</td></tr>
    <tr style="background:#f0fdf4"><td><b>Price (USD)</b></td><td>${price:.8f}</td></tr>
    <tr><td><b>1h Change</b></td><td style="color:#16a34a">+{change:.2f}%</td></tr>
    <tr style="background:#f0fdf4"><td><b>Liquidity</b></td><td>${liquidity:,.0f}</td></tr>
    <tr><td><b>24h Volume</b></td><td>${volume:,.0f}</td></tr>
    <tr style="background:#f0fdf4"><td><b>Token Address</b></td><td><code>{address}</code></td></tr>
    <tr><td><b>DexScreener</b></td><td><a href="{dex_url}">{dex_url}</a></td></tr>
    <tr style="background:#f0fdf4"><td><b>Detected (UTC)</b></td><td>{ts}</td></tr>
  </table>
  <p style="color:#6b7280;font-size:12px;margin-top:16px">
    Automated alert from memecoin-intel. Do your own research.
  </p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(user, password)
        smtp.sendmail(user, RECIPIENT, msg.as_string())

    log.info("Email sent to %s for token %s", RECIPIENT, token)


# ── Notion ────────────────────────────────────────────────────────────────────

def log_to_notion(signal: dict) -> None:
    token = os.environ["NOTION_TOKEN"]

    headers = {
        "Authorization":  f"Bearer {token}",
        "Content-Type":   "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    dex_url = signal.get("dex_url") or None

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Token": {
                "title": [{"text": {"content": signal.get("token", "UNKNOWN")}}]
            },
            "Signal": {
                "select": {"name": "buy now"}
            },
            "Chain": {
                "rich_text": [{"text": {"content": signal.get("chain", "")}}]
            },
            "Token Address": {
                "rich_text": [{"text": {"content": signal.get("token_address", "")}}]
            },
            "Price USD": {
                "number": signal.get("price_usd") or 0
            },
            "Price Change 1h %": {
                "number": signal.get("price_change_1h") or 0
            },
            "Liquidity USD": {
                "number": signal.get("liquidity_usd") or 0
            },
            "Volume 24h": {
                "number": signal.get("volume_24h") or 0
            },
            "DexScreener URL": {
                "url": dex_url
            },
        },
    }

    resp = requests.post(
        f"{NOTION_API_BASE}/pages",
        headers=headers,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    page_id = resp.json().get("id", "")
    log.info("Logged to Notion page %s for token %s", page_id, signal.get("token"))
