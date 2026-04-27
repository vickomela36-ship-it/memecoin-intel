"""
config.py — Central configuration for memecoin-intel.

Set environment variables or edit the defaults below.
"""

import os

# Wallet to track (Solana pubkey)
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")

# Notification
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "vickomela36@gmail.com")

# Notion
NOTION_DATABASE_ID = os.getenv(
    "NOTION_DATABASE_ID", "29d22a95-7503-40b9-9255-6757039bd87d"
)
NOTION_DATA_SOURCE_ID = os.getenv(
    "NOTION_DATA_SOURCE_ID", "684a50fb-f6b5-44c6-b1f5-36a3a6f2679e"
)

# Signal thresholds (can be overridden via env)
BUY_1H_THRESHOLD = float(os.getenv("BUY_1H_THRESHOLD", "3.0"))

# Tokens to watch (comma-separated CoinGecko IDs)
_default_tokens = (
    "bonk,dogwifcoin,popcat,book-of-meme,"
    "cat-in-a-dogs-world,pepe,floki,shiba-inu"
)
WATCHED_TOKENS = os.getenv("WATCHED_TOKENS", _default_tokens).split(",")
