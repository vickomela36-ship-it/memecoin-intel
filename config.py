import os
from dotenv import load_dotenv

load_dotenv()

# Gmail SMTP — create an App Password at https://myaccount.google.com/apppasswords
GMAIL_USER         = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL        = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Notion — integration token from https://www.notion.so/my-integrations
NOTION_TOKEN          = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID          = os.getenv("NOTION_DB_ID",          "9ef4b2232d1a41649c867a47f8b4350f")
NOTION_DATA_SOURCE_ID = os.getenv("NOTION_DATA_SOURCE_ID", "73b5d85d-86bf-4b6e-b8d7-c43e92bc0391")

# Signal thresholds
BUY_SCORE_THRESHOLD = float(os.getenv("BUY_SCORE_THRESHOLD", "70"))

# Tokens to watch (comma-separated contract addresses); leave blank to scan trending
WATCH_TOKENS = [t.strip() for t in os.getenv("WATCH_TOKENS", "").split(",") if t.strip()]
