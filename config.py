import os

# ═══════════════════════════════════════════════════════════════════════════════
# API Keys
# ═══════════════════════════════════════════════════════════════════════════════
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "8292769f-aeb2-471c-af1d-fb98576972e4")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "dac9521a4c004f65897b2bd3e52cf10d")
FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "6c1d5875fd9b4b67a1d3d89d7aaf83b1")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "635bcc979566ecf1df7ab7231f1d1c69")

# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints — Memecoin Scanner
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
# API Endpoints — Crypto Predictions
# ═══════════════════════════════════════════════════════════════════════════════
COINGECKO_API = "https://api.coingecko.com/api/v3"
FEAR_GREED_API = "https://api.alternative.me/fng"
BINANCE_FAPI = "https://fapi.binance.com"
DEFILLAMA_API = "https://api.llama.fi"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"

# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints — Football Predictions
# ═══════════════════════════════════════════════════════════════════════════════
FOOTBALL_DATA_API = "https://api.football-data.org/v4"
ODDS_API = "https://api.the-odds-api.com/v4"

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
# Crypto Prediction Settings
# ═══════════════════════════════════════════════════════════════════════════════
CRYPTO_CACHE_SECONDS = 21600   # 6 hours
CRYPTO_STALE_SECONDS = 43200   # 12 hours

CRYPTO_ASSETS = {
    "BTC": {"coingecko_id": "bitcoin", "binance_symbol": "BTCUSDT", "chain": "Bitcoin"},
    "ETH": {"coingecko_id": "ethereum", "binance_symbol": "ETHUSDT", "chain": "Ethereum"},
    "SOL": {"coingecko_id": "solana", "binance_symbol": "SOLUSDT", "chain": "Solana"},
    "DOGE": {"coingecko_id": "dogecoin", "binance_symbol": "DOGEUSDT", "chain": None},
}

CRYPTO_SIGNAL_WEIGHTS = {
    "rsi": 0.15,
    "ma_cross": 0.15,
    "macd": 0.10,
    "volume": 0.10,
    "fear_greed": 0.10,
    "funding_rate": 0.15,
    "tvl": 0.10,
    "polymarket": 0.15,
}

# ═══════════════════════════════════════════════════════════════════════════════
# Data Files
# ═══════════════════════════════════════════════════════════════════════════════
SIGNALS_FILE = "signals_log.json"
DEGEN_SIGNALS_FILE = "degen_signals_log.json"
WATCHLIST_FILE = "watchlist.json"
TRADES_FILE = "trades.json"
CRYPTO_PREDICTIONS_FILE = "crypto_predictions_log.json"
FOOTBALL_CACHE_FILE = "football_cache.json"

# ═══════════════════════════════════════════════════════════════════════════════
# Search queries for DexScreener discovery
# ═══════════════════════════════════════════════════════════════════════════════
SEARCH_QUERIES = [
    "SOL", "PUMP", "MEME", "BONK", "WIF", "PEPE",
    "DOGE", "CAT", "AI", "TRUMP", "MOON", "SOLANA",
]
