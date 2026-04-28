import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def send_buy_signal_email(signal, cfg) -> None:
    if not cfg.GMAIL_USER or not cfg.GMAIL_APP_PASSWORD:
        log.warning("Gmail credentials not configured — skipping email")
        return

    subject = f"BUY NOW: {signal.symbol} ({signal.token})"
    body = (
        f"BUY NOW Signal Detected!\n\n"
        f"Token:        {signal.token} ({signal.symbol})\n"
        f"Price:        ${signal.price_usd}\n"
        f"1h Change:    {signal.change_1h}%\n"
        f"6h Change:    {signal.change_6h}%\n"
        f"24h Change:   {signal.change_24h}%\n"
        f"Volume 24h:   ${signal.volume_24h}\n"
        f"Liquidity:    ${signal.liquidity_usd}\n"
        f"Buy Pressure: {signal.buy_pressure}\n\n"
        f"DexScreener:  {signal.dexscreener_url}\n"
    )

    msg = MIMEMultipart()
    msg["From"] = cfg.GMAIL_USER
    msg["To"] = cfg.NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(cfg.GMAIL_USER, cfg.GMAIL_APP_PASSWORD)
        server.sendmail(cfg.GMAIL_USER, cfg.NOTIFY_EMAIL, msg.as_string())

    log.info("Email sent to %s for %s", cfg.NOTIFY_EMAIL, signal.symbol)
