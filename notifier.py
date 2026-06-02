import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
import requests
from config import (
    RECIPIENT_EMAIL,
    SENDER_EMAIL,
    GMAIL_APP_PASSWORD,
    NOTION_API_KEY,
    NOTION_DATABASE_ID,
)


def send_email(buy_now_signals: list[dict]) -> None:
    if not buy_now_signals:
        return

    today = date.today().isoformat()
    subject = f"[Memecoin Intel] BUY NOW Signal — {today}"

    rows = "".join(
        f"""
        <tr>
          <td><b>{s['token_name']}</b></td>
          <td>{s['chain']}</td>
          <td>${s['price_usd']:.8f}</td>
          <td style="color:{'#16a34a' if s['price_change_24h'] >= 0 else '#dc2626'}">
            {s['price_change_24h']:+.2f}%
          </td>
          <td>${s['volume_24h']:,.0f}</td>
          <td>${s['market_cap']:,.0f}</td>
          <td><a href="{s['dexscreener_url']}">Chart</a></td>
        </tr>"""
        for s in buy_now_signals
    )

    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#111">
    <h2 style="color:#16a34a">Memecoin Intel — BUY NOW Signals</h2>
    <p><b>Date:</b> {today}</p>
    <p>{len(buy_now_signals)} token(s) triggered a <b style="color:#16a34a">BUY NOW</b> signal.</p>
    <table border="1" cellpadding="8" cellspacing="0"
           style="border-collapse:collapse;font-size:13px;min-width:600px">
      <thead style="background:#f0fdf4">
        <tr>
          <th>Token</th><th>Chain</th><th>Price</th><th>24h Change</th>
          <th>24h Volume</th><th>Market Cap</th><th>Chart</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <br>
    <p style="color:#6b7280;font-size:11px">
      Automated signal from Memecoin Intel. Not financial advice.
    </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

    print(f"Email sent to {RECIPIENT_EMAIL} ({len(buy_now_signals)} signal(s)).")


def log_to_notion(signal: dict) -> None:
    today = date.today().isoformat()

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Token": {"title": [{"text": {"content": signal["token_name"]}}]},
            "Signal Date": {"date": {"start": today}},
            "Signal": {"select": {"name": "Buy Now"}},
            "Price USD": {"number": signal["price_usd"]},
            "Price Change 24h %": {"number": signal["price_change_24h"]},
            "Volume 24h USD": {"number": signal["volume_24h"]},
            "Market Cap USD": {"number": signal["market_cap"]},
            "Chain": {"select": {"name": signal["chain"]}},
        },
    }

    if signal.get("dexscreener_url"):
        payload["properties"]["DexScreener URL"] = {"url": signal["dexscreener_url"]}

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages", json=payload, headers=headers, timeout=15
    )
    if resp.ok:
        print(f"Logged {signal['token_name']} to Notion.")
    else:
        print(f"[WARN] Notion log failed for {signal['token_name']}: {resp.status_code} {resp.text}")
