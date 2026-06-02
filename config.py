import os

RECIPIENT_EMAIL = "vickomela36@gmail.com"
SENDER_EMAIL = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = "4c43196280b44105831de53a9115e1c9"

# Add tokens to track here. Get pair addresses from https://dexscreener.com
# Example: {"chain": "solana", "pair_address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"}
TRACKED_TOKENS: list[dict] = [
    # {"chain": "solana", "pair_address": "<PAIR_ADDRESS>"},
    # {"chain": "ethereum", "pair_address": "<PAIR_ADDRESS>"},
]

# Buy signal thresholds
BUY_SIGNAL_MIN_PRICE_CHANGE_24H = 5.0   # minimum 24h price change %
BUY_SIGNAL_MIN_VOLUME_24H = 100_000     # minimum 24h volume in USD
BUY_SIGNAL_MIN_LIQUIDITY = 50_000       # minimum liquidity in USD
BUY_SIGNAL_MIN_BUY_SELL_RATIO = 1.2    # buys/sells ratio in last hour
