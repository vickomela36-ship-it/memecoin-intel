"""
Email (Gmail SMTP) and Notion REST API notifications for buy signals.
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import (
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER,
    NOTION_DATABASE_ID,
    NOTION_TOKEN,
    RECIPIENT_EMAIL,
)
from signals import Signal

logger = logging.getLogger(__name__)

NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _build_email_html(signals: list[Signal]) -> str:
    rows = ""
    for s in signals:
        rows += (
            f"<tr>"
            f"<td><b>{s.coin}</b></td>"
            f"<td style='color:green;font-weight:bold'>{s.signal.upper()}</td>"
            f"<td>${s.price:.8g}</td>"
            f"<td>{s.confidence:.0f}%</td>"
            f"<td>${s.volume_24h:,.0f}</td>"
            f"<td>{s.notes}</td>"
            f"</tr>"
        )
    return f"""
<html><body>
<h2 style="color:#e63946">🚀 Memecoin BUY NOW Alert</h2>
<p>The following signals were detected at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}:</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:monospace">
  <thead style="background:#f1f1f1">
    <tr><th>Coin</th><th>Signal</th><th>Price</th><th>Confidence</th><th>Vol 24h</th><th>Reason</th></tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
<p style="color:gray;font-size:12px">
  Data sourced from DexScreener. This is not financial advice.<br>
  Memecoin Intel – automated signal monitor
</p>
</body></html>
"""


def send_email(signals: list[Signal]) -> bool:
    """Send a buy-now alert email. Returns True on success."""
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        logger.error("Gmail credentials not set. Skipping email.")
        return False

    subject = f"[Memecoin Intel] BUY NOW signal – {len(signals)} coin(s) detected"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = RECIPIENT_EMAIL

    plain = "\n".join(
        f"{s.coin}: {s.signal.upper()} | ${s.price:.8g} | conf={s.confidence:.0f}% | {s.notes}"
        for s in signals
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_email_html(signals), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, RECIPIENT_EMAIL, msg.as_string())
        logger.info("Email sent to %s (%d signal(s))", RECIPIENT_EMAIL, len(signals))
        return True
    except Exception as exc:
        logger.error("Email failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------

def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def log_signal_to_notion(signal: Signal, email_sent: bool) -> bool:
    """Create a row in the Notion Buy Signals Log. Returns True on success."""
    if not NOTION_TOKEN:
        logger.error("NOTION_TOKEN not set. Skipping Notion log.")
        return False

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal": {
                "title": [{"text": {"content": signal.signal}}]
            },
            "Coin": {
                "rich_text": [{"text": {"content": signal.coin}}]
            },
            "Confidence": {"number": round(signal.confidence, 1)},
            "Price": {"number": round(signal.price, 10)},
            "Notes": {
                "rich_text": [{"text": {"content": signal.notes[:2000]}}]
            },
            "Status": {"select": {"name": "New"}},
            "Email Sent": {"checkbox": email_sent},
            "Timestamp": {"date": {"start": now_iso}},
        },
    }

    try:
        resp = requests.post(NOTION_PAGES_URL, json=payload, headers=_notion_headers(), timeout=15)
        resp.raise_for_status()
        logger.info("Notion: logged %s signal for %s", signal.signal, signal.coin)
        return True
    except Exception as exc:
        logger.error("Notion log failed for %s: %s", signal.coin, exc)
        return False
