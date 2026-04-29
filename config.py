import os
from dotenv import load_dotenv

load_dotenv()

# Gmail SMTP (use an App Password, not your account password)
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "8ee78806328945b987038fd78cf405b6")

# DexScreener chain to monitor
DEXSCREENER_CHAIN = os.getenv("DEXSCREENER_CHAIN", "solana")

# Signal thresholds
BUY_SIGNAL_MIN_PRICE_CHANGE_5M = float(os.getenv("BUY_SIGNAL_MIN_PRICE_CHANGE_5M", "3.0"))
BUY_SIGNAL_MIN_PRICE_CHANGE_1H = float(os.getenv("BUY_SIGNAL_MIN_PRICE_CHANGE_1H", "8.0"))
BUY_SIGNAL_MIN_VOLUME_5M = float(os.getenv("BUY_SIGNAL_MIN_VOLUME_5M", "5000"))
BUY_SIGNAL_MIN_LIQUIDITY = float(os.getenv("BUY_SIGNAL_MIN_LIQUIDITY", "30000"))
