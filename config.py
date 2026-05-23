import os
from dotenv import load_dotenv

load_dotenv()

# Gmail SMTP (use an App Password, not your main password)
GMAIL_USER         = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL        = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Notion integration
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID = os.getenv("NOTION_DB_ID", "4c5532436f5046579b4b0da6cd5fd89a")

# Signal scoring
BUY_SCORE_THRESHOLD = float(os.getenv("BUY_SCORE_THRESHOLD", "70"))

# Tokens to watch (comma-separated contract addresses; empty = scan trending)
WATCH_TOKENS = [t.strip() for t in os.getenv("WATCH_TOKENS", "").split(",") if t.strip()]
