"""
Wallet address, API keys, and token watchlist.
Set DEXSCREENER_TOKENS to the token addresses (Solana/ETH/BSC) you want to track.
"""

# Token addresses to monitor — add or remove as needed
WATCHED_TOKENS = [
    # Solana examples (replace with real addresses)
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # WIF
]

# Thresholds for "buy now" signal
BUY_MIN_1H_CHANGE_PCT   = 3.0    # 1h price change >= 3%
BUY_MIN_VOLUME_24H_USD  = 10_000  # at least $10k daily volume
BUY_MIN_LIQUIDITY_USD   = 5_000   # at least $5k liquidity
BUY_MIN_BUY_PRESSURE    = 55.0    # buy txns >= 55% of total txns

# Thresholds for "sell" signal
SELL_MAX_1H_CHANGE_PCT  = -5.0   # 1h price drop worse than -5%
