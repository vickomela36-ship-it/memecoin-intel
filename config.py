import os

# Notion
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = "0745c86c-6824-46ed-9bbf-7e8b0d53395d"

# Email (Gmail SMTP)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]          # your Gmail address
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]  # Gmail app password
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Tokens to monitor — comma-separated CoinGecko IDs
TOKENS = os.getenv(
    "TOKENS",
    "pepe,dogecoin,shiba-inu,floki,bonk",
).split(",")

# Signal thresholds
BUY_NOW_HIGH_THRESHOLD = float(os.getenv("BUY_NOW_HIGH_THRESHOLD", "5.0"))   # 1h % gain → high confidence
BUY_NOW_MED_THRESHOLD = float(os.getenv("BUY_NOW_MED_THRESHOLD", "2.0"))    # 1h % gain → medium confidence
SELL_THRESHOLD = float(os.getenv("SELL_THRESHOLD", "-5.0"))                  # 1h % loss → sell
MIN_VOLUME_USD = float(os.getenv("MIN_VOLUME_USD", "1_000_000"))             # minimum 24 h volume filter

# How many hours must pass before re-alerting on the same token
ALERT_COOLDOWN_HOURS = int(os.getenv("ALERT_COOLDOWN_HOURS", "4"))

# State file tracks last-alert timestamps to avoid duplicate emails
STATE_FILE = os.getenv("STATE_FILE", "/tmp/memecoin_alert_state.json")
