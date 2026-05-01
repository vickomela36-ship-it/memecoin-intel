WALLET_ADDRESS = ""  # Your Solana wallet address

NOTIFY_EMAIL = "vickomela36@gmail.com"

# DexScreener (no key needed)
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"

# Signal thresholds
BUY_PRICE_CHANGE_5M = 3.0    # % minimum 5m price change
BUY_PRICE_CHANGE_1H = 8.0    # % minimum 1h price change
BUY_VOLUME_5M_USD   = 10_000  # $ minimum 5m volume
BUY_LIQUIDITY_USD   = 50_000  # $ minimum liquidity
SELL_PRICE_CHANGE_5M = -5.0  # % threshold for sell signal
SELL_PRICE_CHANGE_1H = -15.0 # % threshold for sell signal

TARGET_CHAINS = ["solana", "bsc", "ethereum"]
TOP_PAIRS_LIMIT = 50
