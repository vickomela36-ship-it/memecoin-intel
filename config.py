import os
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "vickomela36@gmail.com")

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "29d22a95750340b992556757039bd87d")

TOKEN_ADDRESSES = [
    addr.strip()
    for addr in os.getenv("TOKEN_ADDRESSES", "").split(",")
    if addr.strip()
]

# Signal thresholds
BUY_1H_CHANGE_THRESHOLD = float(os.getenv("BUY_1H_CHANGE_THRESHOLD", "5.0"))
BUY_MIN_LIQUIDITY = float(os.getenv("BUY_MIN_LIQUIDITY", "50000"))
BUY_PRESSURE_THRESHOLD = float(os.getenv("BUY_PRESSURE_THRESHOLD", "0.6"))
