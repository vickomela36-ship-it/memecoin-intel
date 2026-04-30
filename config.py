# Tokens to monitor — add/remove pairs freely
WATCH_LIST = [
    {"symbol": "BONK", "chain": "solana"},
    {"symbol": "WIF",  "chain": "solana"},
    {"symbol": "POPCAT", "chain": "solana"},
    {"symbol": "PEPE", "chain": "ethereum"},
    {"symbol": "FLOKI", "chain": "ethereum"},
]

# Notion
NOTION_DATA_SOURCE_ID = "73b5d85d-86bf-4b6e-b8d7-c43e92bc0391"

# Notifications
EMAIL_RECIPIENT = "vickomela36@gmail.com"

# Signal thresholds
BUY_PRICE_CHANGE_1H   = 5.0   # % 1-hour gain required
BUY_VOLUME_RATIO      = 1.5   # current-hour volume vs trailing avg
SELL_PRICE_CHANGE_1H  = -10.0 # % 1-hour drop that triggers sell
