"""
Sends email alerts (Gmail SMTP) and logs entries to Notion for every
'buy now' signal.
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

import config
from signals import Signal

logger = logging.getLogger(__name__)


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(signal: Signal) -> bool:
    """Send a buy-now alert to EMAIL_RECIPIENT via Gmail SMTP. Returns True on success."""
    if not config.EMAIL_SENDER or not config.EMAIL_APP_PASSWORD:
        logger.warning("Email not configured – set EMAIL_SENDER and EMAIL_APP_PASSWORD")
        return False

    subject = f"[Memecoin Alert] BUY NOW: {signal.coin} @ ${signal.price:.6g}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = f"""
    <html><body style="font-family:Arial,sans-serif;padding:20px">
      <h2 style="color:#d32f2f">&#128680; Memecoin Buy Signal</h2>
      <table border="1" cellpadding="10" cellspacing="0"
             style="border-collapse:collapse;min-width:360px">
        <tr><td><b>Coin</b></td>
            <td><b>{signal.coin}</b></td></tr>
        <tr><td><b>Signal</b></td>
            <td style="color:green;font-weight:bold">BUY NOW</td></tr>
        <tr><td><b>Price</b></td>
            <td>${signal.price:.8g}</td></tr>
        <tr><td><b>Confidence</b></td>
            <td>{signal.confidence * 100:.0f}%</td></tr>
        <tr><td><b>Notes</b></td>
            <td>{signal.notes}</td></tr>
        <tr><td><b>Time</b></td>
            <td>{timestamp}</td></tr>
      </table>
      <p style="color:#9e9e9e;font-size:11px;margin-top:16px">
        Automated alert from memecoin-intel. Not financial advice.
      </p>
    </body></html>
    """

    plain = (
        f"BUY NOW: {signal.coin}\n"
        f"Price:      ${signal.price:.8g}\n"
        f"Confidence: {signal.confidence * 100:.0f}%\n"
        f"Notes:      {signal.notes}\n"
        f"Time:       {timestamp}\n\n"
        "Automated alert. Not financial advice."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_SENDER
    msg["To"] = config.EMAIL_RECIPIENT
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(config.EMAIL_SENDER, config.EMAIL_APP_PASSWORD)
            smtp.sendmail(config.EMAIL_SENDER, config.EMAIL_RECIPIENT, msg.as_string())
        logger.info("Email sent for %s", signal.coin)
        return True
    except Exception as exc:
        logger.error("Failed to send email for %s: %s", signal.coin, exc)
        return False


# ── Notion ────────────────────────────────────────────────────────────────────

def log_to_notion(signal: Signal, email_sent: bool) -> bool:
    """Create a row in the Notion 'Memecoin Buy Signals Log' database."""
    if not config.NOTION_TOKEN:
        logger.warning("Notion not configured – set NOTION_TOKEN")
        return False

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    payload = {
        "parent": {"database_id": config.NOTION_DATABASE_ID},
        "properties": {
            "Signal": {
                "title": [{"text": {"content": "buy now"}}]
            },
            "Coin": {
                "rich_text": [{"text": {"content": signal.coin}}]
            },
            "Price": {"number": signal.price},
            "Confidence": {"number": signal.confidence},
            "Notes": {
                "rich_text": [{"text": {"content": signal.notes}}]
            },
            "Email Sent": {"checkbox": email_sent},
            "Status": {"select": {"name": "New"}},
            "Timestamp": {"date": {"start": now_iso}},
        },
    }

    headers = {
        "Authorization": f"Bearer {config.NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            "https://api.notion.com/v1/pages",
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Logged %s to Notion", signal.coin)
        return True
    except Exception as exc:
        logger.error("Failed to log %s to Notion: %s", signal.coin, exc)
        return False


# ── Combined notifier ─────────────────────────────────────────────────────────

def notify(signal: Signal) -> None:
    """Email + Notion log for a single buy-now signal."""
    email_sent = send_email(signal)
    log_to_notion(signal, email_sent)
