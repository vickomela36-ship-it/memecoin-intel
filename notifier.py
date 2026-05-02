"""
Handles two side-effects for every "buy now" signal:
  1. Send an alert email via Gmail SMTP.
  2. Log the signal as a new row in the Notion "Memecoin Buy Now Signals" DB.
"""

from __future__ import annotations
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import (
    ALERT_EMAIL,
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)

logger = logging.getLogger(__name__)

NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _build_email(token: str, price: float, score: float, reason: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Memecoin Intel] BUY NOW signal — {token}"
    msg["From"] = GMAIL_SENDER
    msg["To"] = ALERT_EMAIL

    plain = (
        f"BUY NOW signal detected!\n\n"
        f"Token  : {token}\n"
        f"Price  : ${price:,.6f}\n"
        f"Score  : {score:.1f} / 10\n"
        f"Reason : {reason}\n"
        f"Time   : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
    )
    html = f"""
    <html><body style="font-family:sans-serif;color:#222">
      <h2 style="color:#16a34a">BUY NOW — {token}</h2>
      <table cellpadding="6">
        <tr><td><b>Price</b></td><td>${price:,.6f}</td></tr>
        <tr><td><b>Score</b></td><td>{score:.1f} / 10</td></tr>
        <tr><td><b>Reason</b></td><td>{reason}</td></tr>
        <tr><td><b>Time</b></td><td>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</td></tr>
      </table>
    </body></html>
    """
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_email(token: str, price: float, score: float, reason: str) -> bool:
    """Send a buy-alert email. Returns True on success."""
    try:
        msg = _build_email(token, price, score, reason)
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, ALERT_EMAIL, msg.as_string())
        logger.info("Email sent for %s", token)
        return True
    except Exception as exc:
        logger.error("Failed to send email for %s: %s", token, exc)
        return False


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------

def log_to_notion(
    token: str,
    price: float,
    score: float,
    reason: str,
    signal: str,
    timestamp: datetime,
    email_sent: bool,
) -> bool:
    """Create a new row in the Memecoin Buy Now Signals database. Returns True on success."""
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal": {
                "title": [{"text": {"content": signal}}]
            },
            "Token": {
                "rich_text": [{"text": {"content": token}}]
            },
            "Price": {
                "number": price
            },
            "Score": {
                "number": score
            },
            "Reason": {
                "rich_text": [{"text": {"content": reason}}]
            },
            "Timestamp": {
                "date": {
                    "start": timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                }
            },
            "Email Sent": {
                "checkbox": email_sent
            },
        },
    }
    try:
        resp = requests.post(NOTION_PAGES_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("Notion row created for %s (signal=%s)", token, signal)
        return True
    except Exception as exc:
        logger.error("Failed to log to Notion for %s: %s", token, exc)
        return False
