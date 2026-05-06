import os
from dotenv import load_dotenv

load_dotenv()

# ── Solana wallet ─────────────────────────────────────────────────────────────
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# ── Gmail SMTP ────────────────────────────────────────────────────────────────
# Use a Gmail App Password (not your main password).
# https://myaccount.google.com/apppasswords
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# ── Notion ────────────────────────────────────────────────────────────────────
# Create an integration at https://www.notion.so/my-integrations and share the
# "Memecoin Buy Now Signals" database with it.
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv(
    "NOTION_DATABASE_ID", "b641d126-bc34-440e-a166-925febc843fc"
)

# ── Signal thresholds ─────────────────────────────────────────────────────────
# Minimum 1-hour price change (%) to qualify as a buy signal.
BUY_SIGNAL_PRICE_CHANGE_1H = float(os.getenv("BUY_SIGNAL_PRICE_CHANGE_1H", "10.0"))
# Minimum 24-hour trading volume (USD) to qualify.
BUY_SIGNAL_VOLUME_MIN = float(os.getenv("BUY_SIGNAL_VOLUME_MIN", "50000"))

# ── Scheduler ─────────────────────────────────────────────────────────────────
CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "1"))
