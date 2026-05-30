import os
from dotenv import load_dotenv

load_dotenv()

# Email
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "vickomela36@gmail.com")

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "61d76708adf042e598dd7d7b6c37b7e9")

# Signal thresholds
MIN_PRICE_CHANGE_24H = float(os.getenv("MIN_PRICE_CHANGE_24H", "15"))   # %
MIN_PRICE_CHANGE_6H = float(os.getenv("MIN_PRICE_CHANGE_6H", "5"))      # %
MIN_VOLUME_24H = float(os.getenv("MIN_VOLUME_24H", "500000"))            # USD
MIN_MARKET_CAP = float(os.getenv("MIN_MARKET_CAP", "50000"))             # USD
MAX_MARKET_CAP = float(os.getenv("MAX_MARKET_CAP", "50000000"))          # USD
MIN_VOLUME_TO_MCAP = float(os.getenv("MIN_VOLUME_TO_MCAP", "0.30"))     # ratio
MIN_LIQUIDITY = float(os.getenv("MIN_LIQUIDITY", "50000"))               # USD

# Scanner
TARGET_CHAIN = os.getenv("TARGET_CHAIN", "solana")
MAX_TOKENS_TO_SCAN = int(os.getenv("MAX_TOKENS_TO_SCAN", "100"))
