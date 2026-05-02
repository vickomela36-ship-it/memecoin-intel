import os
from dotenv import load_dotenv

load_dotenv()

ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Notion database for buy-signal logging
NOTION_DB_ID          = os.getenv("NOTION_DB_ID", "9ef4b2232d1a41649c867a47f8b4350f")
NOTION_DATA_SOURCE_ID = os.getenv("NOTION_DATA_SOURCE_ID", "73b5d85d-86bf-4b6e-b8d7-c43e92bc0391")

# Signal thresholds
BUY_SCORE_THRESHOLD = float(os.getenv("BUY_SCORE_THRESHOLD", "70"))

# Tokens to watch (comma-separated contract addresses or symbols)
# Leave blank to auto-scan trending memecoins
WATCH_TOKENS = [t.strip() for t in os.getenv("WATCH_TOKENS", "").split(",") if t.strip()]
