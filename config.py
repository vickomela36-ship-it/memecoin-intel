import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

GMAIL_USER         = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL        = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")
NOTION_TOKEN       = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID       = os.getenv("NOTION_DB_ID", "b641d126bc34440ea166925febc843fc")
BUY_SCORE_THRESHOLD = float(os.getenv("BUY_SCORE_THRESHOLD", "70"))
WATCH_TOKENS       = [t.strip() for t in os.getenv("WATCH_TOKENS", "").split(",") if t.strip()]
