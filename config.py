import os

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = "vickomela36@gmail.com"

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "958c4eaa-7978-470a-87a4-8b2bcf1e3cf3"

COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")

TRACKED_COINS = [
    "dogecoin", "shiba-inu", "pepe", "dogwifcoin", "bonk",
    "floki", "baby-doge-coin", "book-of-meme", "popcat",
    "mog-coin", "brett", "neiro-on-ethereum", "turbo",
    "coq-inu", "myro",
]

# Minimum 24h price change (%) for a buy now signal
BUY_NOW_MIN_PRICE_CHANGE = 5.0
# Minimum composite score for a buy now signal
BUY_NOW_MIN_SCORE = 55.0
