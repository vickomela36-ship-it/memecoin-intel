"""Email and Notion logging helpers."""
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

import config


def send_email(subject, body_html, body_text):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_SENDER
    msg["To"] = config.GMAIL_RECIPIENT
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
        smtp.sendmail(config.GMAIL_SENDER, config.GMAIL_RECIPIENT, msg.as_string())


def log_to_notion(signal):
    dt_str = signal.get("detected_at", datetime.now(timezone.utc).isoformat())
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    iso = dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    payload = {
        "parent": {"database_id": config.NOTION_DB_ID},
        "properties": {
            "Coin": {"title": [{"text": {"content": signal["coin"]}}]},
            "Signal": {"select": {"name": signal["signal"]}},
            "Price USD": {"number": signal.get("price_usd") or 0},
            "Price Change 24h %": {"number": signal.get("price_change_24h") or 0},
            "Volume 24h USD": {"number": signal.get("volume_24h_usd") or 0},
            "Market Cap USD": {"number": signal.get("market_cap_usd") or 0},
            "Source": {
                "rich_text": [{"text": {"content": signal.get("source", "DexScreener")}}]
            },
            "Detected At": {"date": {"start": iso}},
            "Notes": {
                "rich_text": [{"text": {"content": signal.get("pair_url", "")}}]
            },
        },
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {config.NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def build_email_content(buy_now_signals):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    count = len(buy_now_signals)

    rows_html = ""
    rows_text = ""
    for s in buy_now_signals:
        color = "green" if s["price_change_24h"] >= 0 else "red"
        rows_html += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold">{s['coin']}</td>
          <td style="padding:8px;border:1px solid #ddd">${s['price_usd']:.8g}</td>
          <td style="padding:8px;border:1px solid #ddd;color:{color}">{s['price_change_24h']:+.1f}%</td>
          <td style="padding:8px;border:1px solid #ddd">${s['volume_24h_usd']:,.0f}</td>
          <td style="padding:8px;border:1px solid #ddd">${s['market_cap_usd']:,.0f}</td>
          <td style="padding:8px;border:1px solid #ddd"><a href="{s['pair_url']}">Chart</a></td>
        </tr>"""
        rows_text += (
            f"  • {s['coin']}: ${s['price_usd']:.8g}"
            f" | {s['price_change_24h']:+.1f}% 24h"
            f" | Vol: ${s['volume_24h_usd']:,.0f}"
            f" | MCap: ${s['market_cap_usd']:,.0f}\n"
            f"    {s['pair_url']}\n\n"
        )

    subject = f"BUY NOW: {count} Memecoin Signal{'s' if count != 1 else ''} — {now_str}"

    body_html = f"""<html><body style="font-family:sans-serif;max-width:720px;margin:auto">
  <h2 style="color:#1a1a2e">Memecoin Buy Now Alert</h2>
  <p><b>{count}</b> token{'s' if count != 1 else ''} triggered a
     <span style="color:green;font-weight:bold">BUY NOW</span> signal at {now_str}.</p>
  <table style="width:100%;border-collapse:collapse;margin-top:16px">
    <thead>
      <tr style="background:#1a1a2e;color:#fff">
        <th style="padding:8px">Coin</th>
        <th style="padding:8px">Price</th>
        <th style="padding:8px">24h</th>
        <th style="padding:8px">Volume 24h</th>
        <th style="padding:8px">Market Cap</th>
        <th style="padding:8px">Chart</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  <p style="margin-top:24px;color:#888;font-size:12px">
    Automated signal from memecoin-intel · Always DYOR · Crypto trading carries significant risk.
  </p>
</body></html>"""

    body_text = (
        f"MEMECOIN BUY NOW ALERT\n{'=' * 40}\n"
        f"{count} token(s) flagged at {now_str}\n\n"
        + rows_text
        + "---\nAutomated from memecoin-intel. Always DYOR."
    )

    return subject, body_html, body_text
