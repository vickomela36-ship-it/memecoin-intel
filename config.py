import os
from dotenv import load_dotenv

load_dotenv()

WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# Comma-separated Solana token addresses to watch
WATCHED_TOKENS = [t.strip() for t in os.getenv("WATCHED_TOKENS", "").split(",") if t.strip()]

# Gmail — use an App Password (not your main password)
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = "vickomela36@gmail.com"

# Notion integration token + pre-created "Memecoin Buy Signals" database
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "684a50fb-f6b5-44c6-b1f5-36a3a6f2679e"
