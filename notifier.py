import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from notion_client import Client

from config import (
    ALERT_EMAIL,
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
)
from signals import Signal

logger = logging.getLogger(__name__)

DEXSCREENER_BASE = "https://dexscreener.com"


def send_email(signal: Signal) -> bool:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    dex_url = f"{DEXSCREENER_BASE}/{signal.chain}/{signal.address}"

    subject = f"BUY NOW Signal: {signal.coin} ({signal.confidence * 100:.0f}% confidence)"

    plain = f"""\
BUY NOW Signal Detected!

Coin:       {signal.coin}
Chain:      {signal.chain.capitalize()}
Price:      ${signal.price:.8f}
Confidence: {signal.confidence * 100:.0f}%
Notes:      {signal.notes}
Time:       {now_str}

Token: {signal.address}
Chart: {dex_url}

---
Memecoin Intel | Automated Alert
"""

    html = f"""\
<html>
<body style="font-family:sans-serif;max-width:560px;margin:auto">
  <h2 style="color:#e53e3e">&#128680; BUY NOW: {signal.coin}</h2>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:6px;font-weight:bold">Chain</td>
        <td style="padding:6px">{signal.chain.capitalize()}</td></tr>
    <tr style="background:#f7f7f7"><td style="padding:6px;font-weight:bold">Price</td>
        <td style="padding:6px">${signal.price:.8f}</td></tr>
    <tr><td style="padding:6px;font-weight:bold">Confidence</td>
        <td style="padding:6px">{signal.confidence * 100:.0f}%</td></tr>
    <tr style="background:#f7f7f7"><td style="padding:6px;font-weight:bold">Notes</td>
        <td style="padding:6px">{signal.notes}</td></tr>
    <tr><td style="padding:6px;font-weight:bold">Time</td>
        <td style="padding:6px">{now_str}</td></tr>
  </table>
  <br>
  <p style="word-break:break-all;font-size:12px;color:#666">
    Token: <code>{signal.address}</code>
  </p>
  <p>
    <a href="{dex_url}" style="background:#3182ce;color:#fff;padding:8px 16px;
       border-radius:4px;text-decoration:none">View on DexScreener</a>
  </p>
  <hr style="margin-top:32px">
  <p style="font-size:11px;color:#999">Memecoin Intel | Automated Alert</p>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, ALERT_EMAIL, msg.as_string())
        logger.info("Email sent for %s signal on %s", signal.signal_type, signal.coin)
        return True
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending email for %s: %s", signal.coin, e)
        return False


def log_to_notion(signal: Signal, email_sent: bool) -> bool:
    notion = Client(auth=NOTION_TOKEN)
    now = datetime.now(timezone.utc)

    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Signal": {
                    "title": [{"text": {"content": signal.signal_type.upper()}}]
                },
                "Coin": {
                    "rich_text": [{"text": {"content": signal.coin}}]
                },
                "Price": {"number": signal.price},
                "Confidence": {"number": signal.confidence},
                "Email Sent": {"checkbox": email_sent},
                "Notes": {
                    "rich_text": [{"text": {"content": signal.notes}}]
                },
                "Status": {"select": {"name": "New"}},
                "Timestamp": {
                    "date": {
                        "start": now.isoformat(),
                        "time_zone": "UTC",
                    }
                },
            },
        )
        logger.info("Logged %s signal for %s to Notion", signal.signal_type, signal.coin)
        return True
    except Exception as e:
        logger.error("Failed to log %s to Notion: %s", signal.coin, e)
        return False
