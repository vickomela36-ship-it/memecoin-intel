import os
from dotenv import load_dotenv

load_dotenv()

# Tokens to monitor — comma-separated symbols (DEX Screener will find best pair)
WATCHED_TOKENS = os.getenv("WATCHED_TOKENS", "BONK,WIF,PEPE,TRUMP,POPCAT").split(",")

# Blockchain to filter pairs on
CHAIN = os.getenv("CHAIN", "solana")

# Buy signal thresholds
PRICE_CHANGE_1H_MIN = float(os.getenv("PRICE_CHANGE_1H_MIN", "5.0"))  # % in last 1h
VOLUME_1H_MIN       = float(os.getenv("VOLUME_1H_MIN", "50000"))       # USD volume in 1h
LIQUIDITY_MIN       = float(os.getenv("LIQUIDITY_MIN", "10000"))       # USD liquidity

# Email (standalone SMTP path — needs Gmail App Password)
EMAIL_RECIPIENT    = os.getenv("EMAIL_RECIPIENT", "vickomela36@gmail.com")
SMTP_SERVER        = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT          = int(os.getenv("SMTP_PORT", "587"))
GMAIL_USER         = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Notion (standalone REST path — needs integration token)
NOTION_TOKEN       = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "951ef2fb9adb4524bedbff2272b44560")
