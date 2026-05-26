import os

# Wallet / portfolio
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# Coins to monitor (CoinGecko IDs)
TRACKED_COINS = os.getenv(
    "TRACKED_COINS",
    "dogecoin,shiba-inu,pepe,floki,bonk,dogwifcoin,book-of-meme,brett,mog-coin,popcat",
).split(",")

# Signal thresholds
RSI_BUY_THRESHOLD = float(os.getenv("RSI_BUY_THRESHOLD", "35"))        # RSI below this → buy zone
RSI_SELL_THRESHOLD = float(os.getenv("RSI_SELL_THRESHOLD", "70"))       # RSI above this → sell zone
VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.0"))  # vs 7-day avg
PRICE_DIP_THRESHOLD = float(os.getenv("PRICE_DIP_THRESHOLD", "-8.0"))  # % 24h change

# Email
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "vickomela36@gmail.com")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Notion
NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "2a10f857667a49cda9dbf0783bf6144c")

# CoinGecko
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
