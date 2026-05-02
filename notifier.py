"""
Sends 'buy now' alerts:
  - Email via Gmail SMTP (requires GMAIL_USER + GMAIL_APP_PASSWORD in .env)
  - Row in Notion database (requires NOTION_TOKEN in .env)
"""

import smtplib
import logging
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_EMAIL,
    NOTION_TOKEN, NOTION_DATA_SOURCE_ID,
)

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VER = "2022-06-28"


# ── Email ─────────────────────────────────────────────────────────────────────

def _build_email(signals):
    lines = ["MEMECOIN BUY NOW ALERT\n"]
    rows  = []
    for s in signals:
        lines.append(f"  {s.token}  |  ${s.price:.6f}  |  score={s.score:.0f}  |  {s.reason}")
        rows.append(
            f"<tr><td><b>{s.token}</b></td><td>${s.price:.6f}</td>"
            f"<td>{s.score:.0f}</td><td>{s.reason}</td></tr>"
        )
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    html = f"""<html><body>
<h2>Memecoin — Buy Now Alert</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:monospace">
  <tr style="background:#f0f0f0"><th>Token</th><th>Price</th><th>Score</th><th>Reason</th></tr>
  {''.join(rows)}
</table>
<p style="color:#888;font-size:12px">
  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · memecoin-intel
</p></body></html>"""
    return "\n".join(lines), html


def send_email(signals) -> bool:
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
        log.info("Email sent → %s for %s", ALERT_EMAIL, tokens)
        return True
    except Exception as exc:
        log.error("Email failed: %s", exc)
        return False


# ── Notion ────────────────────────────────────────────────────────────────────

def log_to_notion(signal, email_sent: bool) -> bool:
    if not NOTION_TOKEN:
        log.warning("NOTION_TOKEN not configured — skipping Notion log")
        return False
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "parent": {"database_id": NOTION_DATA_SOURCE_ID},
        "properties": {
            "Signal":     {"title":     [{"text": {"content": "buy now"}}]},
            "Coin":       {"rich_text": [{"text": {"content": signal.token}}]},
            "Price":      {"number": signal.price},
            "Confidence": {"number": signal.score},
            "Timestamp":  {"date": {"start": now_iso}},
            "Notes":      {"rich_text": [{"text": {"content": signal.reason[:2000]}}]},
            "Email Sent": {"checkbox": email_sent},
            "Status":     {"select": {"name": "New"}},
        },
    }
    try:
        resp = requests.post(
            f"{NOTION_API}/pages",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Notion-Version": NOTION_VER,
                "Content-Type": "application/json",
            },
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
    if not buy_signals:
        return
    email_ok = send_email(buy_signals)
    for sig in buy_signals:
        log_to_notion(sig, email_sent=email_ok)
