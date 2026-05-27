import os

# Override via environment variables or GitHub Secrets
WALLET_ADDRESS = os.environ.get("WALLET_ADDRESS", "")
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")  # optional Pro key

# Memecoins tracked by the signal engine
TRACKED_COINS = [
    "dogecoin", "shiba-inu", "pepe", "floki", "bonk",
    "dogwifhat", "brett", "mog-coin", "popcat", "book-of-meme",
]

# Score thresholds (see signals.py for scoring logic)
BUY_SCORE_THRESHOLD = 4
WATCH_SCORE_THRESHOLD = 2
