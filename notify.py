"""
Notification helpers: Gmail SMTP email alert + Notion API row insertion.
"""
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    GMAIL_USER,
    GMAIL_APP_PASSWORD,
    ALERT_EMAIL,
    NOTION_TOKEN,
    NOTION_DATABASE_ID,
)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def send_buy_alert(signal: dict) -> None:
    """Send an HTML email to ALERT_EMAIL via Gmail SMTP (App Password auth)."""
    h1  = signal["h1_change"]
    h6  = signal["h6_change"]
    h24 = signal["h24_change"]
    sym = signal["symbol"]

    subject = f"BUY NOW: {sym}  |  {h1:+.1f}% (1h)"

    html = f"""\
<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;color:#1a1a1a">
  <div style="background:#00c853;padding:20px 24px;border-radius:8px 8px 0 0">
    <h2 style="margin:0;color:#fff">&#x1F680; Buy Now Signal</h2>
    <p style="margin:4px 0 0;color:#e8f5e9;font-size:18px">
      {signal["token_name"]} <span style="opacity:.8">({sym})</span>
    </p>
  </div>
  <div style="border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;padding:20px 24px">
    <table style="width:100%;border-collapse:collapse;font-size:15px">
      <tr style="background:#f5f5f5">
        <td style="padding:10px 12px;font-weight:bold">Price</td>
        <td style="padding:10px 12px">${signal["price_usd"]}</td>
      </tr>
      <tr>
        <td style="padding:10px 12px;font-weight:bold">1h Change</td>
        <td style="padding:10px 12px;color:#00c853;font-weight:bold">{h1:+.2f}%</td>
      </tr>
      <tr style="background:#f5f5f5">
        <td style="padding:10px 12px;font-weight:bold">6h Change</td>
        <td style="padding:10px 12px">{h6:+.2f}%</td>
      </tr>
      <tr>
        <td style="padding:10px 12px;font-weight:bold">24h Change</td>
        <td style="padding:10px 12px">{h24:+.2f}%</td>
      </tr>
      <tr style="background:#f5f5f5">
        <td style="padding:10px 12px;font-weight:bold">24h Volume</td>
        <td style="padding:10px 12px">${signal["volume_24h"]:,.0f}</td>
      </tr>
      <tr>
        <td style="padding:10px 12px;font-weight:bold">Liquidity</td>
        <td style="padding:10px 12px">${signal["liquidity"]:,.0f}</td>
      </tr>
      <tr style="background:#f5f5f5">
        <td style="padding:10px 12px;font-weight:bold">Buy Pressure</td>
        <td style="padding:10px 12px">{signal["buy_pressure"]}%</td>
      </tr>
    </table>
    <br>
    <a href="{signal["dexscreener_url"]}"
       style="background:#6200ea;color:#fff;padding:12px 28px;border-radius:6px;
              text-decoration:none;font-weight:bold;display:inline-block">
      View on DexScreener &#x2192;
    </a>
    <p style="margin-top:20px;color:#9e9e9e;font-size:12px">
      Signal generated at {signal["checked_at"]} UTC &nbsp;|&nbsp; memecoin-intel
    </p>
  </div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())

    print(f"[notify] Email sent → {ALERT_EMAIL}  ({sym})")


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------

_NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
_NOTION_VERSION   = "2022-06-28"


def _notion_headers() -> dict:
    return {
        "Authorization":  f"Bearer {NOTION_TOKEN}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type":   "application/json",
    }


def log_to_notion(signal: dict) -> None:
    """Insert a new row into the Memecoin Buy Signals Notion database."""
    dex_url = signal["dexscreener_url"] or None

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token": {
                "title": [{"text": {"content": signal["token_name"]}}]
            },
            "Symbol": {
                "rich_text": [{"text": {"content": signal["symbol"]}}]
            },
            "Signal": {
                "select": {"name": "buy now"}
            },
            "Price USD": {
                "rich_text": [{"text": {"content": str(signal["price_usd"])}}]
            },
            "1h Change %": {
                "rich_text": [{"text": {"content": f"{signal['h1_change']:+.2f}%"}}]
            },
            "6h Change %": {
                "rich_text": [{"text": {"content": f"{signal['h6_change']:+.2f}%"}}]
            },
            "24h Change %": {
                "rich_text": [{"text": {"content": f"{signal['h24_change']:+.2f}%"}}]
            },
            "Volume 24h USD": {
                "rich_text": [{"text": {"content": f"${signal['volume_24h']:,.0f}"}}]
            },
            "Liquidity USD": {
                "rich_text": [{"text": {"content": f"${signal['liquidity']:,.0f}"}}]
            },
            "Buy Pressure": {
                "rich_text": [{"text": {"content": f"{signal['buy_pressure']}%"}}]
            },
            "Checked At": {
                "date": {"start": signal["checked_at"]}
            },
            "DexScreener URL": {
                "url": dex_url
            },
        },
    }

    resp = requests.post(_NOTION_PAGES_URL, headers=_notion_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    print(f"[notify] Notion row created  ({signal['symbol']})")
