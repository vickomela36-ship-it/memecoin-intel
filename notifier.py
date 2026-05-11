"""
Gmail email notifications for 'buy now' signals.

Required env vars:
  GMAIL_SENDER_EMAIL   – the Gmail address used to send (must have an App Password)
  GMAIL_APP_PASSWORD   – 16-char App Password from myaccount.google.com/apppasswords
  ALERT_RECIPIENT      – override destination (default: vickomela36@gmail.com)
"""

import os
import smtplib
import html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone


RECIPIENT = os.getenv("ALERT_RECIPIENT", "vickomela36@gmail.com")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def _build_html(signals: list[dict]) -> str:
    rows = ""
    for s in signals:
        price = f"${s['price_usd']:,.8f}" if s.get("price_usd") else "N/A"
        rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:bold;">{html.escape(s['coin_symbol'])}</td>
          <td style="padding:8px 12px;">{html.escape(s['coin_name'])}</td>
          <td style="padding:8px 12px;color:#16a34a;font-weight:bold;">+{s['price_change_24h']:.1f}%</td>
          <td style="padding:8px 12px;">{price}</td>
          <td style="padding:8px 12px;">${s['volume_24h_usd']:,.0f}</td>
          <td style="padding:8px 12px;">${s['liquidity_usd']:,.0f}</td>
          <td style="padding:8px 12px;">{html.escape(s['chain'].upper())}</td>
          <td style="padding:8px 12px;">{html.escape(s['dex'])}</td>
        </tr>"""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;">
  <h2 style="color:#16a34a;">🚨 Memecoin Buy Now Signal Alert</h2>
  <p style="color:#6b7280;">{timestamp} — {len(signals)} buy signal(s) detected</p>
  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    <thead>
      <tr style="background:#f3f4f6;">
        <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;">Symbol</th>
        <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;">Name</th>
        <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;">24h Change</th>
        <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;">Price</th>
        <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;">Volume 24h</th>
        <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;">Liquidity</th>
        <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;">Chain</th>
        <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;">DEX</th>
      </tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
  <p style="margin-top:24px;font-size:12px;color:#9ca3af;">
    This is an automated alert from memecoin-intel. Not financial advice.
  </p>
</body>
</html>"""


def _build_plain(signals: list[dict]) -> str:
    lines = [
        "MEMECOIN BUY NOW SIGNAL ALERT",
        "=" * 40,
        f"Detected {len(signals)} buy signal(s)",
        "",
    ]
    for s in signals:
        price = f"${s['price_usd']:,.8f}" if s.get("price_usd") else "N/A"
        lines += [
            f"  {s['coin_symbol']} ({s['coin_name']})",
            f"    Price:     {price}",
            f"    24h chg:   +{s['price_change_24h']:.1f}%",
            f"    Volume 24h: ${s['volume_24h_usd']:,.0f}",
            f"    Liquidity:  ${s['liquidity_usd']:,.0f}",
            f"    Chain: {s['chain'].upper()}  DEX: {s['dex']}",
            f"    Pair: {s['pair_address']}",
            "",
        ]
    lines.append("Not financial advice.")
    return "\n".join(lines)


def send_buy_now_alert(signals: list[dict]) -> bool:
    """Send an HTML+plain email listing all buy-now signals. Returns True on success."""
    sender = os.environ["GMAIL_SENDER_EMAIL"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    count = len(signals)
    subject = f"🚨 Memecoin Buy Now: {count} signal{'s' if count != 1 else ''} detected"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = RECIPIENT

    msg.attach(MIMEText(_build_plain(signals), "plain"))
    msg.attach(MIMEText(_build_html(signals), "html"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(sender, app_password)
            server.sendmail(sender, RECIPIENT, msg.as_string())
        print(f"[notifier] Email sent to {RECIPIENT} ({count} signal(s))")
        return True
    except smtplib.SMTPException as exc:
        print(f"[notifier] Failed to send email: {exc}")
        return False
