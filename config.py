import os

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
# Database: "Memecoin Buy Now Signals"
NOTION_DATABASE_ID = "b641d126-bc34-440e-a166-925febc843fc"

# Gmail (SMTP with App Password)
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = "vickomela36@gmail.com"

# Buy signal thresholds (override via env vars)
BUY_SIGNAL_MIN_VOLUME_USD = float(os.getenv("BUY_SIGNAL_MIN_VOLUME_USD", "100000"))
BUY_SIGNAL_MIN_PRICE_CHANGE_PCT = float(os.getenv("BUY_SIGNAL_MIN_PRICE_CHANGE_PCT", "5.0"))
BUY_SIGNAL_MIN_LIQUIDITY_USD = float(os.getenv("BUY_SIGNAL_MIN_LIQUIDITY_USD", "50000"))
