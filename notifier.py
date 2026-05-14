"""Handles Gmail alerts and Notion logging for buy-now signals."""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

import config

_NOTION_API = "https://api.notion.com/v1/pages"
_NOTION_HEADERS = {
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# ── Email ──────────────────────────────────────────────────────────────────────

def _build_email_html(sig: dict) -> str:
    return f"""
<html><body>
<h2 style="color:#16a34a">🚀 Buy Now Signal: {sig['coin_symbol']}</h2>
<table cellpadding="6" style="border-collapse:collapse;font-family:sans-serif">
  <tr><td><b>Chain</b></td><td>{sig['chain']}</td></tr>
  <tr><td><b>DEX</b></td><td>{sig['dex']}</td></tr>
  <tr><td><b>Price</b></td><td>${sig['price_usd']:.8f}</td></tr>
  <tr><td><b>24h Change</b></td><td>{sig['price_change_24h']:+.2f}%</td></tr>
  <tr><td><b>Liquidity</b></td><td>${sig['liquidity_usd']:,.2f}</td></tr>
  <tr><td><b>24h Volume</b></td><td>${sig['volume_24h_usd']:,.2f}</td></tr>
  <tr><td><b>Pair</b></td><td><code>{sig['pair_address']}</code></td></tr>
</table>
<p style="color:#6b7280;font-size:12px">Memecoin Intel · {date.today()}</p>
</body></html>
"""


def send_email(sig: dict) -> bool:
    if not config.GMAIL_APP_PASSWORD:
        logging.warning("GMAIL_APP_PASSWORD not set — skipping email")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚀 Buy Now Signal: {sig['coin_symbol']} ({sig['price_change_24h']:+.1f}% 24h)"
    msg["From"] = config.GMAIL_SENDER
    msg["To"] = config.GMAIL_RECIPIENT
    msg.attach(MIMEText(_build_email_html(sig), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
            smtp.sendmail(config.GMAIL_SENDER, config.GMAIL_RECIPIENT, msg.as_string())
        logging.info("Email sent for %s", sig["coin_symbol"])
        return True
    except Exception:
        logging.exception("Failed to send email for %s", sig["coin_symbol"])
        return False


# ── Notion ─────────────────────────────────────────────────────────────────────

def log_to_notion(sig: dict, email_sent: bool) -> bool:
    if not config.NOTION_TOKEN:
        logging.warning("NOTION_TOKEN not set — skipping Notion log")
        return False

    today = date.today().isoformat()
    title = f"{sig['coin_symbol']} – Buy Now – {today}"

    payload = {
        "parent": {"database_id": config.NOTION_DATABASE_ID},
        "properties": {
            "Signal Name": {"title": [{"text": {"content": title}}]},
            "Signal": {"select": {"name": "Buy Now"}},
            "Coin Symbol": {"rich_text": [{"text": {"content": sig["coin_symbol"]}}]},
            "Chain": {"rich_text": [{"text": {"content": sig["chain"]}}]},
            "DEX": {"rich_text": [{"text": {"content": sig["dex"]}}]},
            "Pair Address": {"rich_text": [{"text": {"content": sig["pair_address"]}}]},
            "Price USD": {"number": sig["price_usd"]},
            "Price Change 24h %": {"number": sig["price_change_24h"]},
            "Liquidity USD": {"number": sig["liquidity_usd"]},
            "Volume 24h USD": {"number": sig["volume_24h_usd"]},
            "Date": {"date": {"start": today}},
            "Email Sent": {"checkbox": email_sent},
        },
    }

    headers = {**_NOTION_HEADERS, "Authorization": f"Bearer {config.NOTION_TOKEN}"}

    try:
        resp = requests.post(_NOTION_API, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        logging.info("Logged to Notion: %s", title)
        return True
    except Exception:
        logging.exception("Failed to log to Notion for %s", sig["coin_symbol"])
        return False
