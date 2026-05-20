import os

WALLET_ADDRESS = os.getenv("SOLANA_WALLET_ADDRESS", "")
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"

# Signal thresholds
BUY_PRICE_CHANGE_THRESHOLD = 15.0   # minimum 24h % gain to qualify
BUY_VOLUME_THRESHOLD = 100_000       # minimum 24h volume in USD

# Email
EMAIL_RECIPIENT = "vickomela36@gmail.com"
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Notion  (data source id from the existing "Memecoin Buy Now Signals" DB)
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "958c4eaa-7978-470a-87a4-8b2bcf1e3cf3")

# Meteora DLMM
METEORA_API = "https://dlmm-api.meteora.ag"
