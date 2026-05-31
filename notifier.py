import smtplib
import requests
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_email(buy_signals: list[dict]) -> None:
    if not config.GMAIL_USER or not config.GMAIL_APP_PASSWORD:
        print("Warning: GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping email")
        return

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html_rows = "\n".join(
        f"<tr><td>{s['name']} ({s['symbol']})</td>"
        f"<td>${s['price']:.6f}</td>"
        f"<td style='color:green'>{s['change_24h']:+.1f}%</td>"
        f"<td>${s['volume_24h']:,.0f}</td></tr>"
        for s in buy_signals
    )
    body_html = f"""<html><body>
<h2 style="color:#16a34a">Memecoin Buy Now Signals</h2>
<p>Detected at <strong>{now_str}</strong></p>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-family:monospace">
  <tr style="background:#f3f4f6">
    <th>Token</th><th>Price</th><th>24h Change</th><th>Volume 24h</th>
  </tr>
  {html_rows}
</table>
<p style="color:#6b7280;font-size:12px">Sent by memecoin-intel · signals based on 24h momentum + volume ratio</p>
</body></html>"""

    plain_rows = "\n".join(
        f"  • {s['name']} ({s['symbol']}): ${s['price']:.6f}  |  24h: {s['change_24h']:+.1f}%  |  Vol: ${s['volume_24h']:,.0f}"
        for s in buy_signals
    )
    body_plain = f"BUY NOW signals at {now_str}:\n\n{plain_rows}\n"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[memecoin-intel] Buy Now — {len(buy_signals)} signal(s) detected"
    msg["From"] = config.GMAIL_USER
    msg["To"] = config.ALERT_EMAIL
    msg.attach(MIMEText(body_plain, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_USER, config.ALERT_EMAIL, msg.as_string())

    print(f"Email sent → {config.ALERT_EMAIL}  ({len(buy_signals)} Buy Now signal(s))")


def log_to_notion(buy_signals: list[dict]) -> None:
    if not config.NOTION_API_KEY:
        print("Warning: NOTION_API_KEY not set — skipping Notion logging")
        return

    headers = {
        "Authorization": f"Bearer {config.NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    for s in buy_signals:
        payload = {
            "parent": {"database_id": config.NOTION_DATABASE_ID},
            "properties": {
                "Token": {
                    "title": [{"text": {"content": f"{s['name']} ({s['symbol']})"}}]
                },
                "Signal": {"select": {"name": "Buy Now"}},
                "Price USD": {"number": s["price"]},
                "Price Change 24h %": {"number": round(s["change_24h"], 4)},
                "Volume 24h USD": {"number": s["volume_24h"]},
                "Timestamp": {"date": {"start": now_iso}},
                "Notes": {
                    "rich_text": [{"text": {"content": "Auto-logged by memecoin-intel"}}]
                },
            },
        }
        resp = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        print(f"Notion: logged {s['name']} Buy Now signal")
