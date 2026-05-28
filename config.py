import os

# Wallet / portfolio
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# CoinGecko (free tier, no key needed; set for pro)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Coins to track (CoinGecko IDs)
TRACKED_COINS = [
    "dogecoin",
    "shiba-inu",
    "pepe",
    "floki",
    "bonk",
    "dogwifcoin",
    "brett",
    "popcat",
]

# Signal thresholds
BUY_SCORE_THRESHOLD = 60       # score >= this → "buy now"
SELL_SCORE_THRESHOLD = 35      # score <= this → "sell"

# Alert email
ALERT_TO_EMAIL = "vickomela36@gmail.com"
ALERT_FROM_EMAIL = os.getenv("GMAIL_FROM", "")   # sender Gmail address
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "ae1f8eb75a13411b882f6bd31c3c408d"
