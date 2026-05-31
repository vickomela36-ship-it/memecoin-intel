import os

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = "vickomela36@gmail.com"

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = "33442efe90ab4838b1ccd8806961f1d6"

# CoinGecko IDs for memecoins to track
TRACKED_COINS = [
    "dogecoin",
    "shiba-inu",
    "pepe",
    "floki",
    "bonk",
    "dogwifcoin",
    "brett",
    "mog-coin",
    "book-of-meme",
    "popcat",
]

# Signal thresholds
BUY_MIN_CHANGE_24H = 15.0   # % gain in 24h
BUY_MIN_VOLUME_RATIO = 0.25  # volume / market_cap
SELL_MAX_CHANGE_24H = -20.0  # % drop in 24h
