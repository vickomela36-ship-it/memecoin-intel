import os
from dotenv import load_dotenv

load_dotenv()

# Gmail SMTP (use a Gmail App Password, not your account password)
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = "vickomela36@gmail.com"

# Notion integration token + database
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "9ef4b2232d1a41649c867a47f8b4350f"

# Signal thresholds
BUY_CONFIDENCE_THRESHOLD = 60      # minimum score to emit 'buy now'
MIN_LIQUIDITY_USD = 50_000          # ignore pools below this
MIN_VOLUME_24H_USD = 100_000        # ignore low-volume coins

# Solana chain tokens to scan (leave empty to auto-fetch trending ones)
WATCH_TOKENS: list[str] = [
    t.strip() for t in os.getenv("WATCH_TOKENS", "").split(",") if t.strip()
]
