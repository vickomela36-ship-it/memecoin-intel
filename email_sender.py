"""Send buy-signal alert emails via Gmail SMTP."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from config import GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_EMAIL_TO


def _build_html(signals: list[dict]) -> str:
    rows = ""
    for s in signals:
        color = "#22c55e" if s["signal"] == "buy now" else "#ef4444"
        rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:bold">{s['name']} <span style="color:#888;font-weight:normal">({s['symbol']})</span></td>
          <td style="padding:8px 12px;color:{color};font-weight:bold;text-transform:uppercase">{s['signal']}</td>
          <td style="padding:8px 12px">${s['price']:,.6f}</td>
          <td style="padding:8px 12px">{s['change_24h']:+.2f}%</td>
          <td style="padding:8px 12px">{s['rsi'] if s['rsi'] is not None else 'N/A'}</td>
          <td style="padding:8px 12px">{s['confidence'].upper()}</td>
        </tr>"""

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""
    <html><body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px">
      <h2 style="color:#22c55e">🚨 Memecoin Buy Signal Alert</h2>
      <p style="color:#94a3b8">{ts}</p>
      <p>The following coin(s) triggered a <strong style="color:#22c55e">BUY NOW</strong> signal:</p>
      <table style="border-collapse:collapse;width:100%;background:#1e293b;border-radius:8px;overflow:hidden">
        <thead>
          <tr style="background:#334155;color:#94a3b8;font-size:12px;text-transform:uppercase">
            <th style="padding:10px 12px;text-align:left">Coin</th>
            <th style="padding:10px 12px;text-align:left">Signal</th>
            <th style="padding:10px 12px;text-align:left">Price</th>
            <th style="padding:10px 12px;text-align:left">24h Change</th>
            <th style="padding:10px 12px;text-align:left">RSI</th>
            <th style="padding:10px 12px;text-align:left">Confidence</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="color:#64748b;font-size:12px;margin-top:24px">
        Signals are based on RSI, 24h price change, and volume spike analysis via CoinGecko.<br>
        This is not financial advice. Always do your own research.
      </p>
    </body></html>"""


def _build_text(signals: list[dict]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Memecoin Buy Signal Alert — {ts}", "=" * 50]
    for s in signals:
        lines.append(
            f"{s['name']} ({s['symbol']}): {s['signal'].upper()}  |  "
            f"${s['price']:,.6f}  |  {s['change_24h']:+.2f}%  |  "
            f"RSI={s['rsi']}  |  Confidence={s['confidence'].upper()}"
        )
    lines.append("\nNot financial advice. Always DYOR.")
    return "\n".join(lines)


def send_buy_alert(signals: list[dict]) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("  [Email] GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping email.")
        return False

    msg = MIMEMultipart("alternative")
    coin_names = ", ".join(s["name"] for s in signals)
    msg["Subject"] = f"🚨 BUY NOW Signal: {coin_names}"
    msg["From"] = GMAIL_USER
    msg["To"] = ALERT_EMAIL_TO

    msg.attach(MIMEText(_build_text(signals), "plain"))
    msg.attach(MIMEText(_build_html(signals), "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, ALERT_EMAIL_TO, msg.as_string())
        print(f"  [Email] Alert sent to {ALERT_EMAIL_TO} for: {coin_names}")
        return True
    except Exception as exc:
        print(f"  [Email] Failed to send: {exc}")
        return False
