# Alert recipient
ALERT_EMAIL = "vickomela36@gmail.com"

# Notion data source ID for signal logging
NOTION_SIGNAL_DB = "collection://684a50fb-f6b5-44c6-b1f5-36a3a6f2679e"

# DexScreener search query (default: top Solana pairs)
DEXSCREENER_QUERY = "sol"

# Max pairs to evaluate per run
MAX_PAIRS = 30

# Signal thresholds
MIN_LIQUIDITY_USD = 20_000
MIN_VOLUME_24H_USD = 50_000
BUY_1H_CHANGE_PCT = 3.0       # must be above this
BUY_24H_CHANGE_PCT = 5.0      # must be above this
BUY_PRESSURE_RATIO = 0.55     # buys / (buys + sells)
SELL_1H_CHANGE_PCT = -5.0     # triggers sell signal
SELL_24H_CHANGE_PCT = -10.0   # triggers sell signal
