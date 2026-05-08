import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from notion_client import Client

import config
from signals import Signal


# ── Email ─────────────────────────────────────────────────────────────────────

def _build_email(signal: Signal) -> MIMEMultipart:
    subject = f"BUY NOW Signal: {signal.token_name} [{signal.signal_strength}]"
    html = f"""\
<html><body>
<h2 style="color:#16a34a">&#x1F680; Buy Now Signal: {signal.token_name}</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:monospace">
  <tr><td><b>Chain</b></td><td>{signal.chain}</td></tr>
  <tr><td><b>Strength</b></td><td>{signal.signal_strength}</td></tr>
  <tr><td><b>Price (USD)</b></td><td>${signal.price_usd:.8f}</td></tr>
  <tr><td><b>24h Change</b></td><td>{signal.price_change_24h:+.2f}%</td></tr>
  <tr><td><b>24h Volume</b></td><td>${signal.volume_24h:,.0f}</td></tr>
  <tr><td><b>Timestamp (UTC)</b></td><td>{signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
  <tr><td><b>Token Address</b></td><td>{signal.token_address}</td></tr>
  <tr><td><b>Notes</b></td><td>{signal.notes}</td></tr>
</table>
<p style="color:#6b7280;font-size:0.85em">Automated alert from Memecoin Intel &mdash; DYOR before trading.</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_SENDER
    msg["To"] = config.ALERT_EMAIL
    msg.attach(MIMEText(html, "html"))
    return msg


def send_email(signal: Signal) -> None:
    msg = _build_email(signal)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_SENDER, config.ALERT_EMAIL, msg.as_string())
    print(f"[notifier] Email sent → {signal.token_name}")


# ── Notion ────────────────────────────────────────────────────────────────────

def log_to_notion(signal: Signal) -> None:
    notion = Client(auth=config.NOTION_TOKEN)
    ts = signal.timestamp.strftime("%Y-%m-%dT%H:%M:%S")

    notion.pages.create(
        parent={"database_id": config.NOTION_DATABASE_ID},
        properties={
            "Signal Name": {
                "title": [{"text": {"content": f"BUY NOW – {signal.token_name}"}}]
            },
            "Coin": {
                "rich_text": [{"text": {"content": signal.token_name}}]
            },
            "Price (USD)": {"number": signal.price_usd},
            "Price Change %": {"number": signal.price_change_24h},
            "Volume 24h": {"number": signal.volume_24h},
            "Signal Strength": {"select": {"name": signal.signal_strength}},
            "Timestamp": {"date": {"start": ts}},
            "Notes": {
                "rich_text": [{"text": {"content": signal.notes[:2000]}}]
            },
        },
    )
    print(f"[notifier] Notion logged → {signal.token_name}")


# ── Dispatch ──────────────────────────────────────────────────────────────────

def process_signal(signal: Signal) -> None:
    try:
        send_email(signal)
    except Exception as exc:
        print(f"[notifier] Email error for {signal.token_name}: {exc}")

    try:
        log_to_notion(signal)
    except Exception as exc:
        print(f"[notifier] Notion error for {signal.token_name}: {exc}")
