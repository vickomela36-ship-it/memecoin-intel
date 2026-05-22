import os

# Wallet / chain
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# Notion
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
# Database page ID for "Memecoin Buy Now Signals"
NOTION_DATABASE_ID = "673a2e467e3f4db1ad85fb0c320854d3"

# Gmail (App Password, not account password)
GMAIL_USER = os.environ["GMAIL_USER"]          # sender address
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
ALERT_RECIPIENT = "vickomela36@gmail.com"

# Signal thresholds
BUY_MIN_PRICE_CHANGE_24H = float(os.getenv("BUY_MIN_PRICE_CHANGE_24H", "15"))   # %
BUY_MIN_VOLUME_TO_MCAP   = float(os.getenv("BUY_MIN_VOLUME_TO_MCAP",   "0.10")) # ratio
BUY_MIN_MARKET_CAP       = float(os.getenv("BUY_MIN_MARKET_CAP",       "1e6"))  # USD
