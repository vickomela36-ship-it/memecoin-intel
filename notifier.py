from __future__ import annotations
import smtplib
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_EMAIL, NOTION_TOKEN, NOTION_DB_ID
from signals import TokenSignal


def _signal_strength(score: float) -> str:
    if score >= 85:
        return "Strong"
    if score >= 75:
        return "Moderate"
    return "Weak"


def send_email(signals: list[TokenSignal]) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[notifier] Gmail credentials not configured — skipping email")
        return False

    tokens  = ", ".join(s.token for s in signals)
    subject = f"Buy Now: {tokens} — memecoin-intel"
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows      = ""
    plain_rows = ""
    for s in signals:
        rows += (
            f"<tr>"
            f"<td><b>{s.token}</b></td>"
            f"<td>${s.price:.6g}</td>"
            f"<td>{s.score:.0f}/100</td>"
            f"<td>{s.reason}</td>"
            f"</tr>"
        )
        plain_rows += f"  {s.token:<10} ${s.price:.6g:<14} score={s.score:.0f}  {s.reason}\n"

    html = f"""<html><body>
<h2>Memecoin Buy Now Signals</h2>
<table border="1" cellpadding="6" style="border-collapse:collapse">
  <tr><th>Token</th><th>Price</th><th>Score</th><th>Reason</th></tr>
  {rows}
</table>
<p style="color:gray;font-size:12px">Generated {now_utc} by memecoin-intel</p>
</body></html>"""

    plain = f"Memecoin Buy Now Signals — {now_utc}\n\n{plain_rows}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ALERT_EMAIL
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())
        print(f"[notifier] Email sent → {ALERT_EMAIL}")
        return True
    except Exception as e:
        print(f"[notifier] Email failed: {e}")
        return False


def log_to_notion(signal: TokenSignal, email_sent: bool) -> bool:
    if not NOTION_TOKEN:
        print("[notifier] NOTION_TOKEN not configured — skipping Notion log")
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    notes   = f"score={signal.score:.0f} | {signal.reason}"
    if email_sent:
        notes += " | email_sent=true"

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Signal Name":   {"title":     [{"text": {"content": "buy now"}}]},
            "Coin":          {"rich_text": [{"text": {"content": signal.token[:100]}}]},
            "Price (USD)":   {"number":    signal.price},
            "Price Change %":{"number":    signal.price_change_24h},
            "Signal Strength":{"select":   {"name": _signal_strength(signal.score)}},
            "Timestamp":     {"date":      {"start": now_iso}},
            "Volume 24h":    {"number":    signal.volume_24h},
            "Notes":         {"rich_text": [{"text": {"content": notes[:2000]}}]},
        },
    }

    try:
        r = requests.post(
            "https://api.notion.com/v1/pages",
            json=payload,
            headers={
                "Authorization":  f"Bearer {NOTION_TOKEN}",
                "Notion-Version": "2022-06-28",
            },
            timeout=15,
        )
        r.raise_for_status()
        print(f"[notifier] Logged {signal.token} to Notion")
        return True
    except Exception as e:
        print(f"[notifier] Notion log failed for {signal.token}: {e}")
        return False


def notify_buy_signals(signals: list[TokenSignal]) -> None:
    email_ok = send_email(signals)
    for s in signals:
        log_to_notion(s, email_ok)
