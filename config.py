ALERT_EMAIL = "vickomela36@gmail.com"

# DexScreener — free, no key needed
DEXSCREENER_BASE = "https://api.dexscreener.com"
SOLANA_CHAIN = "solana"

# Signal thresholds
MIN_VOLUME_24H   = 50_000     # $50k
MIN_LIQUIDITY    = 10_000     # $10k
MAX_FDV          = 10_000_000 # $10M
BUY_MOMENTUM_1H  = 5.0        # % gain in 1h
BUY_MOMENTUM_6H  = 10.0       # % gain in 6h
MAX_DROP_24H     = -30.0      # below this → sell flag

# Notion — "Memecoin Buy Now Signals" database
NOTION_DB_URL      = "https://www.notion.so/ec3ba050a06d40c2a92ea87b51ceb459"
NOTION_DATASOURCE  = "collection://c57d31d6-ddd4-49bb-ba4a-ee5b97b580e3"

DEXSCREENER_TOKEN_URL = "https://dexscreener.com/solana/{address}"
