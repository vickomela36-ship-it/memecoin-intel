import os

# ═══════════════════════════════════════════════════════════════════════════════
# API Keys
# ═══════════════════════════════════════════════════════════════════════════════
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "8292769f-aeb2-471c-af1d-fb98576972e4")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "dac9521a4c004f65897b2bd3e52cf10d")

# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════════════════════
DEXSCREENER_BOOSTS_TOP = "https://api.dexscreener.com/token-boosts/top/v1"
DEXSCREENER_BOOSTS_LATEST = "https://api.dexscreener.com/token-boosts/latest/v1"
DEXSCREENER_PROFILES = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"
DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens"

HELIUS_RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
BIRDEYE_API = "https://public-api.birdeye.so"
RUGCHECK_API = "https://api.rugcheck.xyz/v1"

# ═══════════════════════════════════════════════════════════════════════════════
# Token Filtering Thresholds
# ═══════════════════════════════════════════════════════════════════════════════
MIN_24H_VOLUME = 50_000
MIN_5M_VOLUME = 500
MIN_LIQUIDITY = 5_000
MIN_TOKEN_AGE_HOURS = 1
MIN_HOLDER_COUNT = 20
MAX_TOP10_HOLDER_PCT = 70.0

# ═══════════════════════════════════════════════════════════════════════════════
# Technical Analysis
# ═══════════════════════════════════════════════════════════════════════════════
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
OHLCV_1M_CANDLES = 60
OHLCV_5M_CANDLES = 288
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIB_PROXIMITY_PCT = 3.0

# ═══════════════════════════════════════════════════════════════════════════════
# Confidence Scoring Weights (must sum to 1.0)
# ═══════════════════════════════════════════════════════════════════════════════
WEIGHT_FIB = 0.20
WEIGHT_RSI = 0.15
WEIGHT_VOLUME = 0.20
WEIGHT_SENTIMENT = 0.15
WEIGHT_HOLDERS = 0.10
WEIGHT_VWAP = 0.10
WEIGHT_PATTERN = 0.10

GRADE_A_MIN = 80
GRADE_B_MIN = 60
GRADE_C_MIN = 40

# ═══════════════════════════════════════════════════════════════════════════════
# Risk Management
# ═══════════════════════════════════════════════════════════════════════════════
STOP_LOSS_PCT = 15
TAKE_PROFIT_2X = 2.0
TAKE_PROFIT_3X = 3.0

# ═══════════════════════════════════════════════════════════════════════════════
# Data Files
# ═══════════════════════════════════════════════════════════════════════════════
SIGNALS_FILE = "signals_log.json"
WATCHLIST_FILE = "watchlist.json"
TRADES_FILE = "trades.json"

# ═══════════════════════════════════════════════════════════════════════════════
# Search queries for DexScreener discovery
# ═══════════════════════════════════════════════════════════════════════════════
SEARCH_QUERIES = [
    "SOL", "PUMP", "MEME", "BONK", "WIF", "PEPE",
    "DOGE", "CAT", "AI", "TRUMP", "MOON", "SOLANA",
]
