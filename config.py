# Tokens to monitor — add any Solana/EVM contract addresses here
TRACKED_TOKENS = [
    {
        "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "symbol": "BONK",
        "name": "Bonk",
    },
    {
        "address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
        "symbol": "POPCAT",
        "name": "Popcat",
    },
    {
        "address": "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82",
        "symbol": "BOME",
        "name": "Book of Meme",
    },
    {
        "address": "ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzc8Eu",
        "symbol": "MOODENG",
        "name": "Moo Deng",
    },
]

# Buy signal thresholds — tune these to your risk appetite
BUY_SIGNAL_CONDITIONS = {
    "min_1h_price_change_pct": 15.0,   # at least +15% in the last hour
    "min_volume_24h_usd":      50_000, # at least $50k 24h volume
    "min_liquidity_usd":       10_000, # at least $10k liquidity pool depth
}
