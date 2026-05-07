import os
from dotenv import load_dotenv

load_dotenv()

WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "b641d126-bc34-440e-a166-925febc843fc")
