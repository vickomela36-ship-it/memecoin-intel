"""
Handles outbound notifications: Gmail (SMTP) and Notion API logging.
"""
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

from config import (
    GMAIL_SENDER, GMAIL_APP_PASSWORD, ALERT_EMAIL,
    NOTION_TOKEN, NOTION_DATABASE_ID,
)

_NOTION_API     = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


# ── Email ─────────────────────────────────────────────────────────────────────

def _build_email_html(signals):
    rows = "".join(
        f"""<tr>
          <td><b>{s['token']} ({s['symbol']})</b></td>
          <td>${s['price_usd']}</td>
          <td style="color:green">+{s['price_change_24h']:.1f}%</td>
          <td>${s['volume_24h_usd'] / 1e6:.2f}M</td>
          <td>${s['liquidity_usd'] / 1e3:.0f}k</td>
          <td>{s['buys_h1']}B / {s['sells_h1']}S</td>
          <td><a href="{s['dexscreener_url']}">Chart ↗</a></td>
        </tr>"""
        for s in signals
    )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<html><body style="font-family:Arial,sans-serif">
<h2 style="color:#1a1a2e">🚀 Memecoin Buy Signal{"s" if len(signals) > 1 else ""} — {ts}</h2>
<table border="1" cellpadding="8" style="border-collapse:collapse;font-size:13px">
  <tr style="background:#e8f5e9;font-weight:bold">
    <td>Token</td><td>Price</td><td>24h Δ</td>
    <td>Volume 24h</td><td>Liquidity</td><td>Txns (1h)</td><td>Link</td>
  </tr>
  {rows}
</table>
<p style="color:#888;font-size:11px;margin-top:16px">
  Criteria: &gt;15% 24h gain · &gt;$100k liquidity · &gt;$500k volume · buy pressure &gt; sell pressure
</p>
</body></html>"""


def send_buy_alert(signals):
    """Send one batched HTML email for all new signals. Returns True on success."""
    if not signals:
        return False

    count = len(signals)
    subject = f"🚀 {count} Memecoin Buy Signal{'s' if count > 1 else ''} Detected"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = ALERT_EMAIL
    msg.attach(MIMEText(_build_email_html(signals), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_SENDER, ALERT_EMAIL, msg.as_string())

    return True


# ── Notion ────────────────────────────────────────────────────────────────────

def _notion_headers():
    return {
        "Authorization":  f"Bearer {NOTION_TOKEN}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type":   "application/json",
    }


def log_to_notion(signal, email_sent=False):
    """Create one row in the Memecoin Buy Signals Notion database."""
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token Name":    {"title":     [{"text": {"content": signal["token"]}}]},
            "Symbol":        {"rich_text": [{"text": {"content": signal["symbol"]}}]},
            "Signal":        {"select":    {"name": "buy now"}},
            "Price USD":     {"rich_text": [{"text": {"content": str(signal["price_usd"])}}]},
            # Notion percent format stores fraction (divide % value by 100)
            "24h Change %":  {"number":    signal["price_change_24h"] / 100},
            "Volume 24h USD":{"number":    signal["volume_24h_usd"]},
            "Liquidity USD": {"number":    signal["liquidity_usd"]},
            "Vol/Liq Ratio": {"number":    signal["vol_liq_ratio"]},
            "DexScreener URL":{"url":      signal["dexscreener_url"]},
            "Pair Address":  {"rich_text": [{"text": {"content": signal["pair_address"]}}]},
            "Timestamp":     {"date":      {"start": signal["timestamp"]}},
            "Email Sent":    {"checkbox":  email_sent},
        },
    }
    resp = requests.post(
        f"{_NOTION_API}/pages",
        headers=_notion_headers(),
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["id"]
