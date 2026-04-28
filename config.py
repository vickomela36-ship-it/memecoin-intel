ALERT_EMAIL = "vickomela36@gmail.com"

# Notion data source (existing "Memecoin Buy Signals" DB)
NOTION_DATA_SOURCE_ID = "684a50fb-f6b5-44c6-b1f5-36a3a6f2679e"

# DexScreener pairs to monitor (chain:pairAddress or token addresses)
# Add/remove pairs here. Defaults to trending boosted tokens if empty.
WATCHED_PAIRS = []

# Signal thresholds
BUY_1H_MIN_PCT    = 3.0   # 1h price change must be >= this
BUY_VOL24H_MIN    = 50_000  # 24h volume in USD must be >= this
BUY_PRESSURE_MIN  = 55.0  # buy pressure % must be >= this
SELL_1H_MAX_PCT   = -5.0  # 1h change at or below this triggers "sell"
SELL_PRESSURE_MAX = 40.0  # buy pressure at or below this triggers "sell"
