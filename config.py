import os

WALLET_ADDRESS = os.environ.get("WALLET_ADDRESS", "")

# Coins to track — Solana token addresses via DexScreener
COINS_TO_TRACK = [
    {"name": "BONK",   "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
    {"name": "WIF",    "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
    {"name": "POPCAT", "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"},
    {"name": "MEW",    "address": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5"},
]

# Email
EMAIL_TO           = "vickomela36@gmail.com"
EMAIL_FROM         = os.environ.get("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# Notion
NOTION_TOKEN       = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = "958c4eaa-7978-470a-87a4-8b2bcf1e3cf3"
