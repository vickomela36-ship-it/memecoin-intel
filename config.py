import os
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
ALERT_EMAIL = "vickomela36@gmail.com"

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
# Pre-created "Memecoin Buy Signals Log" database
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "9ef4b2232d1a41649c867a47f8b4350f")

CHAIN = os.getenv("CHAIN", "solana")

# Signal thresholds
MIN_PRICE_CHANGE_5M = float(os.getenv("MIN_PRICE_CHANGE_5M", "3.0"))
MIN_PRICE_CHANGE_1H = float(os.getenv("MIN_PRICE_CHANGE_1H", "8.0"))
MIN_VOLUME_1H_USD = float(os.getenv("MIN_VOLUME_1H_USD", "30000"))
MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", "5000"))
BUY_CONFIDENCE_THRESHOLD = float(os.getenv("BUY_CONFIDENCE_THRESHOLD", "0.65"))
