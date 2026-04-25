import os
from dotenv import load_dotenv

load_dotenv()

# Wallet / chain
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# Gmail SMTP (use an App Password, not your main password)
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID = os.getenv("NOTION_DB_ID", "5ee05dcac8a4463fbf5639a2eb08f364")

# Signal thresholds
BUY_SCORE_THRESHOLD = float(os.getenv("BUY_SCORE_THRESHOLD", "70"))

# Tokens to watch (comma-separated contract addresses or symbols)
WATCH_TOKENS = [t.strip() for t in os.getenv("WATCH_TOKENS", "").split(",") if t.strip()]
