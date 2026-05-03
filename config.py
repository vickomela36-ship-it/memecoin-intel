ALERT_EMAIL = "vickomela36@gmail.com"

# Notion "Memecoin Buy Now Signals" database
NOTION_DATA_SOURCE_ID = "951ef2fb-9adb-4524-bedb-ff2272b44560"

# DexScreener pairs to monitor (chain/pairAddress).
# Leave empty to scan trending meme tokens automatically.
WATCHED_PAIRS = []

# Signal thresholds
BUY_1H_MIN_PCT    = 3.0    # 1h price change must be >= this
BUY_VOL24H_MIN    = 50_000 # 24h volume in USD must be >= this
BUY_PRESSURE_MIN  = 55.0   # buy pressure % must be >= this
SELL_1H_MAX_PCT   = -5.0   # 1h change at or below this triggers "sell"
SELL_PRESSURE_MAX = 40.0   # buy pressure at or below this triggers "sell"
