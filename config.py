# Tokens to monitor — add Solana memecoin addresses here
# Format: (token_address, display_symbol, chain)
TOKENS_TO_MONITOR = [
    # ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "USDC", "solana"),
]

SIGNAL_THRESHOLDS = {
    "price_change_5m_buy": 3.0,    # % gain in 5 min
    "price_change_1h_buy": 5.0,    # % gain in 1 h
    "volume_usd_1h_min": 50_000,   # minimum hourly volume
    "liquidity_usd_min": 20_000,   # minimum pool liquidity
    "price_change_1h_sell": -10.0, # % drop in 1 h → sell
    "price_change_6h_sell": -20.0, # % drop in 6 h → sell
}

# Notion database (data-source ID) created for signal logging
NOTION_DATABASE_ID = "8d726f13-4f6f-426f-99fa-09bfc9255602"

ALERT_EMAIL = "vickomela36@gmail.com"
