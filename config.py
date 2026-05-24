import os
from dotenv import load_dotenv

load_dotenv()

# Email
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "khraftsisworking@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = "vickomela36@gmail.com"

# Notion  (token from https://www.notion.so/my-integrations)
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "787edb6d23364430b1ca47d87981f3bc"

# Signal thresholds (edit to tune sensitivity)
MIN_LIQUIDITY_USD = 20_000
MIN_VOLUME_24H = 50_000
BUY_SIGNAL_MIN_SCORE = 4
