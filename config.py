import os

# =============================================================================
# API Keys
# =============================================================================
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}")

# =============================================================================
# Strategy Parameters — Swing Recovery After Dump
# =============================================================================

# Token filters
MIN_TOKEN_AGE_HOURS = 24          # Only look at tokens older than 24h
MIN_MARKET_CAP_USD = 2_000_000    # Minimum $2M market cap
MIN_24H_VOLUME_USD = 500_000      # Minimum 24h volume to ensure liquidity

# Dump detection
DUMP_LOOKBACK_HOURS = 6           # How far back to detect a dump
DUMP_THRESHOLD_PCT = -30          # Price must have dropped at least 30% from recent high
VOLUME_SPIKE_MULTIPLIER = 2.0     # Volume during dump should be 2x normal

# Recovery entry signals
RECOVERY_BOUNCE_PCT = 5           # Price bounced at least 5% off the local bottom
RSI_OVERSOLD_THRESHOLD = 35       # RSI below this = oversold, good for entry
MIN_BUY_VOLUME_RATIO = 0.55      # Buy volume should exceed 55% of total during recovery

# Take-profit / stop-loss
TAKE_PROFIT_2X = 2.0              # First target: 2x entry
TAKE_PROFIT_3X = 3.0              # Second target: 3x entry
STOP_LOSS_PCT = -20               # Cut losses at -20%

# Position sizing
MAX_POSITION_SOL = 2.0            # Max SOL per trade
MAX_OPEN_POSITIONS = 5            # Max concurrent positions

# Scan interval
SCAN_INTERVAL_SECONDS = 60        # How often to scan for new opportunities

# =============================================================================
# Jupiter API
# =============================================================================
JUPITER_PRICE_API = "https://api.jup.ag/price/v2"
JUPITER_TOKEN_LIST_API = "https://tokens.jup.ag/tokens?tags=verified"

# =============================================================================
# Helius API
# =============================================================================
HELIUS_API_BASE = "https://api.helius.xyz/v0"
HELIUS_RPC_BASE = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# =============================================================================
# Birdeye API (fallback for OHLCV / market data)
# =============================================================================
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "")
BIRDEYE_API_BASE = "https://public-api.birdeye.so"

# =============================================================================
# Data storage
# =============================================================================
TRADES_LOG_FILE = "trades.json"
