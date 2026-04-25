import os
from dotenv import load_dotenv

load_dotenv()

# Notion
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = "fdab4e7b-859d-4a83-8db8-743fcad7cbe4"

# Gmail SMTP (use an App Password, not your account password)
GMAIL_SENDER = os.environ["GMAIL_SENDER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
ALERT_EMAIL = "vickomela36@gmail.com"

# Comma-separated token symbols to monitor via DexScreener
TOKENS = os.getenv("TOKENS_TO_MONITOR", "PEPE,WIF,BONK,DOGE,SHIB").split(",")

# Minimum score (0–10) to trigger a "buy now" signal
BUY_THRESHOLD = float(os.getenv("BUY_SIGNAL_THRESHOLD", "6.0"))
