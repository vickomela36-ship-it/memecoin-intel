import os
from dotenv import load_dotenv

load_dotenv()

# Memecoins to monitor (CoinGecko IDs)
MEMECOIN_IDS = [
    "dogecoin", "shiba-inu", "pepe", "bonk", "dogwifcoin",
    "floki", "baby-doge-coin", "brett", "book-of-meme", "popcat",
]

# Email alert settings
GMAIL_FROM = os.getenv("GMAIL_FROM_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
ALERT_EMAIL = "vickomela36@gmail.com"

# Notion integration
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv(
    "NOTION_DATABASE_ID", "958c4eaa-7978-470a-87a4-8b2bcf1e3cf3"
)
