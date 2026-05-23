"""
Handles 'buy now' notifications:
  - Sends email via Gmail SMTP
  - Logs the signal to the Notion 'Memecoin Buy Now Signals' database
"""

import smtplib
import logging
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_EMAIL,
    NOTION_TOKEN, NOTION_DB_ID,
)

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VER = "2022-06-28"


# ── Email ─────────────────────────────────────────────────────────────────────

def _build_email(signals) -> tuple[str, str]:
    """Returns (plain_text, html) for a list of TokenSignal objects."""
    plain_lines = ["MEMECOIN BUY NOW ALERT\n"]
    html_rows   = []

    for s in signals:
        plain_lines.append(
            f"  {s.token}  |  ${s.price:.6f}  |  score={s.score:.0f}  |  {s.reason}"
        )
        html_rows.append(
            f"<tr><td><b>{s.token}</b></td><td>${s.price:.6f}</td>"
            f"<td>{s.score:.0f}</td><td>{s.reason}</td></tr>"
        )

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    plain_lines.append(f"\nGenerated: {ts}")

    html = f"""<html><body>
<h2>Memecoin — Buy Now Alert</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:monospace">
  <tr style="background:#f0f0f0">
    <th>Token</th><th>Price</th><th>Score</th><th>Reason</th>
  </tr>
  {''.join(html_rows)}
</table>
<p style="color:#888;font-size:12px">Generated {ts} · memecoin-intel</p>
</body></html>"""

    return "\n".join(plain_lines), html


def send_email(signals) -> bool:
    """Send a batched buy-now alert email. Returns True on success."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        log.warning("Gmail credentials not configured — skipping email")
        return False

    plain, html = _build_email(signals)
    tokens = ", ".join(s.token for s in signals)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Buy Now: {tokens} — memecoin-intel"
    msg["From"]    = GMAIL_USER
    msg["To"]      = ALERT_EMAIL
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())
        log.info("Email sent to %s (%d signal(s))", ALERT_EMAIL, len(signals))
        return True
    except Exception as exc:
        log.error("Email failed: %s", exc)
        return False


# ── Notion ────────────────────────────────────────────────────────────────────

def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VER,
        "Content-Type": "application/json",
    }


def log_to_notion(signal, email_sent: bool) -> bool:
    """Create a row in the Notion buy-signal log. Returns True on success."""
    if not NOTION_TOKEN:
        log.warning("NOTION_TOKEN not configured — skipping Notion log")
        return False

    now_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Signal":     {"title":     [{"text": {"content": "buy now"}}]},
            "Token":      {"rich_text": [{"text": {"content": signal.token}}]},
            "Price":      {"number":    signal.price},
            "Score":      {"number":    signal.score},
            "Timestamp":  {"date":      {"start": now_iso}},
            "Reason":     {"rich_text": [{"text": {"content": signal.reason[:2000]}}]},
            "Email Sent": {"checkbox":  email_sent},
        },
    }

    try:
        resp = requests.post(
            f"{NOTION_API}/pages",
            headers=_notion_headers(),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        log.info("Logged %s to Notion", signal.token)
        return True
    except Exception as exc:
        log.error("Notion log failed for %s: %s", signal.token, exc)
        return False


# ── Orchestrator ──────────────────────────────────────────────────────────────

def notify_buy_signals(buy_signals) -> None:
    """Send one batched email + one Notion row per signal."""
    if not buy_signals:
        return

    email_ok = send_email(buy_signals)

    for sig in buy_signals:
        log_to_notion(sig, email_sent=email_ok)
