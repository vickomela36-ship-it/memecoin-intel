"""Standalone notifier — uses Gmail SMTP and Notion REST API directly.
Requires GMAIL_USER, GMAIL_APP_PASSWORD, and NOTION_TOKEN in .env.
"""
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import (
    EMAIL_RECIPIENT, SMTP_SERVER, SMTP_PORT, GMAIL_USER, GMAIL_APP_PASSWORD,
    NOTION_TOKEN, NOTION_DATABASE_ID,
)

_NOTION_API = "https://api.notion.com/v1/pages"
_NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def send_email(signal: dict) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[notifier] Gmail credentials missing — skipping email")
        return False

    token = signal["token"]
    price = signal["price_usd"]
    subject = f"BUY NOW: {token} @ ${price:.8f} | Score {signal['score']}/100"

    html = f"""
<h2 style="color:#d32f2f">&#128680; Memecoin Buy Signal</h2>
<table cellpadding="6" style="border-collapse:collapse;font-family:monospace">
  <tr><td><b>Token</b></td><td>{token} ({signal['token_name']})</td></tr>
  <tr><td><b>Signal</b></td><td style="color:#d32f2f"><b>BUY NOW</b></td></tr>
  <tr><td><b>Price</b></td><td>${price:.8f}</td></tr>
  <tr><td><b>1h Change</b></td><td>+{signal['price_change_1h']:.2f}%</td></tr>
  <tr><td><b>1h Volume</b></td><td>${signal['volume_1h']:,.0f}</td></tr>
  <tr><td><b>Liquidity</b></td><td>${signal['liquidity_usd']:,.0f}</td></tr>
  <tr><td><b>Score</b></td><td>{signal['score']}/100</td></tr>
  <tr><td><b>Reason</b></td><td>{signal['reason']}</td></tr>
  <tr><td><b>Time (UTC)</b></td><td>{signal['timestamp']}</td></tr>
  <tr><td><b>Chart</b></td><td><a href="{signal['dex_url']}">DEX Screener &#8599;</a></td></tr>
</table>
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as srv:
            srv.starttls()
            srv.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            srv.sendmail(GMAIL_USER, EMAIL_RECIPIENT, msg.as_string())
        print(f"[notifier] email sent → {EMAIL_RECIPIENT} [{token}]")
        return True
    except Exception as e:
        print(f"[notifier] email error: {e}")
        return False


def log_to_notion(signal: dict, email_sent: bool = False) -> bool:
    if not NOTION_TOKEN:
        print("[notifier] NOTION_TOKEN missing — skipping Notion log")
        return False

    token = signal["token"]
    title = f"BUY NOW — {token} @ ${signal['price_usd']:.8f}"
    ts    = signal["timestamp"].replace("+00:00", "Z")

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Signal":     {"title":      [{"text": {"content": title}}]},
            "Token":      {"rich_text":  [{"text": {"content": token}}]},
            "Price":      {"number":     signal["price_usd"]},
            "Score":      {"number":     signal["score"]},
            "Timestamp":  {"date":       {"start": ts, "time_zone": "UTC"}},
            "Email Sent": {"checkbox":   email_sent},
            "Reason":     {"rich_text":  [{"text": {"content": signal["reason"]}}]},
        },
    }

    try:
        resp = requests.post(_NOTION_API, headers=_NOTION_HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[notifier] logged to Notion [{token}]")
        return True
    except Exception as e:
        print(f"[notifier] Notion error: {e}")
        return False
